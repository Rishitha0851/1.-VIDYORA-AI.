"""
VIDYORA AI - Relational Database ORM Models

Defines the SQLAlchemy 2.0 ORM persistence entities supporting educational video
ingestion, multi-tier transcript chunking, AI-generated assessments, and adaptive
learner tracking.

Entities:
  1. User (users)
  2. Video (videos)
  3. VideoTranscript (video_transcripts)
  4. TranscriptSegment (transcript_segments)
  5. KnowledgeChunk (knowledge_chunks)
  6. Quiz (quizzes)
  7. QuizQuestion (quiz_questions)
  8. QuizAttempt (quiz_attempts)
  9. QuizAnswer (quiz_answers)
  10. FlashcardDeck (flashcard_decks)
  11. Flashcard (flashcards)
  12. LearnerProgress (learner_progress)
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from config import settings
from db.base import Base


def generate_uuid() -> str:
    """Generates a standard RFC 4122 v4 UUID string."""
    return str(uuid.uuid4())


# ===========================================================================
# 1. User Entity
# ===========================================================================
class User(Base):
    """
    Represents an authenticated learner on the VIDYORA AI platform.
    Auth is deferred to a future phase; this entity establishes the foreign
    key anchors for videos, quiz attempts, and learning analytics.
    """
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    videos: Mapped[list["Video"]] = relationship("Video", back_populates="user")
    quiz_attempts: Mapped[list["QuizAttempt"]] = relationship(
        "QuizAttempt", back_populates="user", cascade="all, delete-orphan"
    )
    learner_progress: Mapped[list["LearnerProgress"]] = relationship(
        "LearnerProgress", back_populates="user", cascade="all, delete-orphan"
    )
    flashcard_decks: Mapped[list["FlashcardDeck"]] = relationship("FlashcardDeck", back_populates="user")
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"


# ===========================================================================
# 2. Video Entity
# ===========================================================================
class Video(Base):
    """
    Represents an educational video resource submitted to VIDYORA AI.
    Serves as the root entity for transcripts, chunks, quizzes, and flashcards.
    """
    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # YouTube 11-char ID or generated token
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="youtube")
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="submitted", index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="videos")
    transcript: Mapped[Optional["VideoTranscript"]] = relationship(
        "VideoTranscript", back_populates="video", uselist=False, cascade="all, delete-orphan"
    )
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        "KnowledgeChunk",
        back_populates="video",
        cascade="all, delete-orphan",
        order_by="KnowledgeChunk.chunk_index",
    )
    quizzes: Mapped[list["Quiz"]] = relationship(
        "Quiz", back_populates="video", cascade="all, delete-orphan"
    )
    flashcard_decks: Mapped[list["FlashcardDeck"]] = relationship(
        "FlashcardDeck", back_populates="video", cascade="all, delete-orphan"
    )
    learner_progress: Mapped[list["LearnerProgress"]] = relationship(
        "LearnerProgress", back_populates="video", cascade="all, delete-orphan"
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="video", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Video id={self.id} platform={self.platform} status={self.status}>"


# ===========================================================================
# 3. VideoTranscript Entity
# ===========================================================================
class VideoTranscript(Base):
    """
    Aggregated time-aligned spoken transcript for an educational video.
    Maintains 1-to-1 relationship with Video.
    """
    __tablename__ = "video_transcripts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    video_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("videos.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    is_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    segment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cleaned_segment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="transcript")
    segments: Mapped[list["TranscriptSegment"]] = relationship(
        "TranscriptSegment",
        back_populates="transcript",
        cascade="all, delete-orphan",
        order_by="TranscriptSegment.start_time",
    )

    def __repr__(self) -> str:
        return f"<VideoTranscript id={self.id} video_id={self.video_id} lang={self.language}>"


# ===========================================================================
# 4. TranscriptSegment Entity
# ===========================================================================
class TranscriptSegment(Base):
    """
    An individual, time-aligned closed caption snippet extracted from the video.
    Indexed by transcript and timestamp for rapid playback synchronization.
    """
    __tablename__ = "transcript_segments"
    __table_args__ = (
        Index("ix_transcript_segments_transcript_time", "transcript_id", "start_time"),
        Index("ix_transcript_segments_transcript_order", "transcript_id", "segment_index"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    transcript_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("video_transcripts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    duration: Mapped[float] = mapped_column(Float, nullable=False)
    is_cleaned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    transcript: Mapped["VideoTranscript"] = relationship("VideoTranscript", back_populates="segments")

    def __repr__(self) -> str:
        return f"<TranscriptSegment id={self.id} idx={self.segment_index} start={self.start_time:.2f}>"


# ===========================================================================
# 5. KnowledgeChunk Entity
# ===========================================================================
class KnowledgeChunk(Base):
    """
    A contiguous, semantically cohesive knowledge chunk created by deterministic
    aggregation of cleaned transcript segments.
    
    Serves as the foundation for citation grounding, RAG indexing, and weak-area
    identification in adaptive learning loops.
    """
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("video_id", "chunk_index", name="uq_knowledge_chunks_video_chunk_index"),
        Index("ix_knowledge_chunks_video_order", "video_id", "chunk_index"),
        Index("ix_knowledge_chunks_video_time", "video_id", "start_time"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # chunk_id e.g. chk_...
    video_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    duration: Mapped[float] = mapped_column(Float, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    segment_start_index: Mapped[int] = mapped_column(Integer, nullable=False)
    segment_end_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="chunks")
    quiz_questions: Mapped[list["QuizQuestion"]] = relationship("QuizQuestion", back_populates="source_chunk")
    flashcards: Mapped[list["Flashcard"]] = relationship("Flashcard", back_populates="source_chunk")
    learner_progress: Mapped[list["LearnerProgress"]] = relationship("LearnerProgress", back_populates="chunk")
    embeddings: Mapped[list["ChunkEmbedding"]] = relationship(
        "ChunkEmbedding", back_populates="chunk", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<KnowledgeChunk id={self.id} video={self.video_id} idx={self.chunk_index}>"


# ===========================================================================
# 6. Quiz Entity
# ===========================================================================
class Quiz(Base):
    """
    Represents an AI-generated assessment tied to a specific educational video.
    Holds questions and is linked to learner attempts for adaptive evaluation.
    """
    __tablename__ = "quizzes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # quiz_id e.g. quiz_...
    video_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="quizzes")
    questions: Mapped[list["QuizQuestion"]] = relationship(
        "QuizQuestion",
        back_populates="quiz",
        cascade="all, delete-orphan",
        order_by="QuizQuestion.question_order",
    )
    attempts: Mapped[list["QuizAttempt"]] = relationship(
        "QuizAttempt", back_populates="quiz", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Quiz id={self.id} video_id={self.video_id} title={self.title[:30]}>"


# ===========================================================================
# 7. QuizQuestion Entity
# ===========================================================================
class QuizQuestion(Base):
    """
    A single multiple-choice question within a quiz.
    
    Architectural Decisions:
    - options: Stored as a JSON array of strings (e.g. ['A', 'B', 'C', 'D']).
      Rationale: An MCQ option set is an ordered, fixed-size atomic collection
      belonging strictly to this question. An options sub-table would force 4 JOIN
      rows per question without any query optimization benefit.
    - correct_answer & explanation: Stored securely server-side.
    - source_chunk_id & source_timestamp: Enforces the source-grounding principle,
      enabling instant replay of video moments when learners make mistakes.
    """
    __tablename__ = "quiz_questions"
    __table_args__ = (
        Index("ix_quiz_questions_quiz_order", "quiz_id", "question_order"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)  # question_id e.g. q_1
    quiz_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_chunk_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("knowledge_chunks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    question_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[str]] = mapped_column(JSON, nullable=False)  # Exactly 4 distinct choices
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    source_timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    source_formatted_time: Mapped[str] = mapped_column(String(16), nullable=False)
    source_label: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    quiz: Mapped["Quiz"] = relationship("Quiz", back_populates="questions")
    source_chunk: Mapped[Optional["KnowledgeChunk"]] = relationship("KnowledgeChunk", back_populates="quiz_questions")
    answers: Mapped[list["QuizAnswer"]] = relationship(
        "QuizAnswer", back_populates="question", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<QuizQuestion id={self.id} quiz_id={self.quiz_id} order={self.question_order}>"


# ===========================================================================
# 8. QuizAttempt Entity
# ===========================================================================
class QuizAttempt(Base):
    """
    Records a completed assessment submission by a learner.
    Calculates deterministic performance metrics, assigns mastery tiers,
    and indexes weak knowledge chunks for adaptive review.
    """
    __tablename__ = "quiz_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    quiz_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False)
    score_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    performance_tier: Mapped[str] = mapped_column(String(32), nullable=False)  # Strong, Developing, Needs Revision
    performance_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    weak_chunk_ids: Mapped[list[str]] = mapped_column(JSON, nullable=True, default=list)  # list of chunk_ids
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    quiz: Mapped["Quiz"] = relationship("Quiz", back_populates="attempts")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="quiz_attempts")
    answers: Mapped[list["QuizAnswer"]] = relationship(
        "QuizAnswer", back_populates="attempt", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<QuizAttempt id={self.id} score={self.score_percentage}% tier={self.performance_tier}>"


# ===========================================================================
# 9. QuizAnswer Entity
# ===========================================================================
class QuizAnswer(Base):
    """
    Individual response chosen by a learner for a specific quiz question during an attempt.
    Guarantees one recorded answer per question per attempt via a unique constraint.
    """
    __tablename__ = "quiz_answers"
    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_quiz_answers_attempt_question"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    attempt_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("quiz_questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    selected_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    attempt: Mapped["QuizAttempt"] = relationship("QuizAttempt", back_populates="answers")
    question: Mapped["QuizQuestion"] = relationship("QuizQuestion", back_populates="answers")

    def __repr__(self) -> str:
        return f"<QuizAnswer id={self.id} correct={self.is_correct}>"


# ===========================================================================
# 10. FlashcardDeck Entity
# ===========================================================================
class FlashcardDeck(Base):
    """
    A curated collection of active-recall flashcards generated for a video.
    """
    __tablename__ = "flashcard_decks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    video_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    model_used: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="flashcard_decks")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="flashcard_decks")
    cards: Mapped[list["Flashcard"]] = relationship(
        "Flashcard",
        back_populates="deck",
        cascade="all, delete-orphan",
        order_by="Flashcard.card_order",
    )

    def __repr__(self) -> str:
        return f"<FlashcardDeck id={self.id} topic={self.topic[:30]}>"


# ===========================================================================
# 11. Flashcard Entity
# ===========================================================================
class Flashcard(Base):
    """
    A single conceptual study card featuring prompt (front) and answer (back),
    strictly grounded to a source transcript chunk and video timestamp.
    """
    __tablename__ = "flashcards"
    __table_args__ = (
        Index("ix_flashcards_deck_order", "deck_id", "card_order"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # card_1, card_2, etc.
    deck_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("flashcard_decks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_chunk_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("knowledge_chunks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    card_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    front: Mapped[str] = mapped_column(Text, nullable=False)
    back: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    source_timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    source_formatted_time: Mapped[str] = mapped_column(String(16), nullable=False)
    source_label: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    deck: Mapped["FlashcardDeck"] = relationship("FlashcardDeck", back_populates="cards")
    source_chunk: Mapped[Optional["KnowledgeChunk"]] = relationship("KnowledgeChunk", back_populates="flashcards")

    def __repr__(self) -> str:
        return f"<Flashcard id={self.id} deck_id={self.deck_id} order={self.card_order}>"


# ===========================================================================
# 12. LearnerProgress Entity
# ===========================================================================
class LearnerProgress(Base):
    """
    Tracks granular conceptual mastery per learner, per video, and per chunk.
    Enables future adaptive spaced repetition and knowledge-gap targeted review.
    """
    __tablename__ = "learner_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "video_id", "chunk_id", name="uq_learner_progress_user_video_chunk"),
        Index("ix_learner_progress_user_mastery", "user_id", "mastery_score"),
        Index("ix_learner_progress_revision", "user_id", "needs_revision"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    video_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("knowledge_chunks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    mastery_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # 0.0 to 100.0
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    needs_revision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="learner_progress")
    video: Mapped["Video"] = relationship("Video", back_populates="learner_progress")
    chunk: Mapped[Optional["KnowledgeChunk"]] = relationship("KnowledgeChunk", back_populates="learner_progress")

    def __repr__(self) -> str:
        return f"<LearnerProgress user={self.user_id} video={self.video_id} chunk={self.chunk_id} mastery={self.mastery_score}>"


# ===========================================================================
# 13. LearningRecoverySession Entity (Step 14 Phase 3)
# ===========================================================================
class LearningRecoverySession(Base):
    """
    Represents an evidence-grounded learning recovery intervention addressing
    a specific knowledge chunk where a learner demonstrated repeated weakness.
    """
    __tablename__ = "learning_recovery_sessions"
    __table_args__ = (
        Index("ix_recovery_video_chunk", "video_id", "chunk_id"),
        Index("ix_recovery_status", "status"),
        Index("ix_recovery_user", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    video_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("knowledge_chunks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    source_formatted_time: Mapped[str] = mapped_column(String(16), nullable=False)
    originating_evidence: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="CREATED", index=True)
    explanation_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    targeted_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    worked_example: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_takeaway: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    micro_quiz_data: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    pre_recovery_accuracy: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    post_recovery_accuracy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    absolute_improvement: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recovery_result: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    video: Mapped["Video"] = relationship("Video")
    chunk: Mapped["KnowledgeChunk"] = relationship("KnowledgeChunk")
    answers: Mapped[list["RecoveryQuizAnswer"]] = relationship(
        "RecoveryQuizAnswer", back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<LearningRecoverySession id={self.id} chunk={self.chunk_id} status={self.status}>"


# ===========================================================================
# 14. RecoveryQuizAnswer Entity (Step 14 Phase 3)
# ===========================================================================
class RecoveryQuizAnswer(Base):
    """
    Granular answer evaluation record for a question inside a learning recovery session.
    """
    __tablename__ = "recovery_quiz_answers"
    __table_args__ = (
        Index("ix_recovery_answers_session", "session_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_recovery_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    session: Mapped["LearningRecoverySession"] = relationship("LearningRecoverySession", back_populates="answers")

    def __repr__(self) -> str:
        return f"<RecoveryQuizAnswer session={self.session_id} q={self.question_id} correct={self.is_correct}>"


# ===========================================================================
# 15. ChunkEmbedding Entity (Step 17 - RAG + pgvector)
# ===========================================================================
class ChunkEmbedding(Base):
    """
    Stores vector embeddings for KnowledgeChunk entities using PostgreSQL pgvector.
    Enables semantic similarity search, RAG retrieval, and conceptual exploration.
    
    Architectural Decisions:
    - user_id and video_id are denormalized foreign keys for strict, query-level isolation
      without requiring multi-table joins during high-throughput vector similarity scans.
    - model_name and dimension are explicitly tracked to support seamless model transitions
      (e.g., text-embedding-004 -> future models) without breaking database assumptions.
    - UniqueConstraint('chunk_id', 'model_name') ensures idempotent indexing per model.
    """
    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        UniqueConstraint("chunk_id", "model_name", name="uq_chunk_embeddings_chunk_model"),
        Index("ix_chunk_embeddings_user_video", "user_id", "video_id"),
        Index("ix_chunk_embeddings_model", "model_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    chunk_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("knowledge_chunks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    video_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    embedding = mapped_column(Vector(settings.embedding_dimension), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False, default=settings.embedding_model)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False, default=settings.embedding_dimension)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    chunk: Mapped["KnowledgeChunk"] = relationship("KnowledgeChunk", back_populates="embeddings")
    video: Mapped["Video"] = relationship("Video")
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<ChunkEmbedding id={self.id} chunk={self.chunk_id} model={self.model_name}>"


# ===========================================================================
# 16. ChatMessage Entity (Ask VIDYORA Grounded AI Tutor)
# ===========================================================================
class ChatMessage(Base):
    """
    Stores conversational interactions between a learner and Ask VIDYORA.
    Persists the student's question, Gemini's lecture-grounded answer, source
    citations (with timestamps and chunk IDs), and model used.
    
    Security & Multi-Tenancy:
    - user_id foreign key guarantees strict tenant-level isolation.
    - video_id foreign key links conversation directly to the video context.
    - Cascades on video or user deletion.
    """
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_user_video", "user_id", "video_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    video_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    model_used: Mapped[str] = mapped_column(String(64), nullable=False, default="gemini-2.5-flash")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="chat_messages")
    user: Mapped["User"] = relationship("User", back_populates="chat_messages")

    def __repr__(self) -> str:
        return f"<ChatMessage id={self.id} video={self.video_id} user={self.user_id}>"

