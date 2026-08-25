import logging
import os
import socket
import sys
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from limiter import limiter
from database import engine, SessionLocal
from models import Base
from routers.api import router
from routers.invoices import router as invoices_router
from routers.electronic_invoicing import router as electronic_invoicing_router
from routers import auth
from config import settings
from utils.paths import get_base_dir

# ── reportlab barcode preload (non-fatal) ──────────────────────────────
# PyInstaller frozen apps cannot handle reportlab.graphics.barcode's
# dynamic exec()-based imports (_reset).  Preload all submodules here
# so they are in sys.modules before any code triggers _reset.
# Wrapped in try/except because this runs during boot — a failure here
# must NOT crash the backend.
try:
    import importlib.util
    import types

    import reportlab
    import reportlab.graphics

    _BARCODE_MODULES = [
        'reportlab.graphics.barcode.code128',
        'reportlab.graphics.barcode.code39',
        'reportlab.graphics.barcode.code93',
        'reportlab.graphics.barcode.common',
        'reportlab.graphics.barcode.eanbc',
        'reportlab.graphics.barcode.usps',
        'reportlab.graphics.barcode.usps4s',
        'reportlab.graphics.barcode.ecc200datamatrix',
        'reportlab.graphics.barcode.fourstate',
        'reportlab.graphics.barcode.lto',
        'reportlab.graphics.barcode.qr',
        'reportlab.graphics.barcode.qrencoder',
        'reportlab.graphics.barcode.dmtx',
        'reportlab.graphics.barcode.widgets',
    ]

    fake_pkg = types.ModuleType('reportlab.graphics.barcode')
    fake_pkg.__path__ = []
    fake_pkg.__package__ = 'reportlab.graphics.barcode'
    # Save the real module so we can restore it if preload fails
    _real_bc = sys.modules.get('reportlab.graphics.barcode')
    if _real_bc is not None:
        sys.modules['_reportlab_bc_real_preload'] = _real_bc
    sys.modules['reportlab.graphics.barcode'] = fake_pkg

    for modname in _BARCODE_MODULES:
        if modname in sys.modules:
            continue
        for importer in sys.meta_path:
            if hasattr(importer, 'find_spec'):
                spec = importer.find_spec(modname)
                if spec is not None:
                    try:
                        mod = importlib.util.module_from_spec(spec)
                        sys.modules[modname] = mod
                        spec.loader.exec_module(mod)
                    except Exception:
                        if modname in sys.modules:
                            del sys.modules[modname]
                    break

    # Replace fake package with real one
    del sys.modules['reportlab.graphics.barcode']
    import reportlab.graphics.barcode  # noqa: F811
except Exception as exc:
    # Roll back the fake package so downstream imports (xhtml2pdf) get the
    # real reportlab.graphics.barcode module, not our stub.
    _real_bc = sys.modules.get('_reportlab_bc_real_preload')
    if _real_bc is not None:
        sys.modules['reportlab.graphics.barcode'] = _real_bc
        del sys.modules['_reportlab_bc_real_preload']
    elif 'reportlab.graphics.barcode' in sys.modules:
        # fake_pkg or partial — remove it so Python re-imports the real one
        del sys.modules['reportlab.graphics.barcode']
    logging.getLogger(__name__).warning(
        "reportlab barcode preload skipped (%s). Barcode features may not work.", exc
    )
# ────────────────────────────────────────────────────────────────────────

# Usar directorio del ejecutable para logs (NO _MEIPASS)
LOG_DIR = get_base_dir() / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            str(LOG_DIR / "app.log"),
            maxBytes=10 * 1024 * 1024,
            backupCount=5
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LAN_PORT = 8000


def _get_lan_ip():
    """Return the machine's LAN IP address, falling back to 127.0.0.1."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app):
    """Manage application startup and shutdown lifecycle.

    Startup: create tables, seed admin user.
    Shutdown: flush WAL into main DB file.
    """
    # --- startup ---
    logger.info("GA ERP System started")

    # --- yield to application ---
    yield

    # --- shutdown ---
    logger.info("GA ERP System shutting down")
    try:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
            conn.commit()
    except Exception as exc:
        logger.error(f"WAL checkpoint failed: {exc}")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="GA ERP System",
    description="ERP for Ordo ERP",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."}
    )

app.add_middleware(
    CORSMiddleware,
    # allow_origins=["*"] + allow_credentials=True makes Starlette echo
    # the request's origin (e.g. "tauri://localhost") instead of "*".
    # This is REQUIRED because Chromium/Webview2 rejects wildcard when
    # the origin is a non-HTTP protocol like tauri://localhost.
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)[:200]}
    )


# Middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response


# create tables
Base.metadata.create_all(bind=engine)

# Create default admin user if not exists
from models import User
import bcrypt

def create_default_admin():
    db = SessionLocal()
    try:
        # Check if admin exists
        admin = db.query(User).filter(User.role == "admin").first()
        if not admin:
            # Create default admin user
            hashed = bcrypt.hashpw("ordo123".encode(), bcrypt.gensalt())
            admin = User(
                username="admin",
                email="info@ordoerp.com",
                hashed_password=hashed.decode(),
                role="admin",
                is_active=True
            )
            db.add(admin)
            db.commit()
            logger.info("Default admin user created: admin")
        else:
            logger.info("Admin user already exists")
    except Exception as e:
        logger.error(f"Error creating admin: {e}")
    finally:
        db.close()

# Create default admin on startup
create_default_admin()

# include routes
app.include_router(router)
app.include_router(invoices_router)
app.include_router(electronic_invoicing_router)
app.include_router(auth.router)
from routers import produccion
app.include_router(produccion.router)
from routers import presupuestos
app.include_router(presupuestos.router)
from routers import export
app.include_router(export.router)
from routers import suscripcion
app.include_router(suscripcion.router)
from routers import comprobantes
app.include_router(comprobantes.router)
from routers import barcodes
app.include_router(barcodes.router)

# Health check
@app.get("/health")
def health():
    lan_ip = _get_lan_ip()
    return {
        "status": "ok",
        "version": "1.0.0",
        "lan_ip": lan_ip,
        "port": LAN_PORT,
        "sharing_url": f"http://{lan_ip}:{LAN_PORT}",
        "db": "wal",
    }


# Mount frontend static files at root (after all API routes)
_frontend_dist = get_base_dir() / "frontend" / "dist"
if not _frontend_dist.exists():
    # Fallback: relative to backend/ directory
    _frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")


# ============================================================
# INICIO DEL SERVIDOR - Solo para PyInstaller
# ============================================================
if __name__ == "__main__":
    import uvicorn
    from utils.paths import is_frozen
    
    # Fix PyInstaller: stdout/stderr son None cuando console=False
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w')
    
    # Determinar host y puerto — 0.0.0.0 for LAN access
    host = "0.0.0.0"
    port = LAN_PORT
    
    logger.info(f"Iniciando servidor en {host}:{port}")
    
    # Configurar uvicorn directamente - sin reimportar
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
        log_config=None  # Usar nuestro logging, no el de uvicorn
    )
    server = uvicorn.Server(config)
    server.run()
