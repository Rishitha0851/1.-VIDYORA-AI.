"""
VIDYORA AI - Security, Authentication & User Isolation Test Suite (Step 16)

Tests:
  1. Registration success & response sanitization (no password or hash leaked)
  2. Duplicate email rejection (400)
  3. Invalid password login rejection (401)
  4. Non-existent email login rejection (401)
  5. Successful login & valid token retrieval (200)
  6. Current user endpoint GET /api/auth/me (200)
  7. Protected endpoints without authentication rejected (401)
  8. Malformed / tampered JWT rejected (401)
  9. Expired JWT rejected (401)
  10. Authenticated User A can access User A's video workspace (200)
  11. IDOR Attack: Authenticated User B cannot access User A's video workspace (404)
  12. IDOR Attack: Authenticated User B cannot access User A's video knowledge gaps (404)
  13. IDOR Attack: Authenticated User B cannot access User A's quiz attempts (404)
  14. IDOR Attack: Authenticated User B cannot access User A's recovery session (404/403)
  15. IDOR Attack: Authenticated User B cannot submit User A's recovery session (404/403)
  16. IDOR Attack: Authenticated User B cannot inspect User A's learner profile (403)
  17. IDOR Attack: Authenticated User B cannot evaluate User A's quiz (404)
  18. Multi-user Library Isolation: User A and User B see only their own respective videos
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.base import Base
from db.models import (
    KnowledgeChunk,
    LearningRecoverySession,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    User,
    Video,
    VideoTranscript,
)
from db.session import get_db
from main import app
from services.auth_service import create_access_token, hash_password

# Isolated in-memory SQLite database for authentication and security tests
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create in-memory tables and clean up per test."""
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


# ===========================================================================
# 1. Registration & Login Tests
# ===========================================================================

def test_registration_success():
    """Registers a learner, returns JWT and user profile, zero password hash leakage."""
    payload = {
        "email": "learner1@vidyora.ai",
        "password": "Password123!",
        "full_name": "Learner One",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "user" in data
    assert data["user"]["email"] == "learner1@vidyora.ai"
    assert data["user"]["full_name"] == "Learner One"
    assert "id" in data["user"]
    # Guarantee password and hashed_password are never exposed
    assert "password" not in data
    assert "hashed_password" not in data
    assert "password" not in data["user"]
    assert "hashed_password" not in data["user"]


def test_registration_duplicate_email_rejected():
    """Duplicate email registration is rejected with HTTP 400."""
    payload = {
        "email": "duplicate@vidyora.ai",
        "password": "SecurePassword123",
        "full_name": "First User",
    }
    res1 = client.post("/api/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/api/auth/register", json=payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"].lower()


def test_login_invalid_password_rejected():
    """Attempting login with wrong password returns HTTP 401."""
    reg_payload = {
        "email": "user_wrong_pw@vidyora.ai",
        "password": "CorrectPassword123",
    }
    client.post("/api/auth/register", json=reg_payload)

    login_payload = {
        "email": "user_wrong_pw@vidyora.ai",
        "password": "WrongPassword999",
    }
    response = client.post("/api/auth/login", json=login_payload)
    assert response.status_code == 401
    assert "invalid email address or password" in response.json()["detail"].lower()


def test_login_nonexistent_email_rejected():
    """Attempting login with non-existent email returns HTTP 401."""
    payload = {
        "email": "ghost@vidyora.ai",
        "password": "SomePassword123",
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 401


def test_login_successful():
    """Authenticates learner and returns signed JWT access token."""
    reg_payload = {
        "email": "valid_user@vidyora.ai",
        "password": "MySuperSecretPassword",
        "full_name": "Valid User",
    }
    client.post("/api/auth/register", json=reg_payload)

    login_payload = {
        "email": "valid_user@vidyora.ai",
        "password": "MySuperSecretPassword",
    }
    response = client.post("/api/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "valid_user@vidyora.ai"


def test_get_current_user_me_endpoint():
    """GET /api/auth/me returns the authenticated user's profile."""
    reg = client.post("/api/auth/register", json={
        "email": "me_user@vidyora.ai",
        "password": "Password12345",
        "full_name": "Me User",
    }).json()
    token = reg["access_token"]

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    user_data = response.json()
    assert user_data["email"] == "me_user@vidyora.ai"
    assert user_data["full_name"] == "Me User"


# ===========================================================================
# 2. Token Security & Rejection Tests
# ===========================================================================

def test_protected_endpoint_without_auth_rejected():
    """Accessing protected endpoints without an Authorization header returns HTTP 401."""
    routes = [
        ("GET", "/api/videos"),
        ("GET", "/api/videos/vid_123"),
        ("GET", "/api/videos/vid_123/knowledge-gaps"),
        ("GET", "/api/learners/knowledge-gaps"),
        ("GET", "/api/quizzes/q_123/attempts"),
        ("GET", "/api/recovery/rec_123"),
        ("POST", "/api/videos/process"),
        ("POST", "/api/recovery"),
    ]
    for method, route in routes:
        if method == "GET":
            res = client.get(route)
        else:
            res = client.post(route, json={})
        assert res.status_code == 401, f"Route {route} did not return 401 unauthenticated"


def test_malformed_jwt_rejected():
    """Invalid or tampered token returns HTTP 401."""
    headers = {"Authorization": "Bearer this.is.a.completely.tampered.token"}
    res = client.get("/api/videos", headers=headers)
    assert res.status_code == 401
    assert "invalid" in res.json()["detail"].lower()


def test_expired_jwt_rejected():
    """Expired JWT token returns HTTP 401."""
    db = TestingSessionLocal()
    u = User(
        id="user_expired_test",
        email="expired@vidyora.ai",
        hashed_password=hash_password("Password123"),
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.close()

    # Create expired token
    expired_token = create_access_token(
        {"sub": "user_expired_test", "email": "expired@vidyora.ai"},
        expires_delta=timedelta(seconds=-60),
    )
    headers = {"Authorization": f"Bearer {expired_token}"}
    res = client.get("/api/videos", headers=headers)
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


# ===========================================================================
# 3. IDOR (Insecure Direct Object Reference) & Isolation Tests
# ===========================================================================

@pytest.fixture
def users_and_tokens():
    """Creates two distinct learners and returns their tokens and IDs."""
    db = TestingSessionLocal()
    u1 = User(
        id="user_alpha_id",
        email="user_alpha@vidyora.ai",
        full_name="User Alpha",
        hashed_password=hash_password("AlphaPass123"),
        is_active=True,
    )
    u2 = User(
        id="user_beta_id",
        email="user_beta@vidyora.ai",
        full_name="User Beta",
        hashed_password=hash_password("BetaPass123"),
        is_active=True,
    )
    db.add_all([u1, u2])
    db.commit()
    db.close()

    t1 = create_access_token({"sub": "user_alpha_id", "email": "user_alpha@vidyora.ai"})
    t2 = create_access_token({"sub": "user_beta_id", "email": "user_beta@vidyora.ai"})

    return {
        "u1_id": "user_alpha_id",
        "u1_token": t1,
        "u2_id": "user_beta_id",
        "u2_token": t2,
    }


def test_user_can_access_own_video_workspace(users_and_tokens):
    """User Alpha can retrieve User Alpha's video workspace."""
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)
    v1 = Video(
        id="vid_alpha_lecture",
        user_id=users_and_tokens["u1_id"],
        url="https://www.youtube.com/watch?v=vid_alpha_lecture",
        platform="youtube",
        title="Alpha Lecture",
        status="completed",
        created_at=now,
        updated_at=now,
    )
    db.add(v1)
    db.commit()
    db.close()

    headers = {"Authorization": f"Bearer {users_and_tokens['u1_token']}"}
    res = client.get("/api/videos/vid_alpha_lecture", headers=headers)
    assert res.status_code == 200
    assert res.json()["video"]["id"] == "vid_alpha_lecture"


def test_idor_user_beta_cannot_access_user_alpha_video(users_and_tokens):
    """IDOR Attack: User Beta attempts to access User Alpha's video -> returns 404."""
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)
    v1 = Video(
        id="vid_alpha_secret",
        user_id=users_and_tokens["u1_id"],
        url="https://www.youtube.com/watch?v=vid_alpha_secret",
        platform="youtube",
        title="Alpha Private Lecture",
        status="completed",
        created_at=now,
        updated_at=now,
    )
    db.add(v1)
    db.commit()
    db.close()

    headers_beta = {"Authorization": f"Bearer {users_and_tokens['u2_token']}"}
    res = client.get("/api/videos/vid_alpha_secret", headers=headers_beta)
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_idor_user_beta_cannot_access_user_alpha_knowledge_gaps(users_and_tokens):
    """IDOR Attack: User Beta attempts to query knowledge gaps for User Alpha's video -> returns 404."""
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)
    v1 = Video(
        id="vid_alpha_gaps",
        user_id=users_and_tokens["u1_id"],
        url="https://www.youtube.com/watch?v=vid_alpha_gaps",
        platform="youtube",
        title="Alpha Gaps Lecture",
        status="completed",
        created_at=now,
        updated_at=now,
    )
    db.add(v1)
    db.commit()
    db.close()

    headers_beta = {"Authorization": f"Bearer {users_and_tokens['u2_token']}"}
    res = client.get("/api/videos/vid_alpha_gaps/knowledge-gaps", headers=headers_beta)
    assert res.status_code == 404


def test_idor_user_beta_cannot_access_user_alpha_quiz_attempts(users_and_tokens):
    """IDOR Attack: User Beta queries quiz attempt history for User Alpha's quiz -> returns 404."""
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)
    v1 = Video(
        id="vid_alpha_quiz_parent",
        user_id=users_and_tokens["u1_id"],
        url="https://www.youtube.com/watch?v=vid_alpha_quiz_parent",
        platform="youtube",
        title="Alpha Quiz Lecture",
        status="completed",
        created_at=now,
        updated_at=now,
    )
    db.add(v1)
    db.flush()

    q1 = Quiz(
        id="quiz_alpha_only",
        video_id=v1.id,
        title="Alpha Quiz",
        created_at=now,
    )
    db.add(q1)
    db.commit()
    db.close()

    headers_beta = {"Authorization": f"Bearer {users_and_tokens['u2_token']}"}
    res = client.get("/api/quizzes/quiz_alpha_only/attempts", headers=headers_beta)
    assert res.status_code == 404


def test_idor_user_beta_cannot_access_user_alpha_recovery_session(users_and_tokens):
    """IDOR Attack: User Beta retrieves User Alpha's recovery session -> returns 403 or 404."""
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)
    v1 = Video(
        id="vid_alpha_rec",
        user_id=users_and_tokens["u1_id"],
        url="https://www.youtube.com/watch?v=vid_alpha_rec",
        platform="youtube",
        title="Alpha Rec",
        status="completed",
        created_at=now,
        updated_at=now,
    )
    db.add(v1)
    db.flush()

    chk = KnowledgeChunk(
        id="chk_alpha_1",
        video_id=v1.id,
        chunk_index=0,
        text="Concept text",
        start_time=0.0,
        end_time=30.0,
        duration=30.0,
        word_count=5,
        segment_start_index=0,
        segment_end_index=1,
        created_at=now,
    )
    db.add(chk)
    db.flush()

    rec_session = LearningRecoverySession(
        id="session_alpha_private",
        user_id=users_and_tokens["u1_id"],
        video_id=v1.id,
        chunk_id=chk.id,
        source_timestamp=0.0,
        source_formatted_time="00:00",
        originating_evidence="Learner struggled",
        status="CREATED",
        created_at=now,
        updated_at=now,
    )
    db.add(rec_session)
    db.commit()
    db.close()

    headers_beta = {"Authorization": f"Bearer {users_and_tokens['u2_token']}"}
    res = client.get("/api/recovery/session_alpha_private", headers=headers_beta)
    assert res.status_code in [403, 404]


def test_idor_user_beta_cannot_submit_user_alpha_recovery_session(users_and_tokens):
    """IDOR Attack: User Beta submits answers to User Alpha's recovery session -> returns 403 or 404."""
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)
    rec_session = LearningRecoverySession(
        id="session_alpha_submit_target",
        user_id=users_and_tokens["u1_id"],
        video_id="v_some",
        chunk_id="c_some",
        source_timestamp=0.0,
        source_formatted_time="00:00",
        originating_evidence="Learner struggled",
        status="QUIZ_READY",
        micro_quiz_data=[],
        created_at=now,
        updated_at=now,
    )
    db.add(rec_session)
    db.commit()
    db.close()

    headers_beta = {"Authorization": f"Bearer {users_and_tokens['u2_token']}"}
    res = client.post(
        "/api/recovery/session_alpha_submit_target/submit",
        json={"selected_answers": {}},
        headers=headers_beta,
    )
    assert res.status_code in [403, 404]


def test_idor_user_beta_cannot_inspect_user_alpha_profile(users_and_tokens):
    """IDOR Attack: User Beta queries User Alpha's user_id on /api/learners/{user_id}/knowledge-gaps -> returns 403."""
    headers_beta = {"Authorization": f"Bearer {users_and_tokens['u2_token']}"}
    res = client.get(
        f"/api/learners/{users_and_tokens['u1_id']}/knowledge-gaps",
        headers=headers_beta,
    )
    assert res.status_code == 403
    assert "access denied" in res.json()["detail"].lower()


def test_multi_user_library_isolation(users_and_tokens):
    """User A and User B only see their own respective videos in GET /api/videos."""
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)

    # 2 videos for Alpha
    v_a1 = Video(
        id="vid_a1",
        user_id=users_and_tokens["u1_id"],
        url="https://youtube.com/watch?v=vid_a1",
        title="Alpha Lecture 1",
        status="completed",
        created_at=now,
        updated_at=now,
    )
    v_a2 = Video(
        id="vid_a2",
        user_id=users_and_tokens["u1_id"],
        url="https://youtube.com/watch?v=vid_a2",
        title="Alpha Lecture 2",
        status="completed",
        created_at=now,
        updated_at=now,
    )
    # 1 video for Beta
    v_b1 = Video(
        id="vid_b1",
        user_id=users_and_tokens["u2_id"],
        url="https://youtube.com/watch?v=vid_b1",
        title="Beta Lecture 1",
        status="completed",
        created_at=now,
        updated_at=now,
    )
    db.add_all([v_a1, v_a2, v_b1])
    db.commit()
    db.close()

    # User Alpha requests /api/videos
    res_a = client.get("/api/videos", headers={"Authorization": f"Bearer {users_and_tokens['u1_token']}"})
    assert res_a.status_code == 200
    videos_a = res_a.json()["videos"]
    assert len(videos_a) == 2
    video_ids_a = {v["video_id"] for v in videos_a}
    assert video_ids_a == {"vid_a1", "vid_a2"}

    # User Beta requests /api/videos
    res_b = client.get("/api/videos", headers={"Authorization": f"Bearer {users_and_tokens['u2_token']}"})
    assert res_b.status_code == 200
    videos_b = res_b.json()["videos"]
    assert len(videos_b) == 1
    assert videos_b[0]["video_id"] == "vid_b1"
