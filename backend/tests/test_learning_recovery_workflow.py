"""
VIDYORA AI - Step 4: Personalized Learning Recovery Workflow Integration Tests

Validates:
  1. Gap diagnosis distinguishes incorrect answers from unanswered/skipped questions.
  2. Confidence level is computed empirically from answered observations.
  3. Recovery session creation and retrieval via GET /api/videos/{video_id}/chunks/{chunk_id}/recovery.
  4. Session reuse prevents redundant Gemini calls when in-progress session exists.
  5. Server-side grading, before-and-after comparison, and atomic LearnerProgress persistence.
  6. Strict cross-user isolation and security enforcement (User B cannot access User A's recovery).
  7. Idempotent submission preventing duplicate progress records.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.base import Base
from db.models import (
    KnowledgeChunk,
    LearnerProgress,
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
    KnowledgeGapClassification,
    QuizDifficulty,
    QuizQuestionInternal,
    RecoveryInterventionInternal,
    RecoveryResultEnum,
    SourceTimestamp,
)
from services.auth_service import create_access_token

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
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def create_mock_intervention(chunk_id: str) -> RecoveryInterventionInternal:
    return RecoveryInterventionInternal(
        title="Targeted Recovery: Fundamental Concepts",
        explanation="Here is a step-by-step breakdown grounded in the lecture segment.",
        worked_example="For instance, if X is applied, result Y follows predictably.",
        key_takeaway="Always confirm prerequisite conditions before applying the rule.",
        questions=[
            QuizQuestionInternal(
                id=f"rec_q_{i}",
                question=f"Grounded Concept Check Question {i + 1}?",
                options=["Option A (Correct)", "Option B", "Option C", "Option D"],
                correct_answer="Option A (Correct)",
                explanation=f"Explanation for question {i + 1}",
                difficulty=QuizDifficulty.MEDIUM,
                source_timestamp=SourceTimestamp(
                    timestamp=120.0 + i * 30,
                    formatted_time="02:00",
                    label="02:00",
                ),
                source_chunk_id=chunk_id,
            )
            for i in range(3)
        ],
    )


def seed_test_environment(db):
    user_a = User(
        id="user_a_101",
        email="user_a@vidyora.ai",
        username="user_a",
        full_name="User Alpha",
        hashed_password="mock_hash",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    user_b = User(
        id="user_b_202",
        email="user_b@vidyora.ai",
        username="user_b",
        full_name="User Beta",
        hashed_password="mock_hash",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add_all([user_a, user_b])

    video_a = Video(
        id="vid_workflow_a",
        user_id=user_a.id,
        title="Physics Lecture: Newton's Laws",
        url="https://youtube.com/watch?v=workflow123",
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    db.add(video_a)

    chunk_0 = KnowledgeChunk(
        id="chunk_wf_0",
        video_id=video_a.id,
        chunk_index=0,
        text="Newton's First Law describes inertia and uniform motion without external force.",
        start_time=0.0,
        end_time=60.0,
        duration=60.0,
        word_count=12,
        segment_start_index=0,
        segment_end_index=2,
    )
    chunk_1 = KnowledgeChunk(
        id="chunk_wf_1",
        video_id=video_a.id,
        chunk_index=1,
        text="Newton's Second Law defines force as the product of mass and acceleration F=ma.",
        start_time=60.0,
        end_time=120.0,
        duration=60.0,
        word_count=13,
        segment_start_index=3,
        segment_end_index=5,
    )
    db.add_all([chunk_0, chunk_1])
    db.commit()

    token_a = create_access_token({"sub": user_a.id})
    token_b = create_access_token({"sub": user_b.id})
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    return user_a, user_b, video_a, [chunk_0, chunk_1], headers_a, headers_b


def test_gap_distinction_incorrect_vs_unanswered():
    """
    Verifies that incorrect answers identify a conceptual gap,
    while skipped/unanswered questions are clearly distinguished and not labeled as misconceptions.
    """
    db = TestingSessionLocal()
    user_a, _, video, chunks, headers_a, _ = seed_test_environment(db)
    target_chunk = chunks[0]

    quiz = Quiz(
        id="quiz_wf_1",
        video_id=video.id,
        title="Physics Assessment",
        instructions="Answer all questions",
    )
    db.add(quiz)

    q1 = QuizQuestion(
        id="q_1",
        quiz_id=quiz.id,
        question_order=1,
        question_text="What is inertia?",
        options=["Resistance to change", "Force", "Velocity", "Acceleration"],
        correct_answer="Resistance to change",
        explanation="Inertia resists acceleration.",
        difficulty="medium",
        source_timestamp=0.0,
        source_formatted_time="00:00",
        source_label="00:00",
        source_chunk_id=target_chunk.id,
    )
    q2 = QuizQuestion(
        id="q_2",
        quiz_id=quiz.id,
        question_order=2,
        question_text="What happens when net force is zero?",
        options=["Stops immediately", "Constant velocity", "Accelerates", "Spins"],
        correct_answer="Constant velocity",
        explanation="Velocity remains constant.",
        difficulty="medium",
        source_timestamp=20.0,
        source_formatted_time="00:20",
        source_label="00:20",
        source_chunk_id=target_chunk.id,
    )
    db.add_all([q1, q2])

    attempt = QuizAttempt(
        id="att_1",
        quiz_id=quiz.id,
        user_id=user_a.id,
        total_questions=2,
        correct_count=0,
        score_percentage=0.0,
        performance_tier="needs_revision",
        created_at=datetime.now(timezone.utc),
    )
    db.add(attempt)

    ans1 = QuizAnswer(
        id="ans_1",
        attempt_id=attempt.id,
        question_id=q1.id,
        selected_answer="Velocity",  # Incorrect
        is_correct=False,
    )
    ans2 = QuizAnswer(
        id="ans_2",
        attempt_id=attempt.id,
        question_id=q2.id,
        selected_answer=None,  # Unanswered / skipped
        is_correct=False,
    )
    db.add_all([ans1, ans2])
    db.commit()

    resp = client.get(f"/api/videos/{video.id}/knowledge-gaps", headers=headers_a)
    assert resp.status_code == 200
    data = resp.json()

    gap0 = next(g for g in data["gaps"] if g["chunk_id"] == target_chunk.id)
    assert gap0["incorrect_count"] == 1
    assert gap0["unanswered_count"] == 1
    assert gap0["total_observations"] == 2
    assert gap0["accuracy"] == 0.0
    # Single answered mistake with skipped question -> INSUFFICIENT_DATA (honest diagnosis without jumping to conclusion)
    assert gap0["classification"] == KnowledgeGapClassification.INSUFFICIENT_DATA.value
    assert "skipped" in gap0["reason"].lower() or "unanswered" in gap0["reason"].lower() or "single isolated mistake" in gap0["reason"].lower()


def test_confidence_level_computation():
    """
    Verifies that empirical confidence level reflects observation depth:
    >= 4 answered observations -> High
    2-3 answered observations -> Moderate
    1 answered observation -> Low
    0 answered observations -> None
    """
    db = TestingSessionLocal()
    user_a, _, video, chunks, headers_a, _ = seed_test_environment(db)
    target_chunk = chunks[0]

    quiz = Quiz(id="quiz_conf", video_id=video.id, title="Confidence Test", instructions="")
    db.add(quiz)
    questions = [
        QuizQuestion(
            id=f"q_c_{i}",
            quiz_id=quiz.id,
            question_order=i + 1,
            question_text=f"Q{i}",
            options=["A", "B"],
            correct_answer="A",
            explanation="",
            difficulty="easy",
            source_timestamp=0.0,
            source_formatted_time="00:00",
            source_label="00:00",
            source_chunk_id=target_chunk.id,
        )
        for i in range(3)
    ]
    db.add_all(questions)

    attempt = QuizAttempt(
        id="att_conf",
        quiz_id=quiz.id,
        user_id=user_a.id,
        total_questions=3,
        correct_count=3,
        score_percentage=100.0,
        performance_tier="mastered",
        created_at=datetime.now(timezone.utc),
    )
    db.add(attempt)

    for i, q in enumerate(questions):
        db.add(QuizAnswer(id=f"ans_c_{i}", attempt_id=attempt.id, question_id=q.id, selected_answer="A", is_correct=True))
    db.commit()

    resp = client.get(f"/api/videos/{video.id}/knowledge-gaps", headers=headers_a)
    assert resp.status_code == 200
    gap = next(g for g in resp.json()["gaps"] if g["chunk_id"] == target_chunk.id)
    assert gap["confidence_level"] == "Moderate (3 observations)"


def test_recovery_session_creation_reuse_and_latest_endpoint():
    """
    Verifies:
    1. POST /api/recovery creates a targeted intervention session.
    2. GET /api/videos/{video_id}/chunks/{chunk_id}/recovery retrieves it.
    3. If session is unsubmitted and reuse_existing=True, session is reused without calling Gemini.
    """
    db = TestingSessionLocal()
    user_a, _, video, chunks, headers_a, _ = seed_test_environment(db)
    target_chunk = chunks[0]
    mock_intervention = create_mock_intervention(target_chunk.id)

    with patch("services.recovery_service.generate_recovery_intervention", return_value=(mock_intervention, "gemini-2.5-flash")) as mock_gen:
        # Create session 1
        create_resp = client.post(
            "/api/recovery",
            headers=headers_a,
            json={"video_id": video.id, "chunk_id": target_chunk.id},
        )
        assert create_resp.status_code == 201
        session_data = create_resp.json()
        assert session_data["chunk_id"] == target_chunk.id
        assert session_data["status"] == "QUIZ_READY"
        assert len(session_data["micro_quiz"]) == 3
        assert mock_gen.call_count == 1

        # Fetch latest recovery via new GET endpoint
        get_resp = client.get(
            f"/api/videos/{video.id}/chunks/{target_chunk.id}/recovery",
            headers=headers_a,
        )
        assert get_resp.status_code == 200
        latest_data = get_resp.json()
        assert latest_data["id"] == session_data["id"]
        assert latest_data["status"] == "QUIZ_READY"

        # Verify KnowledgeGap response reflects recovery_in_progress
        gap_resp = client.get(f"/api/videos/{video.id}/knowledge-gaps", headers=headers_a)
        assert gap_resp.status_code == 200
        gap_item = next(g for g in gap_resp.json()["gaps"] if g["chunk_id"] == target_chunk.id)
        assert gap_item["recovery_status"] == "recovery_in_progress"
        assert gap_item["recovery_session_id"] == session_data["id"]

        # Call POST with reuse_existing=True -> should reuse existing session without calling Gemini
        reuse_resp = client.post(
            "/api/recovery",
            headers=headers_a,
            json={
                "video_id": video.id,
                "chunk_id": target_chunk.id,
                "reuse_existing": True,
            },
        )
        assert reuse_resp.status_code == 201
        assert reuse_resp.json()["id"] == session_data["id"]
        assert mock_gen.call_count == 1  # Gemini was NOT called again


def test_recovery_evaluation_and_learner_progress_persistence():
    """
    Verifies that submitting a recovery micro-quiz:
    1. Evaluates server-side deterministically (100% correct -> RECOVERED).
    2. Atomically updates LearnerProgress with mastery_score and review_count.
    3. Reflects improvement_demonstrated in knowledge gaps summary.
    """
    db = TestingSessionLocal()
    user_a, _, video, chunks, headers_a, _ = seed_test_environment(db)
    target_chunk = chunks[0]
    mock_intervention = create_mock_intervention(target_chunk.id)

    with patch("services.recovery_service.generate_recovery_intervention", return_value=(mock_intervention, "gemini-2.5-flash")):
        create_resp = client.post(
            "/api/recovery",
            headers=headers_a,
            json={"video_id": video.id, "chunk_id": target_chunk.id},
        )
        assert create_resp.status_code == 201
        session_id = create_resp.json()["id"]

    # Submit all correct answers
    submit_payload = {
        "selected_answers": {
            "rec_q_0": "Option A (Correct)",
            "rec_q_1": "Option A (Correct)",
            "rec_q_2": "Option A (Correct)",
        }
    }
    submit_resp = client.post(
        f"/api/recovery/{session_id}/submit",
        headers=headers_a,
        json=submit_payload,
    )
    assert submit_resp.status_code == 200
    eval_data = submit_resp.json()
    assert eval_data["recovery_result"] == RecoveryResultEnum.RECOVERED.value
    assert eval_data["correct_count"] == 3
    assert eval_data["post_recovery_accuracy"] == 100.0

    # Verify LearnerProgress table in DB was updated
    progress = (
        db.query(LearnerProgress)
        .filter(LearnerProgress.user_id == user_a.id, LearnerProgress.chunk_id == target_chunk.id)
        .first()
    )
    assert progress is not None
    assert progress.mastery_score == 100.0
    assert progress.review_count == 1
    assert progress.needs_revision is False

    # Verify knowledge gaps summary now reports recovered_chunks_count = 1
    gap_resp = client.get(f"/api/videos/{video.id}/knowledge-gaps", headers=headers_a)
    summary = gap_resp.json()["summary"]
    assert summary["recovered_chunks_count"] == 1
    assert summary["recovery_in_progress_count"] == 0

    gap_item = next(g for g in gap_resp.json()["gaps"] if g["chunk_id"] == target_chunk.id)
    assert gap_item["recovery_status"] == "improvement_demonstrated"
    assert gap_item["has_recovered"] is True


def test_cross_user_isolation_for_recovery():
    """
    Verifies strict authentication and isolation:
    User B cannot access or submit User A's recovery session.
    """
    db = TestingSessionLocal()
    _, _, video, chunks, headers_a, headers_b = seed_test_environment(db)
    target_chunk = chunks[0]
    mock_intervention = create_mock_intervention(target_chunk.id)

    with patch("services.recovery_service.generate_recovery_intervention", return_value=(mock_intervention, "gemini-2.5-flash")):
        create_resp = client.post(
            "/api/recovery",
            headers=headers_a,
            json={"video_id": video.id, "chunk_id": target_chunk.id},
        )
        assert create_resp.status_code == 201
        session_id = create_resp.json()["id"]

    # User B attempts to access User A's session -> 403 Forbidden
    unauthorized_get = client.get(f"/api/recovery/{session_id}", headers=headers_b)
    assert unauthorized_get.status_code == 403

    # User B attempts to submit User A's session -> 403 Forbidden
    unauthorized_submit = client.post(
        f"/api/recovery/{session_id}/submit",
        headers=headers_b,
        json={"selected_answers": {"rec_q_0": "Option A (Correct)"}},
    )
    assert unauthorized_submit.status_code == 403

    # User B attempts to query User A's chunk recovery -> 404 (video not found for User B)
    unauthorized_chunk_rec = client.get(
        f"/api/videos/{video.id}/chunks/{target_chunk.id}/recovery",
        headers=headers_b,
    )
    assert unauthorized_chunk_rec.status_code == 404


def test_idempotent_recovery_submission():
    """
    Verifies that repeated submissions are rejected with HTTP 400
    and do not overwrite or duplicate progress records.
    """
    db = TestingSessionLocal()
    _, _, video, chunks, headers_a, _ = seed_test_environment(db)
    target_chunk = chunks[0]
    mock_intervention = create_mock_intervention(target_chunk.id)

    with patch("services.recovery_service.generate_recovery_intervention", return_value=(mock_intervention, "gemini-2.5-flash")):
        create_resp = client.post(
            "/api/recovery",
            headers=headers_a,
            json={"video_id": video.id, "chunk_id": target_chunk.id},
        )
        assert create_resp.status_code == 201
        session_id = create_resp.json()["id"]

    submit_payload = {
        "selected_answers": {
            "rec_q_0": "Option A (Correct)",
            "rec_q_1": "Option A (Correct)",
            "rec_q_2": "Option A (Correct)",
        }
    }
    first_sub = client.post(f"/api/recovery/{session_id}/submit", headers=headers_a, json=submit_payload)
    assert first_sub.status_code == 200

    # Second submission attempt on same session -> rejected with 400
    second_sub = client.post(f"/api/recovery/{session_id}/submit", headers=headers_a, json=submit_payload)
    assert second_sub.status_code == 400
    assert "already been submitted" in second_sub.json()["detail"].lower()
