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
    description="ERP for Carpintería El Menestral",
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
    # Tech-debt: wildcard origins for LAN mode.  The server PC is a trusted
    # network host; restricting origins would break multi-PC LAN sharing.
    allow_origins=["*"],
    allow_credentials=False,
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
            hashed = bcrypt.hashpw("elmenestral123".encode(), bcrypt.gensalt())
            admin = User(
                username="elmenestral",
                email="info@elmenestral.com",
                hashed_password=hashed.decode(),
                role="admin",
                is_active=True
            )
            db.add(admin)
            db.commit()
            logger.info("Default admin user created: elmenestral")
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
