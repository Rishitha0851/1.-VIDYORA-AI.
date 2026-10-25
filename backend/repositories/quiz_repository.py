"""
VIDYORA AI - Quiz Persistence Repository

Encapsulates database operations for Quiz, QuizQuestion, QuizAttempt, and QuizAnswer
entities with transaction safety, source grounding, and server-side answer key protection.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session, joinedload, selectinload

from db.models import KnowledgeChunk, Quiz, QuizAnswer, QuizAttempt, QuizQuestion, Video
from models import GeneratedQuizInternal
from repositories.video_repository import VideoRepository

logger = logging.getLogger(__name__)


class QuizRepository:
    """Repository managing persistence for quizzes, questions, attempts, and answers."""

    @staticmethod
    def get_quiz_by_id(db: Session, quiz_id: str, user_id: Optional[str] = None) -> Optional[Quiz]:
        """
        Retrieves a quiz by ID including all associated questions ordered by question_order.
        Enforces user ownership via Video relationship if user_id is provided.
        Uses joinedload to eliminate N+1 query overhead.
        """
        query = (
            db.query(Quiz)
            .options(joinedload(Quiz.questions))
            .filter(Quiz.id == quiz_id)
        )
        if user_id is not None:
            query = query.join(Video, Quiz.video_id == Video.id).filter(Video.user_id == user_id)
        return query.first()

    @staticmethod
    def quiz_exists(db: Session, quiz_id: str, user_id: Optional[str] = None) -> bool:
        """Checks if a quiz with the given ID exists in the database and belongs to user_id."""
        query = db.query(Quiz.id).filter(Quiz.id == quiz_id)
        if user_id is not None:
            query = query.join(Video, Quiz.video_id == Video.id).filter(Video.user_id == user_id)
        return query.first() is not None

    @staticmethod
    def get_quiz_attempts(db: Session, quiz_id: str, user_id: Optional[str] = None) -> list[QuizAttempt]:
        """
        Retrieves all historical attempts for a quiz ordered chronologically descending.
        Enforces user isolation when user_id is provided.
        Uses selectinload on answers to avoid N+1 queries.
        """
        query = (
            db.query(QuizAttempt)
            .options(selectinload(QuizAttempt.answers))
            .filter(QuizAttempt.quiz_id == quiz_id)
        )
        if user_id is not None:
            query = query.filter(QuizAttempt.user_id == user_id)
        return (
            query
            .order_by(QuizAttempt.created_at.desc())
            .all()
        )


    @staticmethod
    def save_quiz(
        db: Session,
        internal_quiz: GeneratedQuizInternal,
        model_used: str,
        user_id: Optional[str] = None,
    ) -> Quiz:
        """
        Persists a newly generated quiz with full answer key and rationales to PostgreSQL.
        
        Security Guarantee:
        correct_answer and explanation are stored in PostgreSQL on QuizQuestion and
        are NEVER serialized to the client-facing QuizResponse.
        """
        now = datetime.now(timezone.utc)
        try:
            # 1. Ensure foreign-key parent video exists
            VideoRepository.ensure_video_stub(db, internal_quiz.video_id, title=internal_quiz.title, user_id=user_id)

            # 2. Check if quiz already exists (idempotency)
            quiz = db.query(Quiz).filter(Quiz.id == internal_quiz.quiz_id).first()
            if not quiz:
                quiz = Quiz(
                    id=internal_quiz.quiz_id,
                    video_id=internal_quiz.video_id,
                    title=internal_quiz.title,
                    instructions=internal_quiz.instructions,
                    model_used=model_used,
                    created_at=now,
                )
                db.add(quiz)
                db.flush()
            else:
                quiz.video_id = internal_quiz.video_id
                quiz.title = internal_quiz.title
                quiz.instructions = internal_quiz.instructions
                quiz.model_used = model_used
                db.query(QuizQuestion).filter(QuizQuestion.quiz_id == quiz.id).delete()
                db.flush()

            # 3. Persist Quiz Questions
            questions_to_add = []
            for order, q in enumerate(internal_quiz.questions, start=1):
                # Ensure source_chunk_id exists before setting FK to guarantee referential integrity
                valid_chunk_id = None
                if q.source_chunk_id:
                    chunk_exists = db.query(KnowledgeChunk).filter(KnowledgeChunk.id == q.source_chunk_id).first()
                    if not chunk_exists:
                        from sqlalchemy import func
                        max_idx = db.query(func.max(KnowledgeChunk.chunk_index)).filter(KnowledgeChunk.video_id == internal_quiz.video_id).scalar()
                        next_idx = 0 if max_idx is None else max_idx + 1
                        stub_chunk = KnowledgeChunk(
                            id=q.source_chunk_id,
                            video_id=internal_quiz.video_id,
                            chunk_index=next_idx,
                            text=f"Knowledge context for {q.source_chunk_id}",
                            start_time=q.source_timestamp.timestamp,
                            end_time=q.source_timestamp.timestamp + 30.0,
                            duration=30.0,
                            word_count=5,
                            segment_start_index=0,
                            segment_end_index=0,
                            created_at=now,
                        )
                        db.add(stub_chunk)
                        db.flush()
                    valid_chunk_id = q.source_chunk_id

                difficulty_val = q.difficulty.value if hasattr(q.difficulty, "value") else str(q.difficulty)
                db_question_id = f"{quiz.id}_{q.id}" if not q.id.startswith(f"{quiz.id}_") else q.id
                if len(db_question_id) > 128:
                    db_question_id = db_question_id[:128]

                questions_to_add.append(
                    QuizQuestion(
                        id=db_question_id,
                        quiz_id=quiz.id,
                        source_chunk_id=valid_chunk_id,
                        question_order=order,
                        question_text=q.question,
                        options=q.options,
                        correct_answer=q.correct_answer,
                        explanation=q.explanation,
                        difficulty=difficulty_val,
                        source_timestamp=q.source_timestamp.timestamp,
                        source_formatted_time=q.source_timestamp.formatted_time,
                        source_label=q.source_timestamp.label,
                        created_at=now,
                    )
                )

            db.add_all(questions_to_add)
            db.commit()
            db.refresh(quiz)
            logger.info("Persisted quiz %s with %d questions.", quiz.id, len(questions_to_add))
            return quiz

        except Exception as exc:
            db.rollback()
            logger.error("Failed to persist quiz %s: %s", internal_quiz.quiz_id, exc)
            raise

    @staticmethod
    def save_quiz_attempt(
        db: Session,
        quiz_id: str,
        total_questions: int,
        correct_count: int,
        score_percentage: float,
        performance_tier: str,
        performance_summary: str,
        weak_chunk_ids: list[str],
        question_answers: list[dict],
        user_id: Optional[str] = None,
    ) -> QuizAttempt:
        """
        Persists a completed quiz evaluation attempt alongside individual answer choices.
        Guarantees that learner submissions survive backend restarts and state resets.
        """
        now = datetime.now(timezone.utc)
        try:
            attempt = QuizAttempt(
                quiz_id=quiz_id,
                user_id=user_id,
                total_questions=total_questions,
                correct_count=correct_count,
                score_percentage=score_percentage,
                performance_tier=performance_tier,
                performance_summary=performance_summary,
                weak_chunk_ids=weak_chunk_ids,
                created_at=now,
            )
            db.add(attempt)
            db.flush()

            # Record individual answer submissions
            answers_to_add = []
            for qa in question_answers:
                answers_to_add.append(
                    QuizAnswer(
                        attempt_id=attempt.id,
                        question_id=qa["question_id"],
                        selected_answer=qa.get("selected_answer"),
                        is_correct=qa["is_correct"],
                        created_at=now,
                    )
                )

            db.add_all(answers_to_add)
            db.commit()
            db.refresh(attempt)
            logger.info("Persisted quiz attempt %s for quiz %s with score %.1f%%.", attempt.id, quiz_id, score_percentage)
            return attempt

        except Exception as exc:
            db.rollback()
            logger.error("Failed to persist quiz attempt for quiz %s: %s", quiz_id, exc)
            raise
