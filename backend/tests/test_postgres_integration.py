"""
VIDYORA AI - Live PostgreSQL Integration Tests

NOTE / METHODOLOGY:
These tests run exclusively against a real PostgreSQL instance when configured
and reachable. If PostgreSQL is not available locally or credentials are not yet
configured, the test suite skips gracefully with an explicit reason rather than
falsely claiming PostgreSQL was tested.
"""

import pytest
from sqlalchemy import text

from config import settings
from db.session import SessionLocal, check_db_connection, engine


def is_live_postgres_available() -> bool:
    """Checks whether the configured PostgreSQL instance is live and accessible."""
    if not settings.database_url.startswith("postgresql"):
        return False
    is_connected, _ = check_db_connection()
    return is_connected


@pytest.mark.skipif(
    not is_live_postgres_available(),
    reason=(
        "Live PostgreSQL instance not reachable with current environment credentials. "
        "To run live integration tests, ensure PostgreSQL is running and set DATABASE_URL "
        "or DB_PASSWORD in backend/.env."
    ),
)
def test_live_postgres_connection_and_transaction():
    """
    Verifies that a live connection to PostgreSQL can be established and that
    a transactional session can execute native PostgreSQL queries.
    """
    session = SessionLocal()
    try:
        result = session.execute(text("SELECT version();")).scalar()
        assert result is not None
        assert "PostgreSQL" in result
    finally:
        session.close()


@pytest.mark.skipif(
    not is_live_postgres_available(),
    reason="PostgreSQL not reachable for dialect verification.",
)
def test_live_postgres_engine_dialect():
    """Verifies that the SQLAlchemy engine binds to the PostgreSQL dialect."""
    assert engine.dialect.name == "postgresql"
