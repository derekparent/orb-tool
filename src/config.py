"""Flask application configuration."""

import os
from pathlib import Path


class Config:
    """Base configuration."""

    BASE_DIR = Path(__file__).parent.parent
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-change-in-production")

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'orb.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Data files
    SOUNDING_TABLES_PATH = BASE_DIR / "data" / "sounding_tables.json"

    # Security settings
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB file upload limit

    # Rate limiting storage (in production use Redis)
    RATELIMIT_STORAGE_URL = os.environ.get("REDIS_URL", "memory://")

    # CORS settings
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5001,https://localhost:5001").split(",")

    # Session security
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_SECURE", "False").lower() == "true"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False


class TestingConfig(Config):
    """Testing configuration."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}

