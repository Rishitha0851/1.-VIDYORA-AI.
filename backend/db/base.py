"""
VIDYORA AI - Declarative Base & Schema Conventions

Defines the SQLAlchemy 2.0 DeclarativeBase with explicit constraint naming conventions.
Consistent constraint naming guarantees seamless Alembic autogeneration and deterministic
migrations across environments.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Explicit naming conventions for constraints and indexes (Alembic best practice)
# Prevents database-vendor-specific generated names from causing migration drift.
POSTGRES_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """
    Root declarative base for all VIDYORA AI persistence entities.
    Inherits SQLAlchemy 2.0 mapped metadata configuration.
    """
    metadata = MetaData(naming_convention=POSTGRES_NAMING_CONVENTION)
