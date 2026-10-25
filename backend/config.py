"""
VIDYORA AI - Backend Configuration Management

Loads environment variables securely using python-dotenv with fallbacks,
providing type-safe access to application settings and secrets.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Search for .env in current working directory, backend directory, and project root
_BACKEND_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _BACKEND_DIR.parent

# Attempt loading from backend/.env first, then root .env
if (_BACKEND_DIR / ".env").is_file():
    load_dotenv(_BACKEND_DIR / ".env")
elif (_ROOT_DIR / ".env").is_file():
    load_dotenv(_ROOT_DIR / ".env")
else:
    load_dotenv()


class Settings:
    """Centralized configuration settings for VIDYORA AI backend."""

    @property
    def gemini_api_key(self) -> Optional[str]:
        """
        Retrieves the Google Gemini API key from the environment.
        Supports both GEMINI_API_KEY and GOOGLE_API_KEY.
        Returns None or empty string if not configured.
        """
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        return key.strip() if key else None

    @property
    def gemini_model(self) -> str:
        """
        The configured Gemini model identifier.
        Defaults to 'gemini-2.5-flash' for speed, quality, and low latency.
        """
        return os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

    @property
    def embedding_model(self) -> str:
        """Configured embedding model identifier (defaults to text-embedding-004)."""
        return os.getenv("EMBEDDING_MODEL", "text-embedding-004").strip()

    @property
    def embedding_dimension(self) -> int:
        """Vector dimensionality of the embedding model (defaults to 768)."""
        try:
            return int(os.getenv("EMBEDDING_DIMENSION", "768"))
        except ValueError:
            return 768

    @property
    def environment(self) -> str:
        """Operating environment (development, testing, production)."""
        return os.getenv("ENVIRONMENT", "development").strip().lower()

    @property
    def allowed_origins(self) -> list[str]:
        """
        List of origins permitted to access the backend via CORS.
        Parsed from comma-separated ALLOWED_ORIGINS and/or FRONTEND_URL.
        Always includes local dev origins in non-production environments.
        """
        origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
        ]
        custom_origins = os.getenv("ALLOWED_ORIGINS", "")
        if custom_origins:
            for item in custom_origins.split(","):
                cleaned = item.strip().rstrip("/")
                if cleaned and cleaned not in origins:
                    origins.append(cleaned)

        frontend_url = os.getenv("FRONTEND_URL", "").strip().rstrip("/")
        if frontend_url and frontend_url not in origins:
            origins.append(frontend_url)

        return origins

    @property
    def is_gemini_configured(self) -> bool:
        """Checks whether a valid Gemini API key is present."""
        return bool(self.gemini_api_key)

    def get_masked_api_key(self) -> str:
        """Returns a safe, masked representation of the key for diagnostics."""
        key = self.gemini_api_key
        if not key:
            return "NOT_CONFIGURED"
        if len(key) <= 8:
            return "****"
        return f"{key[:4]}...{key[-4:]}"

    # -----------------------------------------------------------------------
    # Authentication & JWT Configuration
    # -----------------------------------------------------------------------

    @property
    def jwt_secret_key(self) -> str:
        """Secret key used to cryptographically sign JWT access tokens."""
        return os.getenv("JWT_SECRET_KEY", "vidyora-default-insecure-dev-secret-key-change-in-production-2026")

    @property
    def jwt_algorithm(self) -> str:
        """Cryptographic algorithm used for signing JWTs (defaults to HS256)."""
        return os.getenv("JWT_ALGORITHM", "HS256").strip()

    @property
    def access_token_expire_minutes(self) -> int:
        """JWT token lifespan in minutes (defaults to 1440 min = 24 hours)."""
        try:
            return int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
        except ValueError:
            return 1440

    # -----------------------------------------------------------------------
    # Database Configuration (PostgreSQL / SQLAlchemy)
    # -----------------------------------------------------------------------

    @property
    def db_user(self) -> str:
        """PostgreSQL database username."""
        return os.getenv("DB_USER", "postgres").strip()

    @property
    def db_password(self) -> str:
        """PostgreSQL database user password."""
        return os.getenv("DB_PASSWORD", "").strip()

    @property
    def db_host(self) -> str:
        """PostgreSQL host address (defaults to localhost)."""
        return os.getenv("DB_HOST", "localhost").strip()

    @property
    def db_port(self) -> str:
        """PostgreSQL port (defaults to 5432)."""
        return os.getenv("DB_PORT", "5432").strip()

    @property
    def db_name(self) -> str:
        """PostgreSQL database name (defaults to vidyora_ai)."""
        return os.getenv("DB_NAME", "vidyora_ai").strip()

    @property
    def database_url(self) -> str:
        """
        Calculates the complete SQLAlchemy database connection URL.
        
        Priority:
        1. If DATABASE_URL is set, use it directly (normalizing postgresql://
           to postgresql+psycopg2:// for SQLAlchemy 2.0).
        2. Otherwise, construct from DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, and DB_NAME.
        """
        raw_url = os.getenv("DATABASE_URL")
        if raw_url:
            raw_url = raw_url.strip()
            # Normalize PostgreSQL dialect for SQLAlchemy 2.0 / psycopg2
            if raw_url.startswith("postgresql://"):
                return raw_url.replace("postgresql://", "postgresql+psycopg2://", 1)
            return raw_url

        user = self.db_user
        password = self.db_password
        host = self.db_host
        port = self.db_port
        name = self.db_name

        if password:
            return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
        return f"postgresql+psycopg2://{user}@{host}:{port}/{name}"

    @property
    def is_database_configured(self) -> bool:
        """Checks if a valid database URL or explicit database credentials are provided."""
        return bool(os.getenv("DATABASE_URL") or os.getenv("DB_PASSWORD"))

    def get_masked_database_url(self) -> str:
        """
        Returns a sanitized database URL with password masked for safe logging.
        Prevents credential leakage in log files or console diagnostics.
        """
        url = self.database_url
        if "@" not in url:
            return url
        try:
            # Format: dialect://user:password@host:port/dbname
            scheme_and_auth, rest = url.split("@", 1)
            if ":" in scheme_and_auth:
                prefix, _ = scheme_and_auth.rsplit(":", 1)
                return f"{prefix}:****@{rest}"
            return url
        except Exception:
            return "postgresql+psycopg2://****@****"


settings = Settings()
