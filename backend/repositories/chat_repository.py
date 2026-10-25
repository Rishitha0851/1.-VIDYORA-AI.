"""
VIDYORA AI - Chat Message Persistence Repository (Step 18)

Encapsulates database operations for Ask VIDYORA conversational messages
with strict multi-tenant user isolation and cascade deletion.
"""

from datetime import datetime, timezone
import logging
from typing import List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from db.models import ChatMessage

logger = logging.getLogger(__name__)


class ChatRepository:
    """Repository managing persistence and retrieval for student chat messages."""

    @classmethod
    def save_message(
        cls,
        db: Session,
        user_id: str,
        video_id: str,
        question: str,
        answer: str,
        sources: list[dict],
        model_used: str,
    ) -> ChatMessage:
        """
        Persists a single Q&A interaction between a student and Ask VIDYORA.
        """
        now = datetime.now(timezone.utc)
        message = ChatMessage(
            video_id=video_id,
            user_id=user_id,
            question=question,
            answer=answer,
            sources=sources,
            model_used=model_used,
            created_at=now,
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        logger.info("Persisted chat message %s for video %s and user %s.", message.id, video_id, user_id)
        return message

    @classmethod
    def get_history(
        cls,
        db: Session,
        user_id: str,
        video_id: str,
        limit: Optional[int] = None,
    ) -> List[ChatMessage]:
        """
        Retrieves all historical chat messages for a specific user and video,
        ordered chronologically ascending. Strictly enforces user isolation.
        """
        query = (
            db.query(ChatMessage)
            .filter(
                and_(
                    ChatMessage.user_id == user_id,
                    ChatMessage.video_id == video_id,
                )
            )
            .order_by(ChatMessage.created_at.asc())
        )
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    @classmethod
    def clear_history(
        cls,
        db: Session,
        user_id: str,
        video_id: str,
    ) -> int:
        """
        Clears all conversation history for a specific user and video.
        Returns the number of deleted records.
        """
        deleted_count = (
            db.query(ChatMessage)
            .filter(
                and_(
                    ChatMessage.user_id == user_id,
                    ChatMessage.video_id == video_id,
                )
            )
            .delete(synchronize_session="fetch")
        )
        db.commit()
        logger.info("Cleared %d chat messages for video %s and user %s.", deleted_count, video_id, user_id)
        return deleted_count
