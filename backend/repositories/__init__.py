"""
VIDYORA AI - Repositories Package Initialization

Re-exports repository classes for clean access across API and service layers.
"""

from repositories.analytics_repository import AnalyticsRepository
from repositories.chat_repository import ChatRepository
from repositories.flashcard_repository import FlashcardRepository
from repositories.quiz_repository import QuizRepository
from repositories.recovery_repository import RecoveryRepository
from repositories.video_repository import VideoRepository

__all__ = [
    "VideoRepository",
    "QuizRepository",
    "FlashcardRepository",
    "AnalyticsRepository",
    "RecoveryRepository",
    "ChatRepository",
]


