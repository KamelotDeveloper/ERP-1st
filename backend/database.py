from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import settings
from utils.paths import is_frozen, get_base_dir
import os


def get_engine():
    url = settings.DATABASE_URL
    
    if url.startswith("sqlite"):
        # Extraer el path de la URL
        db_path = url.replace("sqlite:///", "")
        
        if not os.path.isabs(db_path):
            # Es un path relativo - convertir a absoluto basado en la ubicación del exe
            base = get_base_dir()
            full_path = base / db_path
            url = f"sqlite:///{full_path}"
        
        return create_engine(
            url,
            connect_args={"check_same_thread": False}
        )
    elif url.startswith("postgresql"):
        return create_engine(
            url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20
        )
    else:
        raise ValueError(f"Unsupported database: {url}")

engine = get_engine()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()