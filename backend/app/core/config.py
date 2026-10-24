from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "AlphaQuant Dhan Market Screener"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-key-alpha-quant-production-2026")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ALGORITHM: str = "HS256"
    
    # Session & Database configuration
    DATABASE_URL: str = "sqlite:///./backend/data/alphaquant.db"
    SESSION_STORAGE_PATH: str = "./backend/data/.session.json"
    ENCRYPTION_KEY: Optional[str] = os.getenv("ENCRYPTION_KEY", "DhanAlphaEncryptionKeySecret32b!")
    
    # Default Admin Credentials
    DEFAULT_ADMIN_USERNAME: str = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "Admin@12345")
    
    # Scanner defaults
    AUTO_SCAN_INTERVAL_SECONDS: int = 30

    # Dhan Headless Automated Daily Login Settings
    DHAN_CLIENT_ID: Optional[str] = os.getenv("DHAN_CLIENT_ID", "")
    DHAN_PIN: Optional[str] = os.getenv("DHAN_PIN", "")
    DHAN_TOTP_SECRET: Optional[str] = os.getenv("DHAN_TOTP_SECRET", "")
    AUTO_RENEW_DHAN_TOKEN: bool = True

    class Config:
        env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), ".env")
        case_sensitive = True

settings = Settings()
