"""
VIDYORA AI - Database Configuration Unit Tests

Verifies configuration loading, URL construction, PostgreSQL driver normalization,
and credential masking to prevent secret leakage.
"""

import os
from unittest.mock import patch

import pytest
from config import Settings


def test_default_database_settings():
    """Verifies that default database parameters load correctly when env is unset."""
    with patch.dict(os.environ, {}, clear=True):
        custom_settings = Settings()
        assert custom_settings.db_user == "postgres"
        assert custom_settings.db_password == ""
        assert custom_settings.db_host == "localhost"
        assert custom_settings.db_port == "5432"
        assert custom_settings.db_name == "vidyora_ai"
        assert custom_settings.database_url == "postgresql+psycopg2://postgres@localhost:5432/vidyora_ai"


def test_database_url_from_individual_env_vars():
    """Verifies URL composition when individual DB environment variables are set."""
    env = {
        "DB_USER": "test_user",
        "DB_PASSWORD": "secret_password",
        "DB_HOST": "db.vidyora.internal",
        "DB_PORT": "5433",
        "DB_NAME": "vidyora_prod",
    }
    with patch.dict(os.environ, env, clear=True):
        custom_settings = Settings()
        assert custom_settings.database_url == "postgresql+psycopg2://test_user:secret_password@db.vidyora.internal:5433/vidyora_prod"


def test_database_url_prefers_direct_database_url_env():
    """Verifies that explicit DATABASE_URL overrides individual components."""
    env = {
        "DATABASE_URL": "postgresql://custom_user:pass123@remotehost:5432/custom_db",
        "DB_USER": "ignored_user",
    }
    with patch.dict(os.environ, env, clear=True):
        custom_settings = Settings()
        # Verifies driver normalization: postgresql:// -> postgresql+psycopg2://
        assert custom_settings.database_url == "postgresql+psycopg2://custom_user:pass123@remotehost:5432/custom_db"


def test_masked_database_url_prevents_password_exposure():
    """Verifies that get_masked_database_url masks sensitive passwords for logs."""
    env = {
        "DATABASE_URL": "postgresql+psycopg2://admin:super_secret_password@localhost:5432/vidyora_ai"
    }
    with patch.dict(os.environ, env, clear=True):
        custom_settings = Settings()
        masked = custom_settings.get_masked_database_url()
        assert "super_secret_password" not in masked
        assert masked == "postgresql+psycopg2://admin:****@localhost:5432/vidyora_ai"


def test_is_database_configured_detection():
    """Verifies detection of whether database credentials are configured."""
    with patch.dict(os.environ, {}, clear=True):
        custom_settings = Settings()
        assert custom_settings.is_database_configured is False

    with patch.dict(os.environ, {"DB_PASSWORD": "mypassword"}, clear=True):
        custom_settings = Settings()
        assert custom_settings.is_database_configured is True

    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://postgres:pass@localhost:5432/test"}, clear=True):
        custom_settings = Settings()
        assert custom_settings.is_database_configured is True
