"""
VIDYORA AI - ORM Model Operations & Constraint Enforcement Tests

NOTE / METHODOLOGY:
These tests validate the operational logic of the SQLAlchemy ORM entities:
- Model instantiation and field mapping
- CRUD operations for User, Video, KnowledgeChunk, Quiz, QuizQuestion
- Foreign key enforcement and cascade deletion
- Uniqueness constraint violations

Executed against an isolated in-memory test database with explicit foreign key
enforcement enabled (PRAGMA foreign_keys=ON) to guarantee relational integrity.
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from db.base import Base
from db.models import (
    Flashcard,
    FlashcardDeck,
    KnowledgeChunk,
    LearnerProgress,
    Quiz,
    QuizAnswer,
    QuizAttempt,
    QuizQuestion,
    TranscriptSegment,
    User,
    Video,
    VideoTranscript,
)


@pytest.fixture(scope="function")
def db_session():
    """
    Creates an isolated in-memory database with all tables created from Base.metadata,
    enforcing foreign keys explicitly for constraint validation.
    """
    test_engine = create_engine("sqlite:///:memory:")

    # Enforce SQLite foreign key constraints (disabled by default in SQLite)
    @event.listens_for(test_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


def test_user_crud_lifecycle(db_session: Session):
    """Verifies User creation, retrieval, update, and deletion."""
    # 1. Create
    user = User(
        email="learner@vidyora.ai",
        username="learner_one",
        full_name="Alex Learner",
        hashed_password="hashed_secure_password_123",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert len(user.id) == 36  # UUID v4
    assert user.is_active is True

    # 2. Read
    queried = db_session.query(User).filter_by(email="learner@vidyora.ai").first()
    assert queried is not None
    assert queried.username == "learner_one"

    # 3. Update
    queried.full_name = "Alex Senior Learner"
    db_session.commit()
    db_session.refresh(queried)
    assert queried.full_name == "Alex Senior Learner"

    # 4. Delete
    db_session.delete(queried)
    db_session.commit()
    deleted = db_session.query(User).filter_by(email="learner@vidyora.ai").first()
    assert deleted is None


def test_user_email_uniqueness_constraint(db_session: Session):
    """Verifies that inserting a duplicate user email raises an IntegrityError."""
    user1 = User(email="duplicate@vidyora.ai", username="user1", hashed_password="pw1")
    user2 = User(email="duplicate@vidyora.ai", username="user2", hashed_password="pw2")
    db_session.add(user1)
    db_session.commit()

    db_session.add(user2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_video_crud_and_user_relationship(db_session: Session):
    """Verifies Video creation linked to a User, and querying via relationship."""
    user = User(email="creator@vidyora.ai", username="prof_smith", hashed_password="pw")
    db_session.add(user)
    db_session.commit()

    video = Video(
        id="dQw4w9WgXcQ",
        user_id=user.id,
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        platform="youtube",
        title="Educational Lecture on Neural Networks",
        status="completed",
    )
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)

    assert video.id == "dQw4w9WgXcQ"
    assert video.user.email == "creator@vidyora.ai"
    assert len(user.videos) == 1
    assert user.videos[0].id == "dQw4w9WgXcQ"


def test_invalid_foreign_key_fails(db_session: Session):
    """Verifies that referencing a non-existent parent entity raises an IntegrityError."""
    invalid_video = Video(
        id="vid_nonexistent_user",
        user_id="00000000-0000-0000-0000-000000000000",  # non-existent user
        url="https://youtube.com/watch?v=test",
        platform="youtube",
    )
    db_session.add(invalid_video)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_video_transcript_and_segments_cascade(db_session: Session):
    """Verifies VideoTranscript and time-aligned TranscriptSegment creation and cascade."""
    video = Video(id="vid_transcript_test", url="https://youtube.com/watch?v=transcript", platform="youtube")
    db_session.add(video)
    db_session.commit()

    transcript = VideoTranscript(
        video_id=video.id,
        language="en",
        is_generated=True,
        full_text="Welcome to the machine learning lecture.",
        segment_count=2,
        cleaned_segment_count=2,
    )
    db_session.add(transcript)
    db_session.commit()

    seg1 = TranscriptSegment(
        transcript_id=transcript.id,
        segment_index=0,
        text="Welcome to the",
        start_time=0.0,
        duration=2.5,
        is_cleaned=True,
    )
    seg2 = TranscriptSegment(
        transcript_id=transcript.id,
        segment_index=1,
        text="machine learning lecture.",
        start_time=2.5,
        duration=3.0,
        is_cleaned=True,
    )
    db_session.add_all([seg1, seg2])
    db_session.commit()

    assert len(transcript.segments) == 2
    assert transcript.segments[0].text == "Welcome to the"


def test_knowledge_chunk_creation_and_uniqueness(db_session: Session):
    """Verifies KnowledgeChunk creation and unique constraint on (video_id, chunk_index)."""
    video = Video(id="vid_chunk_test", url="https://youtube.com/watch?v=chunk", platform="youtube")
    db_session.add(video)
    db_session.commit()

    chunk1 = KnowledgeChunk(
        id="chk_01",
        video_id=video.id,
        chunk_index=0,
        text="Gradient descent optimizes weights by calculating partial derivatives.",
        start_time=10.0,
        end_time=45.0,
        duration=35.0,
        word_count=9,
        segment_start_index=0,
        segment_end_index=3,
    )
    db_session.add(chunk1)
    db_session.commit()

    # Attempt inserting duplicate (video_id, chunk_index)
    duplicate_chunk = KnowledgeChunk(
        id="chk_02_duplicate",
        video_id=video.id,
        chunk_index=0,  # Duplicate chunk_index for same video
        text="Duplicate chunk content.",
        start_time=45.0,
        end_time=70.0,
        duration=25.0,
        word_count=3,
        segment_start_index=4,
        segment_end_index=6,
    )
    db_session.add(duplicate_chunk)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_quiz_and_quiz_question_source_grounding(db_session: Session):
    """
    Verifies Quiz and QuizQuestion creation, options JSON serialization,
    and source chunk foreign key linkage.
    """
    video = Video(id="vid_quiz_test", url="https://youtube.com/watch?v=quiz", platform="youtube")
    db_session.add(video)
    db_session.commit()

    chunk = KnowledgeChunk(
        id="chk_source_grounding_01",
        video_id=video.id,
        chunk_index=0,
        text="Backpropagation calculates gradients via the chain rule.",
        start_time=60.0,
        end_time=120.0,
        duration=60.0,
        word_count=7,
        segment_start_index=0,
        segment_end_index=5,
    )
    db_session.add(chunk)
    db_session.commit()

    quiz = Quiz(
        id="quiz_test_101",
        video_id=video.id,
        title="Neural Networks Fundamentals Quiz",
        instructions="Choose the single best answer.",
        model_used="gemini-2.5-flash",
    )
    db_session.add(quiz)
    db_session.commit()

    options = [
        "Product rule",
        "Chain rule",
        "Quotient rule",
        "Power rule",
    ]
    question = QuizQuestion(
        id="q_1",
        quiz_id=quiz.id,
        source_chunk_id=chunk.id,
        question_order=1,
        question_text="What mathematical rule is the foundation of backpropagation?",
        options=options,
        correct_answer="Chain rule",
        explanation="Backpropagation relies on the calculus chain rule to compute gradients.",
        difficulty="medium",
        source_timestamp=65.0,
        source_formatted_time="01:05",
        source_label="Chain rule in backpropagation",
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)

    assert question.id == "q_1"
    assert question.options == options
    assert question.correct_answer == "Chain rule"
    assert question.source_chunk.id == "chk_source_grounding_01"
    assert len(quiz.questions) == 1


def test_quiz_attempt_and_quiz_answer_evaluation(db_session: Session):
    """Verifies storing a completed QuizAttempt and individual QuizAnswers."""
    video = Video(id="vid_attempt_test", url="https://youtube.com/watch?v=attempt", platform="youtube")
    quiz = Quiz(id="quiz_attempt_101", video_id=video.id, title="Test Quiz")
    q1 = QuizQuestion(
        id="q_attempt_1",
        quiz_id=quiz.id,
        question_order=1,
        question_text="What is 2+2?",
        options=["2", "3", "4", "5"],
        correct_answer="4",
        explanation="Basic arithmetic.",
        difficulty="easy",
        source_timestamp=0.0,
        source_formatted_time="00:00",
        source_label="Intro",
    )
    db_session.add_all([video, quiz, q1])
    db_session.commit()

    attempt = QuizAttempt(
        quiz_id=quiz.id,
        total_questions=1,
        correct_count=1,
        score_percentage=100.0,
        performance_tier="Strong",
        performance_summary="Perfect score!",
        weak_chunk_ids=[],
    )
    db_session.add(attempt)
    db_session.commit()

    ans1 = QuizAnswer(
        attempt_id=attempt.id,
        question_id=q1.id,
        selected_answer="4",
        is_correct=True,
    )
    db_session.add(ans1)
    db_session.commit()

    assert len(attempt.answers) == 1
    assert attempt.answers[0].is_correct is True

    # Verifies unique constraint on (attempt_id, question_id)
    duplicate_ans = QuizAnswer(
        attempt_id=attempt.id,
        question_id=q1.id,
        selected_answer="2",
        is_correct=False,
    )
    db_session.add(duplicate_ans)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_video_cascade_deletion(db_session: Session):
    """
    Verifies that deleting a Video cascades and automatically deletes
    its associated transcript, chunks, and quizzes.
    """
    video = Video(id="vid_cascade_test", url="https://youtube.com/watch?v=cascade", platform="youtube")
    transcript = VideoTranscript(video_id=video.id, full_text="Cascade transcript test.")
    chunk = KnowledgeChunk(
        id="chk_cascade",
        video_id=video.id,
        chunk_index=0,
        text="Chunk text",
        start_time=0.0,
        end_time=10.0,
        duration=10.0,
        word_count=2,
        segment_start_index=0,
        segment_end_index=0,
    )
    quiz = Quiz(id="quiz_cascade", video_id=video.id, title="Cascade Quiz")
    db_session.add_all([video, transcript, chunk, quiz])
    db_session.commit()

    # Verify they exist
    assert db_session.query(VideoTranscript).filter_by(video_id=video.id).first() is not None
    assert db_session.query(KnowledgeChunk).filter_by(video_id=video.id).first() is not None
    assert db_session.query(Quiz).filter_by(video_id=video.id).first() is not None

    # Delete video
    db_session.delete(video)
    db_session.commit()

    # Verify cascaded deletion
    assert db_session.query(VideoTranscript).filter_by(video_id="vid_cascade_test").first() is None
    assert db_session.query(KnowledgeChunk).filter_by(video_id="vid_cascade_test").first() is None
    assert db_session.query(Quiz).filter_by(video_id="vid_cascade_test").first() is None
