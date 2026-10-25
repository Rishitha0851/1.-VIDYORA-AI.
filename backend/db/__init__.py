"""
VIDYORA AI - Database Package Initialization

Central registry re-exporting Base, session factory, engine, and all 12 ORM entities.
"""

from db.base import Base
from db.models import (
    Flashcard,
    FlashcardDeck,
    KnowledgeChunk,
    LearnerProgress,
    LearningRecoverySession,
    Quiz,
    QuizAnswer,
    QuizAttempt,
    QuizQuestion,
    RecoveryQuizAnswer,
    TranscriptSegment,
    User,
    Video,
    VideoTranscript,
)
from db.session import SessionLocal, check_db_connection, create_app_engine, engine, get_db

__all__ = [
    "Base",
    "engine",
    "create_app_engine",
    "SessionLocal",
    "get_db",
    "check_db_connection",
    "User",
    "Video",
    "VideoTranscript",
    "TranscriptSegment",
    "KnowledgeChunk",
    "Quiz",
    "QuizQuestion",
    "QuizAttempt",
    "QuizAnswer",
    "FlashcardDeck",
    "Flashcard",
    "LearnerProgress",
    "LearningRecoverySession",
    "RecoveryQuizAnswer",
]
