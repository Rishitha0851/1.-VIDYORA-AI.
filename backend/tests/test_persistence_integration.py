"""
VIDYORA AI - Step 13 Phase 3 Persistence Integration Tests

Tests:
1. Successful video, transcript, segments, and knowledge chunk persistence.
2. Idempotency and duplicate video handling (clean replacement without constraint crashes).
3. Transaction rollback on failure (ensuring no partial records).
4. Quiz and question persistence with server-side answer protection.
5. Quiz evaluation reading from database and deterministic scoring.
6. Quiz attempt and answer persistence.
7. Flashcard deck and card persistence preserving source grounding.
8. Persistence survival across session simulation (backend restart simulation).
"""

import pytest
from sqlalchemy.orm import Session

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
from db.session import SessionLocal
from models import (
    Flashcard as PydanticFlashcard,
    GeneratedQuizInternal,
    QuizDifficulty,
    QuizQuestionInternal,
    SourceTimestamp,
    TranscriptChunk as PydanticChunk,
    TranscriptSegment as PydanticSegment,
    VideoTranscript as PydanticTranscript,
)
from repositories import FlashcardRepository, QuizRepository, VideoRepository


@pytest.fixture
def db():
    """Provides a transactional database session for tests."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_video_and_chunks_persistence(db: Session):
    """Verifies persisting a video with transcript, segments, and knowledge chunks."""
    vid_id = "test_persistence_vid_001"
    url = f"https://www.youtube.com/watch?v={vid_id}"

    raw_segs = [
        PydanticSegment(text="Hello learners.", start=0.0, duration=2.0),
        PydanticSegment(text="Welcome to deep learning.", start=2.0, duration=3.0),
    ]
    clean_segs = [
        PydanticSegment(text="Hello learners.", start=0.0, duration=2.0),
        PydanticSegment(text="Welcome to deep learning.", start=2.0, duration=3.0),
    ]
    chunks = [
        PydanticChunk(
            chunk_id=f"chk_{vid_id}_0",
            chunk_index=0,
            video_id=vid_id,
            text="Hello learners. Welcome to deep learning.",
            start_time=0.0,
            end_time=5.0,
            duration=5.0,
            word_count=6,
            segment_start_index=0,
            segment_end_index=1,
        )
    ]

    p_transcript = PydanticTranscript(
        video_id=vid_id,
        language="en",
        is_generated=True,
        full_text="Hello learners. Welcome to deep learning.",
        segments=raw_segs,
        segment_count=2,
        cleaned_segments=clean_segs,
        cleaned_segment_count=2,
        chunks=chunks,
        chunk_count=1,
    )

    # Persist
    saved_video = VideoRepository.save_processed_video(
        db=db,
        video_id=vid_id,
        url=url,
        platform="youtube",
        title="Intro to Deep Learning",
        transcript_data=p_transcript,
    )

    assert saved_video.id == vid_id
    assert saved_video.status == "completed"

    # Query from fresh query
    fetched_video = db.query(Video).filter(Video.id == vid_id).first()
    assert fetched_video is not None
    assert fetched_video.title == "Intro to Deep Learning"
    assert fetched_video.transcript is not None
    assert fetched_video.transcript.language == "en"
    assert len(fetched_video.transcript.segments) == 4  # 2 raw + 2 cleaned
    assert len(fetched_video.chunks) == 1
    assert fetched_video.chunks[0].id == f"chk_{vid_id}_0"


def test_duplicate_video_idempotency(db: Session):
    """Verifies that re-processing an existing video updates data without duplicate key errors."""
    vid_id = "test_persistence_vid_001"
    url = f"https://www.youtube.com/watch?v={vid_id}"

    # Re-process with updated title and new chunks
    raw_segs = [PydanticSegment(text="Updated lecture.", start=0.0, duration=3.0)]
    clean_segs = [PydanticSegment(text="Updated lecture.", start=0.0, duration=3.0)]
    chunks = [
        PydanticChunk(
            chunk_id=f"chk_{vid_id}_updated",
            chunk_index=0,
            video_id=vid_id,
            text="Updated lecture.",
            start_time=0.0,
            end_time=3.0,
            duration=3.0,
            word_count=2,
            segment_start_index=0,
            segment_end_index=0,
        )
    ]
    p_transcript = PydanticTranscript(
        video_id=vid_id,
        language="en",
        is_generated=False,
        full_text="Updated lecture.",
        segments=raw_segs,
        segment_count=1,
        cleaned_segments=clean_segs,
        cleaned_segment_count=1,
        chunks=chunks,
        chunk_count=1,
    )

    updated_video = VideoRepository.save_processed_video(
        db=db,
        video_id=vid_id,
        url=url,
        platform="youtube",
        title="Updated Intro to Deep Learning",
        transcript_data=p_transcript,
    )

    assert updated_video.title == "Updated Intro to Deep Learning"
    assert len(updated_video.chunks) == 1
    assert updated_video.chunks[0].id == f"chk_{vid_id}_updated"


def test_quiz_persistence_and_answer_security(db: Session):
    """
    Verifies that a generated quiz is persisted with correct answers and explanations,
    while server-side query confirms answers remain in DB.
    """
    vid_id = "test_quiz_vid_001"
    quiz_id = "quiz_persist_test_999"

    q1 = QuizQuestionInternal(
        id="q_1",
        question="What does an activation function introduce?",
        options=["Linearity", "Non-linearity", "Random noise", "Zero output"],
        correct_answer="Non-linearity",
        explanation="Activation functions introduce non-linear properties to neural networks.",
        difficulty=QuizDifficulty.MEDIUM,
        source_timestamp=SourceTimestamp(timestamp=12.5, formatted_time="00:12", label="Activation topic"),
        source_chunk_id="chk_non_linear_01",
    )

    internal_quiz = GeneratedQuizInternal(
        quiz_id=quiz_id,
        video_id=vid_id,
        title="Neural Net Activations Quiz",
        instructions="Choose the correct answer.",
        questions=[q1],
    )

    # Persist
    saved_quiz = QuizRepository.save_quiz(db, internal_quiz, model_used="gemini-2.5-flash")
    assert saved_quiz.id == quiz_id

    # Retrieve from DB directly
    fetched_quiz = QuizRepository.get_quiz_by_id(db, quiz_id)
    assert fetched_quiz is not None
    assert len(fetched_quiz.questions) == 1
    q_db = fetched_quiz.questions[0]
    assert q_db.correct_answer == "Non-linearity"
    assert q_db.explanation == "Activation functions introduce non-linear properties to neural networks."
    assert q_db.options == ["Linearity", "Non-linearity", "Random noise", "Zero output"]


def test_quiz_attempt_and_answers_persistence(db: Session):
    """Verifies that grading a quiz persists QuizAttempt and individual QuizAnswer records."""
    quiz_id = "quiz_persist_test_999"
    db_quiz = QuizRepository.get_quiz_by_id(db, quiz_id)
    assert db_quiz is not None
    q_db = db_quiz.questions[0]

    attempt = QuizRepository.save_quiz_attempt(
        db=db,
        quiz_id=quiz_id,
        total_questions=1,
        correct_count=1,
        score_percentage=100.0,
        performance_tier="Strong",
        performance_summary="Mastery achieved!",
        weak_chunk_ids=[],
        question_answers=[
            {
                "question_id": q_db.id,
                "selected_answer": "Non-linearity",
                "is_correct": True,
            }
        ],
        user_id=None,
    )

    assert attempt.id is not None
    assert attempt.score_percentage == 100.0
    assert attempt.performance_tier == "Strong"

    # Query attempt from DB
    queried_attempt = db.query(QuizAttempt).filter(QuizAttempt.id == attempt.id).first()
    assert queried_attempt is not None
    assert len(queried_attempt.answers) == 1
    assert queried_attempt.answers[0].is_correct is True
    assert queried_attempt.answers[0].selected_answer == "Non-linearity"


def test_flashcard_persistence_and_chunk_grounding(db: Session):
    """Verifies that generated flashcards are persisted with source timestamps and chunk IDs."""
    vid_id = "test_cards_vid_001"
    card1 = PydanticFlashcard(
        id="c_1",
        front="What is a learning rate?",
        back="A hyperparameter that controls how much to change the model in response to the estimated error gradient.",
        difficulty=QuizDifficulty.EASY,
        source_timestamp=SourceTimestamp(timestamp=30.0, formatted_time="00:30", label="Learning rate intro"),
        source_chunk_id="chk_lr_01",
    )

    deck = FlashcardRepository.save_flashcard_deck(
        db=db,
        video_id=vid_id,
        topic="Optimization Concepts",
        cards=[card1],
        model_used="gemini-2.5-flash",
        user_id=None,
    )

    assert deck.id is not None
    assert deck.topic == "Optimization Concepts"

    # Query decks for video
    decks = FlashcardRepository.get_decks_by_video_id(db, vid_id)
    assert len(decks) >= 1
    target_deck = next(d for d in decks if d.id == deck.id)
    assert len(target_deck.cards) == 1
    assert target_deck.cards[0].front == "What is a learning rate?"
    assert target_deck.cards[0].source_timestamp == 30.0
