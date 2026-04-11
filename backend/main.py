import logging
import os
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from database import engine
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

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="GA ERP System",
    description="ERP for Carpintería El Menestral",
    version="1.0.0"
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
    allow_origins=[
        "*",
        "http://tauri.localhost",
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
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
from database import SessionLocal
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

# Health check
@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.on_event("startup")
async def startup_event():
    logger.info("GA ERP System started")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("GA ERP System shutting down")


# ============================================================
# INICIO DEL SERVIDOR - Solo para PyInstaller
# ============================================================
if __name__ == "__main__":
    import uvicorn
    from utils.paths import is_frozen
    
    # Determinar host y puerto
    host = "127.0.0.1"
    port = 8000
    
    logger.info(f"Iniciando servidor en {host}:{port}")
    
    # Configurar uvicorn directamente - sin reimportar
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info"
    )
    server = uvicorn.Server(config)
    server.run()
