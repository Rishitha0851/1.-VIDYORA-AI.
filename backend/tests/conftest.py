"""
VIDYORA AI - Global Test Configuration & Fixtures

Provides automatic authentication override for pre-existing legacy test suites
that do not supply Authorization headers, while preserving strict authentication
behavior for test_auth_and_isolation.py.
"""

import pytest
from fastapi import Depends
from sqlalchemy.orm import Session

from db.models import User
from db.session import get_db
from main import app
from services.auth_service import get_current_user


def mock_get_current_user(db: Session = Depends(get_db)) -> User:
    """
    FastAPI dependency override for legacy tests.
    Ensures that legacy_default_user_id exists in the active test database session
    so foreign key constraints on user_id are always satisfied.
    """
    user = db.query(User).filter(User.id == "legacy_default_user_id").first()
    if not user:
        user = User(
            id="legacy_default_user_id",
            email="legacy_tester@vidyora.ai",
            username="legacy_tester",
            full_name="Legacy Tester",
            hashed_password="hashed_pw_default_legacy",
            is_active=True,
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
        except Exception:
            db.rollback()
            user = db.query(User).filter(User.id == "legacy_default_user_id").first()
    return user


@pytest.fixture(autouse=True)
def override_auth_for_legacy_tests(request):
    """
    Automatically overrides get_current_user dependency for legacy tests,
    ensuring existing endpoint tests pass without having to rewrite headers
    across dozens of test files.
    """
    if (
        "test_auth_and_isolation" in request.node.fspath.basename
        or "test_rag_and_embeddings" in request.node.fspath.basename
        or "test_ask_vidyora_chat" in request.node.fspath.basename
        or "test_learning_recovery_workflow" in request.node.fspath.basename
    ):
        yield
        return

    app.dependency_overrides[get_current_user] = mock_get_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
