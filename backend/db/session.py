"""
VIDYORA AI - Database Session & Connection Management

Provides database engine instantiation, connection pooling, and FastAPI session
lifecycle dependency. Uses SQLAlchemy 2.0 with PostgreSQL/psycopg2.
"""

import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine Configuration & Connection Pooling
# ---------------------------------------------------------------------------
# pool_pre_ping=True: Validates connection vitality prior to checkout, preventing
#                     stale connection errors when the DB restarts or drops idle TCP.
# pool_size=5: Maintains up to 5 permanent pooled connections per worker process.
# max_overflow=10: Accommodates temporary spikes up to 10 additional connections.
# pool_recycle=1800: Recycles connections after 30 minutes to prevent backend drops.
# ---------------------------------------------------------------------------

def create_app_engine(url: str | None = None):
    """Factory creating an engine with production-minded pool settings."""
    db_url = url or settings.database_url
    
    # If using SQLite (e.g. in standalone unit tests), configure accordingly
    if db_url.startswith("sqlite"):
        return create_engine(
            db_url,
            connect_args={"check_same_thread": False},
        )

    return create_engine(
        db_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=1800,
        echo=False,
    )


# Application-level engine and session factory
engine = create_app_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a transactional SQLAlchemy database session.
    
    Guarantees session cleanup upon HTTP request resolution.
    Usage in FastAPI route:
      @app.get('/items')
      def read_items(db: Session = Depends(get_db)):
          ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection(custom_engine=None) -> tuple[bool, str]:
    """
    Lightweight health check verifying database reachability via 'SELECT 1'.
    Returns (True, 'Connected') or (False, error_message).
    Never throws uncaught exceptions.
    """
    target_engine = custom_engine or engine
    try:
        with target_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "Database connection healthy"
    except Exception as exc:
        masked_url = settings.get_masked_database_url()
        logger.warning("Database connection check failed against %s: %s", masked_url, exc)
        return False, str(exc)
