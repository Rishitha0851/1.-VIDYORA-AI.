"""
VIDYORA AI - Tests for Step 14 Phase 1: Deterministic Learner Knowledge Gap Engine

Validates:
  1. Chunk-level metrics calculation
  2. Explainable classification heuristics (STRONG, DEVELOPING, WEAK, INSUFFICIENT_DATA)
  3. Longitudinal trend derivation (IMPROVING, STABLE, DECLINING, INSUFFICIENT_DATA)
  4. Video-specific knowledge gap endpoint (GET /api/videos/{video_id}/knowledge-gaps)
  5. Cross-video learner profile endpoint (GET /api/learners/knowledge-gaps)
  6. 404 handling for unknown videos
  7. Absolute zero LLM/Gemini dependencies
  8. Chronological ordering integrity across multiple quizzes and attempts
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.base import Base
from db.models import (
    KnowledgeChunk,
    Quiz,
    QuizAnswer,
    QuizAttempt,
    QuizQuestion,
    User,
    Video,
)
from db.session import get_db
from main import app
from models import KnowledgeGapClassification, PerformanceTrend
from services.knowledge_gap_service import KnowledgeGapService

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


# ===========================================================================
# 1. Pure Unit Tests: Deterministic Metrics, Classification & Trends
# ===========================================================================

def test_chunk_metrics_no_attempts():
    """No observations yields 0 accuracy and insufficient data flags."""
    metrics = KnowledgeGapService.compute_chunk_metrics([])
    assert metrics["total_observations"] == 0
    assert metrics["accuracy"] == 0.0
    assert metrics["most_recent_result"] is None

    classification, reason = KnowledgeGapService.classify_chunk(metrics)
    assert classification == KnowledgeGapClassification.INSUFFICIENT_DATA
    assert "No quiz questions answered" in reason

    trend, trend_reason = KnowledgeGapService.compute_trend([])
    assert trend == PerformanceTrend.INSUFFICIENT_DATA


def test_chunk_metrics_one_incorrect_attempt():
    """A single isolated error is classified as INSUFFICIENT_DATA rather than immediately WEAK."""
    obs = [{"is_correct": False, "attempt_id": "att_1", "created_at": datetime.now(timezone.utc)}]
    metrics = KnowledgeGapService.compute_chunk_metrics(obs)
    assert metrics["total_observations"] == 1
    assert metrics["correct_count"] == 0
    assert metrics["incorrect_count"] == 1
    assert metrics["accuracy"] == 0.0
    assert metrics["consecutive_incorrect_count"] == 1

    classification, reason = KnowledgeGapService.classify_chunk(metrics)
    assert classification == KnowledgeGapClassification.INSUFFICIENT_DATA
    assert "isolated mistake" in reason.lower()

    trend, _ = KnowledgeGapService.compute_trend(obs)
    assert trend == PerformanceTrend.INSUFFICIENT_DATA


def test_chunk_metrics_one_correct_attempt():
    """A single initial success is classified as INSUFFICIENT_DATA to prevent premature mastery claim."""
    obs = [{"is_correct": True, "attempt_id": "att_1", "created_at": datetime.now(timezone.utc)}]
    metrics = KnowledgeGapService.compute_chunk_metrics(obs)
    assert metrics["total_observations"] == 1
    assert metrics["accuracy"] == 1.0

    classification, reason = KnowledgeGapService.classify_chunk(metrics)
    assert classification == KnowledgeGapClassification.INSUFFICIENT_DATA
    assert "initial correct" in reason.lower()


def test_chunk_metrics_repeated_incorrect_attempts():
    """Two or more consecutive errors strictly trigger WEAK classification."""
    obs = [
        {"is_correct": False, "attempt_id": "att_1", "created_at": datetime.now(timezone.utc)},
        {"is_correct": False, "attempt_id": "att_2", "created_at": datetime.now(timezone.utc)},
    ]
    metrics = KnowledgeGapService.compute_chunk_metrics(obs)
    assert metrics["total_observations"] == 2
    assert metrics["accuracy"] == 0.0
    assert metrics["consecutive_incorrect_count"] == 2

    classification, reason = KnowledgeGapService.classify_chunk(metrics)
    assert classification == KnowledgeGapClassification.WEAK
    assert "consecutive errors" in reason.lower()

    trend, _ = KnowledgeGapService.compute_trend(obs)
    assert trend == PerformanceTrend.STABLE


def test_chunk_metrics_mixed_developing_attempts():
    """Mixed accuracy between 40% and 74% assigns DEVELOPING classification."""
    obs = [
        {"is_correct": True, "attempt_id": "att_1", "created_at": datetime.now(timezone.utc)},
        {"is_correct": False, "attempt_id": "att_2", "created_at": datetime.now(timezone.utc)},
        {"is_correct": True, "attempt_id": "att_3", "created_at": datetime.now(timezone.utc)},
        {"is_correct": False, "attempt_id": "att_4", "created_at": datetime.now(timezone.utc)},
    ]
    metrics = KnowledgeGapService.compute_chunk_metrics(obs)
    assert metrics["total_observations"] == 4
    assert metrics["accuracy"] == 0.50
    assert metrics["consecutive_incorrect_count"] == 1

    classification, reason = KnowledgeGapService.classify_chunk(metrics)
    assert classification == KnowledgeGapClassification.DEVELOPING
    assert "mixed performance" in reason.lower()


def test_chunk_metrics_previously_weak_recently_improved():
    """Struggled initially (False, False) then succeeded (True, True) yields IMPROVING trend."""
    obs = [
        {"is_correct": False, "attempt_id": "att_1", "created_at": datetime.now(timezone.utc)},
        {"is_correct": False, "attempt_id": "att_2", "created_at": datetime.now(timezone.utc)},
        {"is_correct": True, "attempt_id": "att_3", "created_at": datetime.now(timezone.utc)},
        {"is_correct": True, "attempt_id": "att_4", "created_at": datetime.now(timezone.utc)},
    ]
    metrics = KnowledgeGapService.compute_chunk_metrics(obs)
    assert metrics["accuracy"] == 0.50
    assert metrics["consecutive_incorrect_count"] == 0
    assert metrics["consecutive_correct_count"] == 2

    trend, reason = KnowledgeGapService.compute_trend(obs)
    assert trend == PerformanceTrend.IMPROVING
    assert "improved" in reason.lower()


def test_chunk_metrics_previously_strong_recently_declining():
    """Succeeded initially (True, True) then failed (False, False) yields DECLINING trend."""
    obs = [
        {"is_correct": True, "attempt_id": "att_1", "created_at": datetime.now(timezone.utc)},
        {"is_correct": True, "attempt_id": "att_2", "created_at": datetime.now(timezone.utc)},
        {"is_correct": False, "attempt_id": "att_3", "created_at": datetime.now(timezone.utc)},
        {"is_correct": False, "attempt_id": "att_4", "created_at": datetime.now(timezone.utc)},
    ]
    metrics = KnowledgeGapService.compute_chunk_metrics(obs)
    assert metrics["accuracy"] == 0.50
    assert metrics["consecutive_incorrect_count"] == 2

    # Because last 2 were incorrect, classification recognizes recent repeated mistake
    classification, _ = KnowledgeGapService.classify_chunk(metrics)
    assert classification == KnowledgeGapClassification.WEAK

    trend, reason = KnowledgeGapService.compute_trend(obs)
    assert trend == PerformanceTrend.DECLINING
    assert "declined" in reason.lower()


def test_chunk_metrics_strong_mastery():
    """Consistent high accuracy (3/3 or 4/4) yields STRONG classification."""
    obs = [
        {"is_correct": True, "attempt_id": "att_1", "created_at": datetime.now(timezone.utc)},
        {"is_correct": True, "attempt_id": "att_2", "created_at": datetime.now(timezone.utc)},
        {"is_correct": True, "attempt_id": "att_3", "created_at": datetime.now(timezone.utc)},
    ]
    metrics = KnowledgeGapService.compute_chunk_metrics(obs)
    assert metrics["accuracy"] == 1.0
    assert metrics["has_demonstrated_mastery"] is True

    classification, _ = KnowledgeGapService.classify_chunk(metrics)
    assert classification == KnowledgeGapClassification.STRONG

    trend, _ = KnowledgeGapService.compute_trend(obs)
    assert trend == PerformanceTrend.STABLE


def test_distinguish_unanswered_from_incorrect():
    """
    Skipped/unanswered questions (selected_answer=None, is_correct=False)
    must NOT be classified as WEAK misconceptions.
    """
    obs = [
        {
            "is_correct": False,
            "selected_answer": None,
            "is_unanswered": True,
            "attempt_id": "att_1",
            "created_at": datetime.now(timezone.utc),
        },
        {
            "is_correct": False,
            "selected_answer": None,
            "is_unanswered": True,
            "attempt_id": "att_2",
            "created_at": datetime.now(timezone.utc),
        },
    ]
    metrics = KnowledgeGapService.compute_chunk_metrics(obs)
    assert metrics["unanswered_count"] == 2
    assert metrics["incorrect_count"] == 0
    assert metrics["consecutive_incorrect_count"] == 0

    classification, reason = KnowledgeGapService.classify_chunk(metrics)
    assert classification == KnowledgeGapClassification.INSUFFICIENT_DATA
    assert "skipped without answering" in reason.lower()

    # If 1 is answered incorrectly and 1 is skipped:
    mixed_obs = [
        {
            "is_correct": False,
            "selected_answer": "Wrong Option",
            "is_unanswered": False,
            "attempt_id": "att_1",
            "created_at": datetime.now(timezone.utc),
        },
        {
            "is_correct": False,
            "selected_answer": None,
            "is_unanswered": True,
            "attempt_id": "att_2",
            "created_at": datetime.now(timezone.utc),
        },
    ]
    mixed_metrics = KnowledgeGapService.compute_chunk_metrics(mixed_obs)
    assert mixed_metrics["unanswered_count"] == 1
    assert mixed_metrics["incorrect_count"] == 1
    # Only 1 answered question with error -> isolated mistake, not WEAK
    classification_mixed, _ = KnowledgeGapService.classify_chunk(mixed_metrics)
    assert classification_mixed == KnowledgeGapClassification.INSUFFICIENT_DATA


def test_concept_name_and_action_derivation():
    """Verify deterministic concept title and recommended action derivations."""
    name1 = KnowledgeGapService.derive_concept_name(
        "So, in this part, we examine backpropagation through multilayer networks. Next topic...", 0
    )
    assert "backpropagation" in name1.lower()

    action_weak = KnowledgeGapService.derive_recommended_action(
        KnowledgeGapClassification.WEAK, has_recovered=False, unanswered_count=0
    )
    assert "recovery" in action_weak.lower()

    status_rec = KnowledgeGapService.derive_recovery_status(
        KnowledgeGapClassification.WEAK, latest_recovery_result="RECOVERED", has_recovered=True
    )
    assert status_rec == "improvement_demonstrated"


# ===========================================================================
# 2. Integration Tests: Database Persistence & API Endpoints
# ===========================================================================

def test_video_knowledge_gaps_not_found_returns_404():
    """GET /api/videos/{video_id}/knowledge-gaps returns 404 for unknown video ID."""
    response = client.get("/api/videos/nonexistent_vid/knowledge-gaps")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@patch("services.gemini_service.generate_quiz")
@patch("services.gemini_service.generate_video_summary")
def test_video_knowledge_gaps_multichunk_multiattempt_no_gemini(mock_summary, mock_quiz):
    """
    Verifies full database aggregation across multiple chunks, quizzes, and attempts:
    - Zero Gemini calls executed
    - Chronological order preserved
    - WEAK chunks prioritized in response
    """
    db = TestingSessionLocal()
    base_time = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)

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

    # 1. Setup Video
    vid = Video(
        id="vid_analytics_test",
        user_id="legacy_default_user_id",
        url="https://www.youtube.com/watch?v=vid_analytics_test",
        platform="youtube",
        title="Deep Learning Foundations",
        status="completed",
        created_at=base_time,
        updated_at=base_time,
    )
    db.add(vid)
    db.flush()

    # 2. Setup 3 Knowledge Chunks
    chk_weak = KnowledgeChunk(
        id="chk_weak_001",
        video_id=vid.id,
        chunk_index=0,
        text="Backpropagation calculates gradients via the chain rule.",
        start_time=10.0,
        end_time=40.0,
        duration=30.0,
        word_count=7,
        segment_start_index=0,
        segment_end_index=2,
        created_at=base_time,
    )
    chk_strong = KnowledgeChunk(
        id="chk_strong_002",
        video_id=vid.id,
        chunk_index=1,
        text="Activation functions introduce non-linearity.",
        start_time=45.0,
        end_time=75.0,
        duration=30.0,
        word_count=5,
        segment_start_index=3,
        segment_end_index=5,
        created_at=base_time,
    )
    chk_unassessed = KnowledgeChunk(
        id="chk_unassessed_003",
        video_id=vid.id,
        chunk_index=2,
        text="Convolutional layers capture local spatial features.",
        start_time=80.0,
        end_time=110.0,
        duration=30.0,
        word_count=6,
        segment_start_index=6,
        segment_end_index=8,
        created_at=base_time,
    )
    db.add_all([chk_weak, chk_strong, chk_unassessed])
    db.flush()

    # 3. Setup Quiz 1 & Questions
    quiz1 = Quiz(
        id="quiz_part1",
        video_id=vid.id,
        title="Part 1 Assessment",
        created_at=base_time,
    )
    db.add(quiz1)
    db.flush()

    q_backprop1 = QuizQuestion(
        id=f"{quiz1.id}_q1",
        quiz_id=quiz1.id,
        source_chunk_id=chk_weak.id,
        question_order=1,
        question_text="What does backprop compute?",
        options=["Gradients", "Images", "Audio", "Labels"],
        correct_answer="Gradients",
        explanation="Calculates gradients",
        source_timestamp=15.0,
        source_formatted_time="00:15",
        source_label="Backprop",
        created_at=base_time,
    )
    q_activation1 = QuizQuestion(
        id=f"{quiz1.id}_q2",
        quiz_id=quiz1.id,
        source_chunk_id=chk_strong.id,
        question_order=2,
        question_text="Why use activation functions?",
        options=["Non-linearity", "Cooling", "Sorting", "Storage"],
        correct_answer="Non-linearity",
        explanation="Adds non-linearity",
        source_timestamp=50.0,
        source_formatted_time="00:50",
        source_label="Activation",
        created_at=base_time,
    )
    db.add_all([q_backprop1, q_activation1])
    db.flush()

    # 4. Attempt 1 at t=0: Learner fails backprop, succeeds activation
    att1 = QuizAttempt(
        id="att_001",
        quiz_id=quiz1.id,
        user_id="legacy_default_user_id",
        total_questions=2,
        correct_count=1,
        score_percentage=50.0,
        performance_tier="Needs Revision",
        created_at=base_time + timedelta(hours=1),
    )
    db.add(att1)
    db.flush()

    ans1_q1 = QuizAnswer(
        attempt_id=att1.id,
        question_id=q_backprop1.id,
        selected_answer="Audio",  # WRONG
        is_correct=False,
        created_at=base_time + timedelta(hours=1),
    )
    ans1_q2 = QuizAnswer(
        attempt_id=att1.id,
        question_id=q_activation1.id,
        selected_answer="Non-linearity",  # CORRECT
        is_correct=True,
        created_at=base_time + timedelta(hours=1),
    )
    db.add_all([ans1_q1, ans1_q2])
    db.flush()

    # 5. Attempt 2 at t=2: Learner again fails backprop, succeeds activation
    att2 = QuizAttempt(
        id="att_002",
        quiz_id=quiz1.id,
        user_id="legacy_default_user_id",
        total_questions=2,
        correct_count=1,
        score_percentage=50.0,
        performance_tier="Needs Revision",
        created_at=base_time + timedelta(hours=2),
    )
    db.add(att2)
    db.flush()

    ans2_q1 = QuizAnswer(
        attempt_id=att2.id,
        question_id=q_backprop1.id,
        selected_answer="Images",  # WRONG AGAIN (2 consecutive failures)
        is_correct=False,
        created_at=base_time + timedelta(hours=2),
    )
    ans2_q2 = QuizAnswer(
        attempt_id=att2.id,
        question_id=q_activation1.id,
        selected_answer="Non-linearity",  # CORRECT AGAIN (2 consecutive successes)
        is_correct=True,
        created_at=base_time + timedelta(hours=2),
    )
    db.add_all([ans2_q1, ans2_q2])
    video_id = vid.id
    db.commit()
    db.close()

    # 6. Call API
    response = client.get(f"/api/videos/{video_id}/knowledge-gaps")
    assert response.status_code == 200
    data = response.json()

    # Verify no Gemini calls were executed during analytics
    mock_summary.assert_not_called()
    mock_quiz.assert_not_called()

    # Verify summary aggregations
    assert data["video_id"] == "vid_analytics_test"
    summary = data["summary"]
    assert summary["total_chunks"] == 3
    assert summary["assessed_chunks"] == 2
    assert summary["weak_chunks_count"] == 1
    assert summary["strong_chunks_count"] == 1
    assert summary["insufficient_data_count"] == 1
    assert data["weak_chunk_ids"] == ["chk_weak_001"]

    # Verify individual chunk classifications
    gaps = data["gaps"]
    assert len(gaps) == 3

    # Priority sort puts WEAK chunk first
    weak_gap = gaps[0]
    assert weak_gap["chunk_id"] == "chk_weak_001"
    assert weak_gap["classification"] == "WEAK"
    assert weak_gap["accuracy"] == 0.0
    assert weak_gap["total_observations"] == 2
    assert weak_gap["consecutive_incorrect_count"] == 2
    assert "consecutive errors" in weak_gap["reason"].lower()

    # STRONG chunk
    strong_gap = next(g for g in gaps if g["chunk_id"] == "chk_strong_002")
    assert strong_gap["classification"] == "STRONG"
    assert strong_gap["accuracy"] == 1.0
    assert strong_gap["has_demonstrated_mastery"] is True

    # UNASSESSED chunk
    unassessed_gap = next(g for g in gaps if g["chunk_id"] == "chk_unassessed_003")
    assert unassessed_gap["classification"] == "INSUFFICIENT_DATA"
    assert unassessed_gap["total_observations"] == 0
    assert "no quiz questions answered" in unassessed_gap["reason"].lower()


def test_learner_overall_knowledge_gaps():
    """GET /api/learners/knowledge-gaps synthesizes cross-video assessment metrics."""
    response = client.get("/api/learners/knowledge-gaps")
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "weak_chunk_ids" in data
    assert "gaps" in data
    assert isinstance(data["videos_analyzed"], int)
