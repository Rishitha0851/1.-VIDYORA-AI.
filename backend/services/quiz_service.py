"""
VIDYORA AI - Quiz History & Analytics Service

Coordinates business logic for retrieving historical learner quiz attempts
and tracking performance progression without exposing server-held answer keys.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from models import (
    PerformanceTier,
    QuizAttemptAnswerHistory,
    QuizAttemptHistoryItem,
    QuizAttemptHistoryResponse,
)
from repositories.quiz_repository import QuizRepository

logger = logging.getLogger(__name__)


class QuizService:
    """Service layer managing historical quiz evaluations and learner analytics."""

    @staticmethod
    def get_quiz_attempts(db: Session, quiz_id: str, user_id: Optional[str] = None) -> Optional[QuizAttemptHistoryResponse]:
        """
        Retrieves all historical attempts for the specified quiz_id.
        Enforces user ownership when user_id is provided.
        
        Returns:
            - None if the quiz does not exist in the database or does not belong to user (API maps to 404).
            - QuizAttemptHistoryResponse with an empty list if the quiz exists but has 0 attempts (200 OK).
            - QuizAttemptHistoryResponse with attempts ordered chronologically descending.
        """
        if not QuizRepository.quiz_exists(db, quiz_id, user_id=user_id):
            return None

        attempts = QuizRepository.get_quiz_attempts(db, quiz_id, user_id=user_id)
        history_items = []

        for att in attempts:
            tier_val = (
                PerformanceTier(att.performance_tier)
                if att.performance_tier in [t.value for t in PerformanceTier]
                else PerformanceTier.DEVELOPING
            )

            answer_records = []
            for ans in att.answers:
                # Strip quiz prefix for client-facing question_id representation
                clean_q_id = (
                    ans.question_id.replace(f"{quiz_id}_", "", 1)
                    if ans.question_id.startswith(f"{quiz_id}_")
                    else ans.question_id
                )
                answer_records.append(
                    QuizAttemptAnswerHistory(
                        question_id=clean_q_id,
                        selected_answer=ans.selected_answer,
                        is_correct=ans.is_correct,
                    )
                )

            history_items.append(
                QuizAttemptHistoryItem(
                    attempt_id=att.id,
                    quiz_id=att.quiz_id,
                    score=att.correct_count,
                    total_questions=att.total_questions,
                    score_percentage=att.score_percentage,
                    performance_tier=tier_val,
                    performance_summary=att.performance_summary,
                    weak_chunk_ids=att.weak_chunk_ids or [],
                    submitted_at=att.created_at.isoformat() if att.created_at else "",
                    answers=answer_records,
                )
            )

        return QuizAttemptHistoryResponse(
            quiz_id=quiz_id,
            total_attempts=len(history_items),
            attempts=history_items,
        )
