"""
VIDYORA AI - Learning Recovery Persistence Repository

Encapsulates database operations for LearningRecoverySession and RecoveryQuizAnswer
entities with transaction safety, source grounding, and server-side answer key protection.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload

from db.models import LearnerProgress, LearningRecoverySession, RecoveryQuizAnswer

logger = logging.getLogger(__name__)


class RecoveryRepository:
    """Repository managing persistence for learning recovery interventions and micro-assessments."""

    @staticmethod
    def get_session_by_id(db: Session, session_id: str, user_id: Optional[str] = None) -> Optional[LearningRecoverySession]:
        """
        Retrieves a recovery session by ID including associated answers.
        Enforces user ownership when user_id is provided.
        Uses selectinload on answers to avoid N+1 queries.
        """
        stmt = (
            select(LearningRecoverySession)
            .options(selectinload(LearningRecoverySession.answers))
            .filter(LearningRecoverySession.id == session_id)
        )
        if user_id is not None:
            stmt = stmt.filter(LearningRecoverySession.user_id == user_id)
        return db.scalars(stmt).first()

    @staticmethod
    def get_sessions_for_chunk(
        db: Session,
        video_id: str,
        chunk_id: str,
        user_id: Optional[str] = None,
    ) -> list[LearningRecoverySession]:
        """
        Retrieves all recovery sessions for a given video knowledge chunk ordered by created_at desc.
        """
        stmt = (
            select(LearningRecoverySession)
            .options(selectinload(LearningRecoverySession.answers))
            .filter(
                LearningRecoverySession.video_id == video_id,
                LearningRecoverySession.chunk_id == chunk_id,
            )
        )
        if user_id:
            stmt = stmt.filter(LearningRecoverySession.user_id == user_id)

        stmt = stmt.order_by(
            LearningRecoverySession.attempt_number.desc(),
            LearningRecoverySession.created_at.desc(),
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def count_attempts_for_chunk(
        db: Session,
        video_id: str,
        chunk_id: str,
        user_id: Optional[str] = None,
    ) -> int:
        """
        Returns the number of prior recovery sessions created for this knowledge chunk.
        """
        stmt = (
            select(func.count(LearningRecoverySession.id))
            .filter(
                LearningRecoverySession.video_id == video_id,
                LearningRecoverySession.chunk_id == chunk_id,
            )
        )
        if user_id:
            stmt = stmt.filter(LearningRecoverySession.user_id == user_id)

        return db.scalar(stmt) or 0

    @staticmethod
    def get_latest_recovery_result_for_chunk(
        db: Session,
        video_id: str,
        chunk_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Retrieves the most recent recovery_result (e.g. 'RECOVERED') for an evaluated session.
        """
        stmt = (
            select(LearningRecoverySession.recovery_result)
            .filter(
                LearningRecoverySession.video_id == video_id,
                LearningRecoverySession.chunk_id == chunk_id,
                LearningRecoverySession.status == "EVALUATED",
            )
        )
        if user_id:
            stmt = stmt.filter(LearningRecoverySession.user_id == user_id)

        stmt = stmt.order_by(LearningRecoverySession.evaluated_at.desc())
        return db.scalars(stmt).first()

    @staticmethod
    def get_latest_session_for_chunk(
        db: Session,
        video_id: str,
        chunk_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[LearningRecoverySession]:
        """
        Retrieves the most recent recovery session for a knowledge chunk,
        whether in progress (QUIZ_READY) or evaluated.
        """
        stmt = (
            select(LearningRecoverySession)
            .options(selectinload(LearningRecoverySession.answers))
            .filter(
                LearningRecoverySession.video_id == video_id,
                LearningRecoverySession.chunk_id == chunk_id,
            )
        )
        if user_id:
            stmt = stmt.filter(LearningRecoverySession.user_id == user_id)

        stmt = stmt.order_by(
            LearningRecoverySession.attempt_number.desc(),
            LearningRecoverySession.created_at.desc(),
        )
        return db.scalars(stmt).first()

    @staticmethod
    def create_session(
        db: Session,
        session: LearningRecoverySession,
    ) -> LearningRecoverySession:
        """
        Persists a newly created recovery session in PostgreSQL inside an atomic transaction.
        """
        try:
            db.add(session)
            db.commit()
            db.refresh(session)
            return session
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def record_evaluation(
        db: Session,
        session_id: str,
        post_recovery_accuracy: float,
        absolute_improvement: float,
        total_questions: int,
        correct_count: int,
        recovery_result: str,
        answers: list[dict],
    ) -> Optional[LearningRecoverySession]:
        """
        Atomically records grading evaluation and learner answers for a recovery session.
        Also synchronizes conceptual progress in learner_progress.
        Guarantees that evaluation, answers, and progress rows are committed together.
        """
        now = datetime.now(timezone.utc)
        try:
            session = db.query(LearningRecoverySession).filter(
                LearningRecoverySession.id == session_id
            ).first()

            if not session:
                return None

            session.status = "EVALUATED"
            session.post_recovery_accuracy = post_recovery_accuracy
            session.absolute_improvement = absolute_improvement
            session.total_questions = total_questions
            session.correct_count = correct_count
            session.recovery_result = recovery_result
            session.evaluated_at = now

            # Insert answers
            for ans in answers:
                answer_obj = RecoveryQuizAnswer(
                    session_id=session_id,
                    question_id=ans["question_id"],
                    selected_answer=ans.get("selected_answer"),
                    is_correct=ans["is_correct"],
                    created_at=now,
                )
                db.add(answer_obj)

            # Atomically update or insert LearnerProgress
            if session.user_id and session.video_id:
                lp = db.query(LearnerProgress).filter(
                    LearnerProgress.user_id == session.user_id,
                    LearnerProgress.video_id == session.video_id,
                    LearnerProgress.chunk_id == session.chunk_id,
                ).first()
                if lp:
                    lp.mastery_score = post_recovery_accuracy
                    lp.review_count += 1
                    lp.last_reviewed_at = now
                    lp.needs_revision = (recovery_result == "NOT_RECOVERED")
                else:
                    lp = LearnerProgress(
                        user_id=session.user_id,
                        video_id=session.video_id,
                        chunk_id=session.chunk_id,
                        mastery_score=post_recovery_accuracy,
                        review_count=1,
                        last_reviewed_at=now,
                        needs_revision=(recovery_result == "NOT_RECOVERED"),
                    )
                    db.add(lp)

            db.commit()
            db.refresh(session)
            return session
        except Exception:
            db.rollback()
            raise
