"""
VIDYORA AI - Tests for Step 13 Phase 4 Persistent Read APIs

Tests:
  1. GET /api/videos (empty database, multiple videos, ordering, lightweight projection)
  2. GET /api/videos/{video_id} (workspace restoration, 404 handling, no Gemini calls)
  3. GET /api/quizzes/{quiz_id}/attempts (history, ordering, 404 handling, zero leakage)
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.base import Base
from db.models import (
    Flashcard,
    FlashcardDeck,
    KnowledgeChunk,
    Quiz,
    QuizAnswer,
    QuizAttempt,
    QuizQuestion,
    TranscriptSegment,
    Video,
    VideoTranscript,
)
from db.session import get_db
from main import app

# In-memory SQLite engine for fast, isolated repository & API testing
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
    """Rebuild in-memory schema and isolate dependency override per test."""
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)



# ===========================================================================
# 1. Tests for GET /api/videos (List Videos)
# ===========================================================================

def test_list_videos_empty_database():
    """GET /api/videos on empty database returns empty list with total_count=0."""
    response = client.get("/api/videos")
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 0
    assert data["videos"] == []


def test_list_videos_populated_and_ordered():
    """GET /api/videos returns lightweight projection ordered by created_at desc."""
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)

    # Video 1: older
    v1 = Video(
        id="vid_older",
        user_id="legacy_default_user_id",
        url="https://www.youtube.com/watch?v=vid_older",
        platform="youtube",
        title="Older Lecture",
        status="completed",
        created_at=datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc),
    )
    # Video 2: newer with transcript and chunks
    v2 = Video(
        id="vid_newer",
        user_id="legacy_default_user_id",
        url="https://www.youtube.com/watch?v=vid_newer",
        platform="youtube",
        title="Newer Lecture",
        status="completed",
        created_at=datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc),
    )
    db.add_all([v1, v2])
    db.flush()

    vt2 = VideoTranscript(
        video_id=v2.id,
        language="en",
        is_generated=True,
        full_text="Some full lecture text.",
        segment_count=15,
        cleaned_segment_count=12,
        created_at=now,
        updated_at=now,
    )
    db.add(vt2)
    db.flush()

    chk = KnowledgeChunk(
        id="chk_new_1",
        video_id=v2.id,
        chunk_index=0,
        text="Chunk content",
        start_time=0.0,
        end_time=30.0,
        duration=30.0,
        word_count=2,
        segment_start_index=0,
        segment_end_index=2,
        created_at=now,
    )
    db.add(chk)
    db.commit()
    db.close()

    response = client.get("/api/videos")
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 2
    videos = data["videos"]

    # Verify descending created_at order
    assert videos[0]["video_id"] == "vid_newer"
    assert videos[0]["title"] == "Newer Lecture"
    assert videos[0]["segment_count"] == 15
    assert videos[0]["chunk_count"] == 1
    assert videos[0]["has_transcript"] is True

    assert videos[1]["video_id"] == "vid_older"
    assert videos[1]["segment_count"] == 0
    assert videos[1]["chunk_count"] == 0
    assert videos[1]["has_transcript"] is False


# ===========================================================================
# 2. Tests for GET /api/videos/{video_id} (Workspace Restoration)
# ===========================================================================

def test_get_video_workspace_not_found_returns_404():
    """GET /api/videos/{video_id} returns 404 for an unknown video_id."""
    response = client.get("/api/videos/nonexistent_id")
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


@patch("services.gemini_service.generate_video_summary")
@patch("services.gemini_service.generate_quiz")
def test_get_video_workspace_loads_persisted_data_without_gemini(mock_quiz, mock_summary):
    """
    GET /api/videos/{video_id} reloads complete video metadata, transcripts,
    chunks, latest quiz, and latest flashcards WITHOUT calling Gemini.
    """
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)

    video = Video(
        id="vid_persisted_test",
        user_id="legacy_default_user_id",
        url="https://www.youtube.com/watch?v=vid_persisted_test",
        platform="youtube",
        title="Persisted Neural Networks",
        status="completed",
        created_at=now,
        updated_at=now,
    )
    db.add(video)
    db.flush()

    vt = VideoTranscript(
        video_id=video.id,
        language="en",
        is_generated=True,
        full_text="Welcome to neural networks.",
        segment_count=2,
        cleaned_segment_count=2,
        created_at=now,
        updated_at=now,
    )
    db.add(vt)
    db.flush()

    seg1 = TranscriptSegment(
        transcript_id=vt.id,
        segment_index=0,
        text="Raw welcome",
        start_time=0.0,
        duration=2.5,
        is_cleaned=False,
        created_at=now,
    )
    c_seg1 = TranscriptSegment(
        transcript_id=vt.id,
        segment_index=0,
        text="Cleaned welcome",
        start_time=0.0,
        duration=2.5,
        is_cleaned=True,
        created_at=now,
    )
    db.add_all([seg1, c_seg1])

    chk = KnowledgeChunk(
        id="chk_nn_1",
        video_id=video.id,
        chunk_index=0,
        text="Neural networks are computational models.",
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

    # Add persisted Quiz with QuizQuestion
    quiz = Quiz(
        id="quiz_persisted_1",
        video_id=video.id,
        title="Neural Networks Quiz",
        instructions="Answer all questions",
        model_used="gemini-2.5-flash",
        created_at=now,
    )
    db.add(quiz)
    db.flush()

    qq = QuizQuestion(
        id=f"{quiz.id}_q_1",
        quiz_id=quiz.id,
        source_chunk_id=chk.id,
        question_order=1,
        question_text="What is a neural network?",
        options=["Model", "Fruit", "Planet", "Animal"],
        correct_answer="Model",
        explanation="Secret server explanation",
        difficulty="medium",
        source_timestamp=5.0,
        source_formatted_time="00:05",
        source_label="Intro",
        created_at=now,
    )
    db.add(qq)

    # Add persisted FlashcardDeck with Flashcard
    deck = FlashcardDeck(
        id="deck_persisted_1",
        video_id=video.id,
        topic="Neural Networks Decks",
        model_used="gemini-2.5-flash",
        created_at=now,
        updated_at=now,
    )
    db.add(deck)
    db.flush()

    card = Flashcard(
        id=f"{deck.id}_c_1",
        deck_id=deck.id,
        source_chunk_id=chk.id,
        card_order=1,
        front="What is backprop?",
        back="Gradient optimization method",
        difficulty="medium",
        source_timestamp=10.0,
        source_formatted_time="00:10",
        source_label="Backprop",
        created_at=now,
    )
    db.add(card)

    video_id_str = video.id
    db.commit()
    db.close()

    # Call endpoint
    response = client.get(f"/api/videos/{video_id_str}")
    assert response.status_code == 200
    data = response.json()

    # Verify no Gemini calls were made
    mock_summary.assert_not_called()
    mock_quiz.assert_not_called()

    # Verify video & transcript reconstruction
    assert data["video"]["id"] == video_id_str
    assert data["video"]["title"] == "Persisted Neural Networks"
    assert data["video"]["transcript"]["full_text"] == "Welcome to neural networks."
    assert len(data["video"]["transcript"]["segments"]) == 1
    assert data["video"]["transcript"]["segments"][0]["text"] == "Raw welcome"
    assert len(data["video"]["transcript"]["cleaned_segments"]) == 1
    assert data["video"]["transcript"]["cleaned_segments"][0]["text"] == "Cleaned welcome"
    assert len(data["video"]["transcript"]["chunks"]) == 1
    assert data["video"]["transcript"]["chunks"][0]["chunk_id"] == "chk_nn_1"

    # Verify latest quiz restored securely (NO answer key or explanation leaked!)
    assert data["latest_quiz"] is not None
    assert data["latest_quiz"]["quiz_id"] == "quiz_persisted_1"
    assert len(data["latest_quiz"]["questions"]) == 1
    q_client = data["latest_quiz"]["questions"][0]
    assert q_client["id"] == "q_1"
    assert q_client["question"] == "What is a neural network?"
    assert "correct_answer" not in q_client
    assert "explanation" not in q_client

    # Verify flashcards restored
    assert data["latest_flashcards"] is not None
    assert data["latest_flashcards"]["topic"] == "Neural Networks Decks"
    assert len(data["latest_flashcards"]["cards"]) == 1
    assert data["latest_flashcards"]["cards"][0]["front"] == "What is backprop?"


# ===========================================================================
# 3. Tests for GET /api/quizzes/{quiz_id}/attempts (Quiz History)
# ===========================================================================

def test_quiz_attempt_history_not_found_returns_404():
    """GET /api/quizzes/{quiz_id}/attempts returns 404 if quiz does not exist."""
    response = client.get("/api/quizzes/unknown_quiz/attempts")
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


def test_quiz_attempt_history_empty_returns_200():
    """GET /api/quizzes/{quiz_id}/attempts returns 200 with empty list when quiz has no attempts."""
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)

    video = Video(
        id="vid_test_quiz_empty",
        user_id="legacy_default_user_id",
        url="https://www.youtube.com/watch?v=vid_test_quiz_empty",
        platform="youtube",
        title="Quiz Video",
        status="completed",
        created_at=now,
        updated_at=now,
    )
    db.add(video)
    db.flush()

    quiz = Quiz(
        id="quiz_no_attempts",
        video_id=video.id,
        title="Unattempted Quiz",
        created_at=now,
    )
    db.add(quiz)
    quiz_id_str = quiz.id
    db.commit()
    db.close()

    response = client.get(f"/api/quizzes/{quiz_id_str}/attempts")
    assert response.status_code == 200
    data = response.json()
    assert data["quiz_id"] == "quiz_no_attempts"
    assert data["total_attempts"] == 0
    assert data["attempts"] == []


def test_quiz_attempt_history_multiple_attempts_ordered_and_secure():
    """GET /api/quizzes/{quiz_id}/attempts returns attempts chronologically desc and leaks no answer keys."""
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)

    video = Video(
        id="vid_history_test",
        user_id="legacy_default_user_id",
        url="https://www.youtube.com/watch?v=vid_history_test",
        platform="youtube",
        title="History Video",
        status="completed",
        created_at=now,
        updated_at=now,
    )
    db.add(video)
    db.flush()

    quiz = Quiz(
        id="quiz_with_history",
        video_id=video.id,
        title="Historical Quiz",
        created_at=now,
    )
    db.add(quiz)
    db.flush()

    qq1 = QuizQuestion(
        id=f"{quiz.id}_q_1",
        quiz_id=quiz.id,
        question_order=1,
        question_text="Q1 text",
        options=["A", "B", "C", "D"],
        correct_answer="A",
        explanation="Secret",
        difficulty="easy",
        source_timestamp=0.0,
        source_formatted_time="00:00",
        source_label="Intro",
        created_at=now,
    )
    db.add(qq1)
    db.flush()

    # Attempt 1: older, scored 50%
    att1 = QuizAttempt(
        id="att_1",
        quiz_id=quiz.id,
        user_id="legacy_default_user_id",
        total_questions=2,
        correct_count=1,
        score_percentage=50.0,
        performance_tier="Needs Revision",
        performance_summary="Needs revision summary",
        weak_chunk_ids=["chk_1"],
        created_at=datetime(2026, 10, 3, 14, 0, tzinfo=timezone.utc),
    )
    # Attempt 2: newer, scored 100%
    att2 = QuizAttempt(
        id="att_2",
        quiz_id=quiz.id,
        user_id="legacy_default_user_id",
        total_questions=2,
        correct_count=2,
        score_percentage=100.0,
        performance_tier="Strong",
        performance_summary="Mastery summary",
        weak_chunk_ids=[],
        created_at=datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc),
    )
    db.add_all([att1, att2])
    db.flush()

    ans1 = QuizAnswer(
        attempt_id=att2.id,
        question_id=qq1.id,
        selected_answer="A",
        is_correct=True,
        created_at=datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc),
    )
    db.add(ans1)
    quiz_id_str = quiz.id
    db.commit()
    db.close()

    response = client.get(f"/api/quizzes/{quiz_id_str}/attempts")
    assert response.status_code == 200
    data = response.json()
    assert data["quiz_id"] == "quiz_with_history"
    assert data["total_attempts"] == 2

    # Verify ordered most recent first
    assert data["attempts"][0]["attempt_id"] == "att_2"
    assert data["attempts"][0]["score_percentage"] == 100.0
    assert data["attempts"][0]["performance_tier"] == "Strong"
    assert len(data["attempts"][0]["answers"]) == 1
    assert data["attempts"][0]["answers"][0]["question_id"] == "q_1"
    assert data["attempts"][0]["answers"][0]["selected_answer"] == "A"
    assert data["attempts"][0]["answers"][0]["is_correct"] is True
    # Ensure answer key is NOT leaked
    assert "correct_answer" not in data["attempts"][0]["answers"][0]
    assert "explanation" not in data["attempts"][0]["answers"][0]

    assert data["attempts"][1]["attempt_id"] == "att_1"
    assert data["attempts"][1]["score_percentage"] == 50.0
    assert data["attempts"][1]["performance_tier"] == "Needs Revision"
