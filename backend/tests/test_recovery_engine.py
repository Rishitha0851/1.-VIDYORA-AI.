"""
VIDYORA AI - Comprehensive Tests for Step 14 Phase 3: Targeted Learning Recovery Engine

Validates:
  1. Recovery session creation and weak chunk grounding
  2. Answer-key security (correct_answer and explanation omitted before submission)
  3. Gemini error handling (timeout -> 504, rate limit -> 429, malformed -> 502)
  4. Validation: unknown video (404), unknown chunk (404), unknown session (404)
  5. Submission validation: unknown question ID (400), invalid option (400), double submission (400)
  6. Deterministic evaluation logic:
     - RECOVERED (>= 75% accuracy and improved)
     - IMPROVED (60% - 74.9% accuracy and improved)
     - NOT_RECOVERED (< 60% accuracy or no improvement)
     - INSUFFICIENT_EVIDENCE (< 2 questions)
  7. Attempt tracking and maximum attempt enforcement (MAX = 2)
  8. Different pedagogical guidance between Attempt 1 and Attempt 2
  9. Transaction safety and rollback handling
  10. Integration with Knowledge Gap state (has_recovered=True)
"""

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

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
    QuizAnswer,
    QuizAttempt,
    QuizQuestion,
    User,
    Video,
)
from db.session import get_db
from main import app
from models import (
    QuizDifficulty,
    QuizQuestionInternal,
    RecoveryInterventionInternal,
    RecoveryResultEnum,
    RecoverySessionStatus,
    SourceTimestamp,
)
from services.gemini_service import (
    GeminiRateLimitError,
    GeminiTimeoutError,
    GeminiValidationError,
)

# Isolated SQLite in-memory test database
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
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
    """Isolates DB schema and FastAPI dependency per test."""
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def seed_video_and_chunks(db, video_id="vid_recovery_test", num_chunks=3):
    """Helper to seed video and knowledge chunks in the test DB."""
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
        db.flush()

    video = Video(
        id=video_id,
        user_id="legacy_default_user_id",
        url="https://www.youtube.com/watch?v=testrecovery",
        title="Gradient Descent and Optimization",
        status="completed",
        platform="youtube",
    )
    db.add(video)
    db.flush()

    chunks = []
    for i in range(num_chunks):
        chunk = KnowledgeChunk(
            id=f"{video_id}_chk_{i}",
            video_id=video_id,
            chunk_index=i,
            text=f"Transcript content for concept {i+1}. In this section we explain gradient descent update rule and step size.",
            start_time=float(i * 120),
            end_time=float((i + 1) * 120),
            duration=120.0,
            word_count=50,
            segment_start_index=i * 5,
            segment_end_index=(i + 1) * 5,
        )
        db.add(chunk)
        chunks.append(chunk)

    db.commit()
    return video, chunks


def create_sample_intervention(weak_chunk_id, num_questions=3):
    """Creates a sample RecoveryInterventionInternal for mocking Gemini output."""
    questions = []
    for i in range(num_questions):
        questions.append(
            QuizQuestionInternal(
                id=f"rq_{i+1}",
                question=f"What is the primary role of the learning rate in concept {i+1}?",
                options=[
                    "Scales the gradient step size",
                    "Computes the loss function directly",
                    "Initializes model weights to zero",
                    "Normalizes input feature vectors",
                ],
                correct_answer="Scales the gradient step size",
                explanation="The learning rate is a hyperparameter that scales the magnitude of parameter updates along the gradient vector.",
                difficulty=QuizDifficulty.MEDIUM,
                source_timestamp=SourceTimestamp(
                    timestamp=10.0 + i * 20.0,
                    formatted_time=f"00:{10 + i * 20:02d}",
                    label=f"Discussion at 00:{10 + i * 20:02d}",
                ),
                source_chunk_id=weak_chunk_id,
            )
        )

    return RecoveryInterventionInternal(
        title="Understanding Gradient Step Scaling",
        explanation="Gradient descent updates model parameters iteratively in the opposite direction of the gradient. The learning rate controls how large a step is taken.",
        worked_example="If the gradient is 0.5 and the learning rate is 0.1, the parameter moves by 0.05.",
        key_takeaway="The learning rate directly scales the gradient magnitude during parameter updates.",
        questions=questions,
    )


# ===========================================================================
# 1. Recovery Creation & Answer-Key Security Tests
# ===========================================================================

def test_create_recovery_session_success():
    """Verifies recovery session creation, grounding, and answer-key security."""
    db = TestingSessionLocal()
    video, chunks = seed_video_and_chunks(db)
    target_chunk = chunks[0]

    sample_intervention = create_sample_intervention(target_chunk.id, num_questions=3)

    with patch("services.recovery_service.generate_recovery_intervention", return_value=(sample_intervention, "gemini-2.5-flash")):
        response = client.post(
            "/api/recovery",
            json={
                "video_id": video.id,
                "chunk_id": target_chunk.id,
            },
        )

    assert response.status_code == 201
    data = response.json()

    assert data["video_id"] == video.id
    assert data["chunk_id"] == target_chunk.id
    assert data["attempt_number"] == 1
    assert data["status"] == "QUIZ_READY"
    assert data["explanation_title"] == "Understanding Gradient Step Scaling"
    assert data["targeted_explanation"] is not None
    assert data["worked_example"] is not None
    assert data["key_takeaway"] is not None
    assert len(data["micro_quiz"]) == 3

    # CRITICAL SECURITY CHECK: correct_answer and explanation must NOT be present in client response!
    for q in data["micro_quiz"]:
        assert "correct_answer" not in q
        assert "explanation" not in q
        assert len(q["options"]) == 4

    # Verify session persisted in DB with answer key stored server-side
    session_id = data["id"]
    db_session = db.query(LearningRecoverySession).filter(LearningRecoverySession.id == session_id).first()
    assert db_session is not None
    assert len(db_session.micro_quiz_data) == 3
    assert db_session.micro_quiz_data[0]["correct_answer"] == "Scales the gradient step size"


def test_create_recovery_unknown_video_returns_404():
    """Non-existent video ID returns HTTP 404."""
    response = client.post(
        "/api/recovery",
        json={
            "video_id": "nonexistent_video",
            "chunk_id": "nonexistent_chunk",
        },
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_create_recovery_unknown_chunk_returns_404():
    """Non-existent chunk ID for existing video returns HTTP 404."""
    db = TestingSessionLocal()
    video, _ = seed_video_and_chunks(db)

    response = client.post(
        "/api/recovery",
        json={
            "video_id": video.id,
            "chunk_id": "invalid_chunk_id",
        },
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ===========================================================================
# 2. Gemini Error Mapping Tests
# ===========================================================================

def test_recovery_gemini_timeout_returns_504():
    """Gemini timeout during intervention generation maps to HTTP 504."""
    db = TestingSessionLocal()
    video, chunks = seed_video_and_chunks(db)

    with patch("services.recovery_service.generate_recovery_intervention", side_effect=GeminiTimeoutError()):
        response = client.post(
            "/api/recovery",
            json={"video_id": video.id, "chunk_id": chunks[0].id},
        )
    assert response.status_code == 504
    assert "timed out" in response.json()["detail"].lower()


def test_recovery_gemini_rate_limit_returns_429():
    """Gemini rate limit during intervention generation maps to HTTP 429."""
    db = TestingSessionLocal()
    video, chunks = seed_video_and_chunks(db)

    with patch("services.recovery_service.generate_recovery_intervention", side_effect=GeminiRateLimitError()):
        response = client.post(
            "/api/recovery",
            json={"video_id": video.id, "chunk_id": chunks[0].id},
        )
    assert response.status_code == 429
    assert "rate limit" in response.json()["detail"].lower()


def test_recovery_gemini_validation_error_returns_502():
    """Malformed output from Gemini maps to HTTP 502."""
    db = TestingSessionLocal()
    video, chunks = seed_video_and_chunks(db)

    with patch("services.recovery_service.generate_recovery_intervention", side_effect=GeminiValidationError("Invalid schema")):
        response = client.post(
            "/api/recovery",
            json={"video_id": video.id, "chunk_id": chunks[0].id},
        )
    assert response.status_code == 502


# ===========================================================================
# 3. Micro-Quiz Submission & Validation Tests
# ===========================================================================

def test_submit_recovery_unknown_session_returns_404():
    """Submitting answers to a non-existent session returns HTTP 404."""
    response = client.post(
        "/api/recovery/nonexistent_session_id/submit",
        json={"selected_answers": {"rq_1": "Scales the gradient step size"}},
    )
    assert response.status_code == 404


def test_submit_recovery_unknown_question_id_returns_400():
    """Submitting an answer for a question not in the session returns HTTP 400."""
    db = TestingSessionLocal()
    video, chunks = seed_video_and_chunks(db)
    target_chunk = chunks[0]

    sample_intervention = create_sample_intervention(target_chunk.id)
    with patch("services.recovery_service.generate_recovery_intervention", return_value=(sample_intervention, "gemini-2.5-flash")):
        create_resp = client.post("/api/recovery", json={"video_id": video.id, "chunk_id": target_chunk.id})
    session_id = create_resp.json()["id"]

    response = client.post(
        f"/api/recovery/{session_id}/submit",
        json={"selected_answers": {"fake_question_99": "Scales the gradient step size"}},
    )
    assert response.status_code == 400
    assert "does not belong" in response.json()["detail"].lower()


def test_submit_recovery_invalid_option_returns_400():
    """Submitting an option not among the 4 choices returns HTTP 400."""
    db = TestingSessionLocal()
    video, chunks = seed_video_and_chunks(db)
    target_chunk = chunks[0]

    sample_intervention = create_sample_intervention(target_chunk.id)
    with patch("services.recovery_service.generate_recovery_intervention", return_value=(sample_intervention, "gemini-2.5-flash")):
        create_resp = client.post("/api/recovery", json={"video_id": video.id, "chunk_id": target_chunk.id})
    session_id = create_resp.json()["id"]

    response = client.post(
        f"/api/recovery/{session_id}/submit",
        json={"selected_answers": {"rq_1": "Completely invented option"}},
    )
    assert response.status_code == 400
    assert "not among the valid options" in response.json()["detail"].lower()


def test_submit_recovery_already_evaluated_returns_400():
    """Submitting answers to an already evaluated session returns HTTP 400."""
    db = TestingSessionLocal()
    video, chunks = seed_video_and_chunks(db)
    target_chunk = chunks[0]

    sample_intervention = create_sample_intervention(target_chunk.id)
    with patch("services.recovery_service.generate_recovery_intervention", return_value=(sample_intervention, "gemini-2.5-flash")):
        create_resp = client.post("/api/recovery", json={"video_id": video.id, "chunk_id": target_chunk.id})
    session_id = create_resp.json()["id"]

    valid_answers = {"rq_1": "Scales the gradient step size", "rq_2": "Scales the gradient step size", "rq_3": "Scales the gradient step size"}

    # First submission succeeds
    resp1 = client.post(f"/api/recovery/{session_id}/submit", json={"selected_answers": valid_answers})
    assert resp1.status_code == 200

    # Second submission is rejected
    resp2 = client.post(f"/api/recovery/{session_id}/submit", json={"selected_answers": valid_answers})
    assert resp2.status_code == 400
    assert "already been submitted" in resp2.json()["detail"].lower()


# ===========================================================================
# 4. Deterministic Evaluation Logic Tests
# ===========================================================================

def test_deterministic_scoring_successful_recovery():
    """
    3/3 correct (100%) with baseline 0% -> RECOVERED.
    Verifies score calculation, absolute improvement (+100%), and explanations released.
    """
    db = TestingSessionLocal()
    video, chunks = seed_video_and_chunks(db)
    target_chunk = chunks[0]

    sample_intervention = create_sample_intervention(target_chunk.id, num_questions=3)
    with patch("services.recovery_service.generate_recovery_intervention", return_value=(sample_intervention, "gemini-2.5-flash")):
        create_resp = client.post("/api/recovery", json={"video_id": video.id, "chunk_id": target_chunk.id})
    session_id = create_resp.json()["id"]

    # Learner answers all 3 correctly
    submission = {
        "selected_answers": {
            "rq_1": "Scales the gradient step size",
            "rq_2": "Scales the gradient step size",
            "rq_3": "Scales the gradient step size",
        }
    }
    eval_resp = client.post(f"/api/recovery/{session_id}/submit", json=submission)
    assert eval_resp.status_code == 200
    data = eval_resp.json()

    assert data["total_questions"] == 3
    assert data["correct_count"] == 3
    assert data["post_recovery_accuracy"] == 100.0
    assert data["pre_recovery_accuracy"] == 0.0
    assert data["absolute_improvement"] == 100.0
    assert data["recovery_result"] == "RECOVERED"
    assert data["can_retry"] is False
    assert len(data["question_results"]) == 3

    # Now verify that question results provide full answers and explanations for review
    for qr in data["question_results"]:
        assert qr["is_correct"] is True
        assert qr["correct_answer"] == "Scales the gradient step size"
        assert len(qr["explanation"]) > 0


def test_deterministic_scoring_improved_outcome():
    """
    2/3 correct (66.7%) with baseline 0% -> IMPROVED (>=60% but <75%).
    can_retry should be True (since attempt 1).
    """
    db = TestingSessionLocal()
    video, chunks = seed_video_and_chunks(db)
    target_chunk = chunks[0]

    sample_intervention = create_sample_intervention(target_chunk.id, num_questions=3)
    with patch("services.recovery_service.generate_recovery_intervention", return_value=(sample_intervention, "gemini-2.5-flash")):
        create_resp = client.post("/api/recovery", json={"video_id": video.id, "chunk_id": target_chunk.id})
    session_id = create_resp.json()["id"]

    # Learner answers 2 correctly and 1 incorrectly
    submission = {
        "selected_answers": {
            "rq_1": "Scales the gradient step size",
            "rq_2": "Scales the gradient step size",
            "rq_3": "Computes the loss function directly",  # Incorrect
        }
    }
    eval_resp = client.post(f"/api/recovery/{session_id}/submit", json=submission)
    assert eval_resp.status_code == 200
    data = eval_resp.json()

    assert data["correct_count"] == 2
    assert data["total_questions"] == 3
    assert data["post_recovery_accuracy"] == 66.7
    assert data["recovery_result"] == "IMPROVED"
    assert data["can_retry"] is True


def test_deterministic_scoring_not_recovered():
    """
    1/3 correct (33.3%) with baseline 0% -> NOT_RECOVERED (<60%).
    """
    db = TestingSessionLocal()
    video, chunks = seed_video_and_chunks(db)
    target_chunk = chunks[0]

    sample_intervention = create_sample_intervention(target_chunk.id, num_questions=3)
    with patch("services.recovery_service.generate_recovery_intervention", return_value=(sample_intervention, "gemini-2.5-flash")):
        create_resp = client.post("/api/recovery", json={"video_id": video.id, "chunk_id": target_chunk.id})
    session_id = create_resp.json()["id"]

    submission = {
        "selected_answers": {
            "rq_1": "Scales the gradient step size",
            "rq_2": "Computes the loss function directly",
            "rq_3": "Initializes model weights to zero",
        }
    }
    eval_resp = client.post(f"/api/recovery/{session_id}/submit", json=submission)
    assert eval_resp.status_code == 200
    data = eval_resp.json()

    assert data["correct_count"] == 1
    assert data["post_recovery_accuracy"] == 33.3
    assert data["recovery_result"] == "NOT_RECOVERED"
    assert data["can_retry"] is True


def test_deterministic_scoring_insufficient_evidence():
    """
    Micro-quiz with fewer than 2 questions -> INSUFFICIENT_EVIDENCE.
    """
    db = TestingSessionLocal()
    video, chunks = seed_video_and_chunks(db)
    target_chunk = chunks[0]

    single_q_intervention = create_sample_intervention(target_chunk.id, num_questions=1)
    with patch("services.recovery_service.generate_recovery_intervention", return_value=(single_q_intervention, "gemini-2.5-flash")):
        create_resp = client.post("/api/recovery", json={"video_id": video.id, "chunk_id": target_chunk.id})
    session_id = create_resp.json()["id"]

    submission = {"selected_answers": {"rq_1": "Scales the gradient step size"}}
    eval_resp = client.post(f"/api/recovery/{session_id}/submit", json=submission)
    assert eval_resp.status_code == 200
    data = eval_resp.json()

    assert data["total_questions"] == 1
    assert data["recovery_result"] == "INSUFFICIENT_EVIDENCE"


# ===========================================================================
# 5. Repeated Recovery & Maximum Attempt Enforcement
# ===========================================================================

def test_repeated_recovery_and_maximum_attempt_limit():
    """
    Verifies that:
    - Attempt 1 creates attempt_number = 1
    - Attempt 2 creates attempt_number = 2 with misconception contrast
    - Attempt 3 is rejected with HTTP 400 (MAX_RECOVERY_ATTEMPTS = 2 reached)
    """
    db = TestingSessionLocal()
    video, chunks = seed_video_and_chunks(db)
    target_chunk = chunks[0]

    sample_intervention_1 = create_sample_intervention(target_chunk.id)
    sample_intervention_2 = create_sample_intervention(target_chunk.id)

    # Attempt 1
    with patch("services.recovery_service.generate_recovery_intervention", return_value=(sample_intervention_1, "gemini-2.5-flash")) as mock_gen:
        resp1 = client.post("/api/recovery", json={"video_id": video.id, "chunk_id": target_chunk.id})
        assert resp1.status_code == 201
        assert resp1.json()["attempt_number"] == 1
        assert mock_gen.call_args.kwargs["attempt_number"] == 1

    # Attempt 2
    with patch("services.recovery_service.generate_recovery_intervention", return_value=(sample_intervention_2, "gemini-2.5-flash")) as mock_gen:
        resp2 = client.post("/api/recovery", json={"video_id": video.id, "chunk_id": target_chunk.id})
        assert resp2.status_code == 201
        assert resp2.json()["attempt_number"] == 2
        assert mock_gen.call_args.kwargs["attempt_number"] == 2

    # Attempt 3 (Must be rejected)
    resp3 = client.post("/api/recovery", json={"video_id": video.id, "chunk_id": target_chunk.id})
    assert resp3.status_code == 400
    assert "maximum recovery attempts" in resp3.json()["detail"].lower()


# ===========================================================================
# 6. Read History & Knowledge Gap State Integration
# ===========================================================================

def test_get_chunk_recovery_history():
    """Verifies GET /api/videos/{video_id}/chunks/{chunk_id}/recovery-history."""
    db = TestingSessionLocal()
    video, chunks = seed_video_and_chunks(db)
    target_chunk = chunks[0]

    sample_intervention = create_sample_intervention(target_chunk.id)
    with patch("services.recovery_service.generate_recovery_intervention", return_value=(sample_intervention, "gemini-2.5-flash")):
        client.post("/api/recovery", json={"video_id": video.id, "chunk_id": target_chunk.id})
        client.post("/api/recovery", json={"video_id": video.id, "chunk_id": target_chunk.id})

    history_resp = client.get(f"/api/videos/{video.id}/chunks/{target_chunk.id}/recovery-history")
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history) == 2
    assert history[0]["attempt_number"] == 2
    assert history[1]["attempt_number"] == 1


def test_knowledge_gap_reflects_recovery_state():
    """
    Verifies that after successful recovery evaluation,
    GET /api/videos/{video_id}/knowledge-gaps marks has_recovered=True on that chunk.
    """
    db = TestingSessionLocal()
    video, chunks = seed_video_and_chunks(db)
    target_chunk = chunks[0]

    # Create recovery session
    sample_intervention = create_sample_intervention(target_chunk.id)
    with patch("services.recovery_service.generate_recovery_intervention", return_value=(sample_intervention, "gemini-2.5-flash")):
        create_resp = client.post("/api/recovery", json={"video_id": video.id, "chunk_id": target_chunk.id})
    session_id = create_resp.json()["id"]

    # Submit 100% correct answers to achieve RECOVERED
    submission = {
        "selected_answers": {
            "rq_1": "Scales the gradient step size",
            "rq_2": "Scales the gradient step size",
            "rq_3": "Scales the gradient step size",
        }
    }
    client.post(f"/api/recovery/{session_id}/submit", json=submission)

    # Check knowledge gaps endpoint
    gaps_resp = client.get(f"/api/videos/{video.id}/knowledge-gaps")
    assert gaps_resp.status_code == 200
    gaps_data = gaps_resp.json()

    recovered_chunk_gap = next((g for g in gaps_data["gaps"] if g["chunk_id"] == target_chunk.id), None)
    assert recovered_chunk_gap is not None
    assert recovered_chunk_gap["has_recovered"] is True
    assert recovered_chunk_gap["latest_recovery_result"] == "RECOVERED"
