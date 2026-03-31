from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import settings

def get_engine():
    url = settings.DATABASE_URL
    
    if url.startswith("sqlite"):
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