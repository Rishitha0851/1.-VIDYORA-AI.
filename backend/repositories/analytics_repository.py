"""
VIDYORA AI - Analytics Persistence Repository

Executes optimized SQL queries to retrieve chunk-level assessment observations
and historical answer streams from PostgreSQL without N+1 query overhead.
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import KnowledgeChunk, QuizAnswer, QuizAttempt, QuizQuestion, Video

logger = logging.getLogger(__name__)


class AnalyticsRepository:
    """Repository handling SQL queries for learner performance and knowledge gap analysis."""

    @staticmethod
    def get_chunks_for_video(db: Session, video_id: str, user_id: Optional[str] = None) -> list[KnowledgeChunk]:
        """
        Retrieves all knowledge chunks for a given video ordered by chunk_index.
        Enforces user ownership if user_id is provided.
        """
        stmt = select(KnowledgeChunk).filter(KnowledgeChunk.video_id == video_id)
        if user_id is not None:
            stmt = stmt.join(Video, KnowledgeChunk.video_id == Video.id).filter(Video.user_id == user_id)
        stmt = stmt.order_by(KnowledgeChunk.chunk_index.asc())
        return list(db.scalars(stmt).all())

    @staticmethod
    def video_exists(db: Session, video_id: str, user_id: Optional[str] = None) -> bool:
        """Checks if a video with the specified ID exists in the database and is owned by user_id."""
        query = db.query(Video.id).filter(Video.id == video_id)
        if user_id is not None:
            query = query.filter(Video.user_id == user_id)
        return query.first() is not None

    @staticmethod
    def get_chunk_answer_observations_for_video(
        db: Session,
        video_id: str,
        user_id: Optional[str] = None,
    ) -> list[dict]:
        """
        Retrieves chronological learner answer events for questions grounded in
        knowledge chunks belonging to the specified video.
        
        Ordered by attempt creation timestamp ascending to guarantee proper
        longitudinal trajectory and trend derivation.
        """
        stmt = (
            select(
                QuizQuestion.source_chunk_id,
                QuizAnswer.is_correct,
                QuizAnswer.selected_answer,
                QuizAttempt.id.label("attempt_id"),
                QuizAttempt.created_at.label("attempt_created_at"),
                QuizAttempt.user_id.label("user_id"),
            )
            .join(QuizQuestion, QuizQuestion.id == QuizAnswer.question_id)
            .join(QuizAttempt, QuizAttempt.id == QuizAnswer.attempt_id)
            .join(KnowledgeChunk, KnowledgeChunk.id == QuizQuestion.source_chunk_id)
            .filter(KnowledgeChunk.video_id == video_id)
            .filter(QuizQuestion.source_chunk_id.is_not(None))
        )

        if user_id:
            stmt = stmt.filter(QuizAttempt.user_id == user_id)

        stmt = stmt.order_by(QuizAttempt.created_at.asc(), QuizAnswer.created_at.asc())
        rows = db.execute(stmt).all()

        return [
            {
                "chunk_id": row.source_chunk_id,
                "is_correct": bool(row.is_correct),
                "selected_answer": row.selected_answer,
                "is_unanswered": row.selected_answer is None or str(row.selected_answer).strip() == "",
                "attempt_id": str(row.attempt_id),
                "created_at": row.attempt_created_at,
                "user_id": row.user_id,
            }
            for row in rows
        ]

    @staticmethod
    def get_all_chunk_answer_observations(
        db: Session,
        user_id: Optional[str] = None,
    ) -> tuple[list[KnowledgeChunk], list[dict]]:
        """
        Retrieves all assessed knowledge chunks and their chronological answer events
        across all videos (optionally scoped to a user).
        """
        obs_stmt = (
            select(
                QuizQuestion.source_chunk_id,
                QuizAnswer.is_correct,
                QuizAnswer.selected_answer,
                QuizAttempt.id.label("attempt_id"),
                QuizAttempt.created_at.label("attempt_created_at"),
                QuizAttempt.user_id.label("user_id"),
                KnowledgeChunk.video_id.label("video_id"),
            )
            .join(QuizQuestion, QuizQuestion.id == QuizAnswer.question_id)
            .join(QuizAttempt, QuizAttempt.id == QuizAnswer.attempt_id)
            .join(KnowledgeChunk, KnowledgeChunk.id == QuizQuestion.source_chunk_id)
            .filter(QuizQuestion.source_chunk_id.is_not(None))
        )

        if user_id:
            obs_stmt = obs_stmt.filter(QuizAttempt.user_id == user_id)

        obs_stmt = obs_stmt.order_by(QuizAttempt.created_at.asc(), QuizAnswer.created_at.asc())
        obs_rows = db.execute(obs_stmt).all()

        chunk_ids = list({row.source_chunk_id for row in obs_rows})
        chunks: list[KnowledgeChunk] = []
        if chunk_ids:
            chunk_stmt = (
                select(KnowledgeChunk)
                .filter(KnowledgeChunk.id.in_(chunk_ids))
                .order_by(KnowledgeChunk.video_id.asc(), KnowledgeChunk.chunk_index.asc())
            )
            chunks = list(db.scalars(chunk_stmt).all())

        observations = [
            {
                "chunk_id": row.source_chunk_id,
                "is_correct": bool(row.is_correct),
                "selected_answer": row.selected_answer,
                "is_unanswered": row.selected_answer is None or str(row.selected_answer).strip() == "",
                "attempt_id": str(row.attempt_id),
                "created_at": row.attempt_created_at,
                "user_id": row.user_id,
                "video_id": row.video_id,
            }
            for row in obs_rows
        ]

        return chunks, observations
