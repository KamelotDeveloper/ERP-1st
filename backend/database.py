from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from config import settings
from utils.paths import is_frozen, get_base_dir
import os
import sqlite3


def apply_sqlite_pragmas(dbapi_connection, connection_record):
    """Set WAL journal mode and concurrency pragmas on SQLite connect.

    Designed to be used as a SQLAlchemy ``event.listens_for(engine, "connect")``
    callback, or called directly with a raw DB-API connection.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


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
        
        eng = create_engine(
            url,
            connect_args={"check_same_thread": False}
        )
        event.listen(eng, "connect", apply_sqlite_pragmas)
        return eng
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