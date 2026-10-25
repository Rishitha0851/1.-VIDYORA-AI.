import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ---------------------------------------------------------------------------
# Path Configuration & Schema Metadata
# ---------------------------------------------------------------------------
# Ensure the backend directory is in sys.path so config and db can be resolved
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from config import settings
from db.base import Base
import db.models  # noqa: F401 - registers all 12 ORM models on Base.metadata

# Alembic Config object
config = context.config

# Setup Python logging if config file present
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata to our centralized Base
target_metadata = Base.metadata


def get_url() -> str:
    """Retrieves normalized database URL from centralized application settings."""
    return settings.database_url


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    Emits SQL statements directly to STDOUT or file without requiring an active DB connection.
    Useful for generating SQL audit scripts or pre-deployment reviews.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.
    Creates an Engine connected to the target database and applies changes in a transaction.
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
