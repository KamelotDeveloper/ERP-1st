import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database - SQLite default for desktop ERP
    DATABASE_URL: str = "sqlite:///./carpinteria.db"
    
    # JWT
    JWT_SECRET_KEY: str = "ga-erp-secret-key-local-desktop-erp"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True  # Default to True for desktop use
    
    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000,http://tauri.localhost"
    
    # Electronic Invoicing (ARCA/AFIP)
    # Mode: "mock" = simulated responses, "real" = actual ARCA API
    AFIP_MODE: str = "mock"
    AFIP_AMBIENTE: str = "testing"
    AFIP_CERT_PATH: Optional[str] = None
    AFIP_KEY_PATH: Optional[str] = None
    AFIP_CUIT: Optional[str] = None
    
    # Backup
    BACKUP_PATH: str = "./backups"
    BACKUP_RETENTION_DAYS: int = 30
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 5
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @property
    def allowed_origins_list(self) -> list:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]
    
    @property
    def is_afip_mock_mode(self) -> bool:
        return self.AFIP_MODE.lower() == "mock"
    
    @property
    def is_afip_real_mode(self) -> bool:
        return self.AFIP_MODE.lower() == "real" and self.AFIP_CERT_PATH and self.AFIP_KEY_PATH


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
