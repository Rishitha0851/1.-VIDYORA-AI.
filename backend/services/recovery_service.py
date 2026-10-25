"""
VIDYORA AI - Targeted Learning Recovery Engine Service

Orchestrates evidence-grounded remediation for identified knowledge gaps:
1. Validates weak knowledge chunk and extracts baseline assessment evidence.
2. Prompts Gemini for source-grounded explanation and focused micro-quiz.
3. Persists recovery sessions with server-side answer keys.
4. Performs deterministic backend grading and before/after recovery measurement.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from db.models import KnowledgeChunk, LearningRecoverySession, Video
from models import (
    QuizDifficulty,
    QuizQuestionClient,
    RecoveryEvaluationResponse,
    RecoveryQuestionResult,
    RecoveryResultEnum,
    RecoverySessionClientView,
    RecoverySessionStatus,
    RecoverySubmitRequest,
    SourceTimestamp,
    TranscriptChunk,
)
from repositories.analytics_repository import AnalyticsRepository
from repositories.recovery_repository import RecoveryRepository
from services.gemini_service import generate_recovery_intervention
from services.knowledge_gap_service import KnowledgeGapService

logger = logging.getLogger(__name__)

# Configurable engineering heuristics for recovery decision logic
MAX_RECOVERY_ATTEMPTS = 2
MIN_QUESTIONS_FOR_DECISION = 2
RECOVERY_PASS_THRESHOLD_PCT = 75.0
IMPROVEMENT_THRESHOLD_PCT = 60.0


class RecoveryService:
    """Service encapsulating the lifecycle and deterministic evaluation of learning recovery."""

    @staticmethod
    def _chunk_to_transcript_chunk(chunk: KnowledgeChunk) -> TranscriptChunk:
        """Converts an ORM KnowledgeChunk into a Pydantic TranscriptChunk."""
        return TranscriptChunk(
            chunk_id=chunk.id,
            chunk_index=chunk.chunk_index,
            video_id=chunk.video_id,
            text=chunk.text,
            start_time=chunk.start_time,
            end_time=chunk.end_time,
            duration=chunk.duration,
            word_count=chunk.word_count,
            segment_start_index=chunk.segment_start_index,
            segment_end_index=chunk.segment_end_index,
        )

    @classmethod
    def create_recovery_session(
        cls,
        db: Session,
        video_id: str,
        chunk_id: str,
        user_id: Optional[str] = None,
        reuse_existing: bool = False,
    ) -> RecoverySessionClientView:
        """
        Initiates a targeted learning recovery session for a specific weak chunk.
        Validates weak chunk, retrieves prior assessment evidence, prompts Gemini
        for grounded explanation & micro-quiz, and saves session in PostgreSQL.
        """
        # 1. Verify Video exists and belongs to user if user_id is provided
        video_query = db.query(Video).filter(Video.id == video_id)
        if user_id:
            video_query = video_query.filter(Video.user_id == user_id)
        video = video_query.first()
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video '{video_id}' not found.",
            )

        # 2. Verify Chunk exists for this video
        chunk = (
            db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.id == chunk_id, KnowledgeChunk.video_id == video_id)
            .first()
        )
        if not chunk:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Knowledge chunk '{chunk_id}' not found in video '{video_id}'.",
            )

        # 3. If reuse_existing is True, reuse any active in-progress or completed session
        if reuse_existing:
            existing_latest = RecoveryRepository.get_latest_session_for_chunk(
                db, video_id, chunk_id, user_id=user_id
            )
            if existing_latest:
                if existing_latest.status != RecoverySessionStatus.EVALUATED.value:
                    return cls.get_recovery_session(db, existing_latest.id, user_id=user_id)
                if existing_latest.recovery_result == RecoveryResultEnum.RECOVERED.value:
                    return cls.get_recovery_session(db, existing_latest.id, user_id=user_id)

        # 4. Check attempt limit
        prior_attempts = RecoveryRepository.count_attempts_for_chunk(db, video_id, chunk_id, user_id=user_id)
        if prior_attempts >= MAX_RECOVERY_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Maximum recovery attempts ({MAX_RECOVERY_ATTEMPTS}) reached for this knowledge chunk. Please review the lecture video directly.",
            )
        attempt_number = prior_attempts + 1

        # 4. Extract originating evidence and baseline accuracy from KnowledgeGapService
        gap_response = KnowledgeGapService.analyze_video_knowledge_gaps(db, video_id, user_id=user_id)
        originating_evidence = "Learner struggled with this conceptual section on previous assessment attempts."
        pre_recovery_accuracy = 0.0

        if gap_response:
            for g in gap_response.gaps:
                if g.chunk_id == chunk_id:
                    originating_evidence = g.reason
                    pre_recovery_accuracy = round(g.accuracy * 100, 1)
                    break

        # 5. Extract narrowly related context chunks (adjacent chunks only, not full transcript)
        all_chunks = AnalyticsRepository.get_chunks_for_video(db, video_id)
        adjacent_chunks: list[TranscriptChunk] = []
        for c in all_chunks:
            if c.id != chunk.id and abs(c.chunk_index - chunk.chunk_index) <= 1:
                adjacent_chunks.append(cls._chunk_to_transcript_chunk(c))

        weak_transcript_chunk = cls._chunk_to_transcript_chunk(chunk)

        # 6. Generate targeted intervention via Gemini
        intervention, model_used = generate_recovery_intervention(
            video_title=video.title,
            weak_chunk=weak_transcript_chunk,
            context_chunks=adjacent_chunks,
            originating_evidence=originating_evidence,
            attempt_number=attempt_number,
            num_questions=3,
        )

        # 7. Create persistent session record
        session_id = str(uuid.uuid4())
        formatted_time = KnowledgeGapService.format_timestamp(chunk.start_time)

        db_session = LearningRecoverySession(
            id=session_id,
            user_id=user_id,
            video_id=video_id,
            chunk_id=chunk_id,
            source_timestamp=chunk.start_time,
            source_formatted_time=formatted_time,
            originating_evidence=originating_evidence,
            attempt_number=attempt_number,
            status=RecoverySessionStatus.QUIZ_READY.value,
            explanation_title=intervention.title,
            targeted_explanation=intervention.explanation,
            worked_example=intervention.worked_example,
            key_takeaway=intervention.key_takeaway,
            micro_quiz_data=[q.model_dump() for q in intervention.questions],
            pre_recovery_accuracy=pre_recovery_accuracy,
            total_questions=len(intervention.questions),
            correct_count=0,
        )

        persisted = RecoveryRepository.create_session(db, db_session)

        # 8. Return client view with answer keys stripped
        client_questions = [
            QuizQuestionClient(
                id=q.id,
                question=q.question,
                options=q.options,
                difficulty=q.difficulty,
                source_timestamp=q.source_timestamp,
                source_chunk_id=q.source_chunk_id,
            )
            for q in intervention.questions
        ]

        return RecoverySessionClientView(
            id=persisted.id,
            video_id=persisted.video_id,
            chunk_id=persisted.chunk_id,
            chunk_index=chunk.chunk_index,
            source_timestamp=SourceTimestamp(
                timestamp=chunk.start_time,
                formatted_time=formatted_time,
                label=f"Chunk {chunk.chunk_index + 1} ({formatted_time})",
            ),
            originating_evidence=persisted.originating_evidence,
            attempt_number=persisted.attempt_number,
            status=RecoverySessionStatus(persisted.status),
            explanation_title=persisted.explanation_title,
            targeted_explanation=persisted.targeted_explanation,
            worked_example=persisted.worked_example,
            key_takeaway=persisted.key_takeaway,
            micro_quiz=client_questions,
            pre_recovery_accuracy=persisted.pre_recovery_accuracy,
            chunk_text=chunk.text,
        )

    @classmethod
    def get_recovery_session(
        cls,
        db: Session,
        session_id: str,
        user_id: Optional[str] = None,
    ) -> RecoverySessionClientView:
        """
        Retrieves a recovery session by ID.
        If not yet evaluated, strips correct answers and explanations.
        If evaluated, includes full evaluation metrics, answers, and explanations.
        """
        session = RecoveryRepository.get_session_by_id(db, session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recovery session '{session_id}' not found.",
            )

        if user_id and session.user_id and session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this recovery session.",
            )

        chunk = (
            db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.id == session.chunk_id)
            .first()
        )
        chunk_index = chunk.chunk_index if chunk else 0
        chunk_text = chunk.text if chunk else None

        raw_questions = session.micro_quiz_data or []
        is_evaluated = session.status == RecoverySessionStatus.EVALUATED.value

        # Prepare client questions (sanitized)
        client_questions = [
            QuizQuestionClient(
                id=q["id"],
                question=q["question"],
                options=q["options"],
                difficulty=QuizDifficulty(q.get("difficulty", "medium")),
                source_timestamp=SourceTimestamp(**q["source_timestamp"]),
                source_chunk_id=q.get("source_chunk_id"),
            )
            for q in raw_questions
        ]

        question_results: list[RecoveryQuestionResult] = []
        if is_evaluated:
            answer_map = {a.question_id: a for a in session.answers}
            for q in raw_questions:
                ans = answer_map.get(q["id"])
                question_results.append(
                    RecoveryQuestionResult(
                        question_id=q["id"],
                        question=q["question"],
                        selected_answer=ans.selected_answer if ans else None,
                        correct_answer=q["correct_answer"],
                        is_correct=ans.is_correct if ans else False,
                        explanation=q["explanation"],
                        source_timestamp=SourceTimestamp(**q["source_timestamp"]),
                    )
                )

        can_retry = (
            is_evaluated
            and session.recovery_result != RecoveryResultEnum.RECOVERED.value
            and session.attempt_number < MAX_RECOVERY_ATTEMPTS
        )

        recovery_res_enum = (
            RecoveryResultEnum(session.recovery_result)
            if session.recovery_result
            else None
        )

        result_summary = None
        if is_evaluated and session.post_recovery_accuracy is not None:
            result_summary = cls._generate_result_summary(
                recovery_result=recovery_res_enum or RecoveryResultEnum.NOT_RECOVERED,
                correct_count=session.correct_count,
                total_questions=session.total_questions,
                post_accuracy=session.post_recovery_accuracy,
                pre_accuracy=session.pre_recovery_accuracy,
                abs_improvement=session.absolute_improvement or 0.0,
            )

        return RecoverySessionClientView(
            id=session.id,
            video_id=session.video_id,
            chunk_id=session.chunk_id,
            chunk_index=chunk_index,
            source_timestamp=SourceTimestamp(
                timestamp=session.source_timestamp,
                formatted_time=session.source_formatted_time,
                label=f"Chunk {chunk_index + 1} ({session.source_formatted_time})",
            ),
            originating_evidence=session.originating_evidence,
            attempt_number=session.attempt_number,
            status=RecoverySessionStatus(session.status),
            explanation_title=session.explanation_title,
            targeted_explanation=session.targeted_explanation,
            worked_example=session.worked_example,
            key_takeaway=session.key_takeaway,
            micro_quiz=client_questions,
            pre_recovery_accuracy=session.pre_recovery_accuracy,
            chunk_text=chunk_text,
            post_recovery_accuracy=session.post_recovery_accuracy,
            absolute_improvement=session.absolute_improvement,
            recovery_result=recovery_res_enum,
            result_summary=result_summary,
            question_results=question_results,
            can_retry=can_retry,
            evaluated_at=session.evaluated_at.isoformat() if session.evaluated_at else None,
        )

    @classmethod
    def evaluate_recovery_session(
        cls,
        db: Session,
        session_id: str,
        request: RecoverySubmitRequest,
        user_id: Optional[str] = None,
    ) -> RecoveryEvaluationResponse:
        """
        Deterministically evaluates a submitted recovery micro-quiz on the backend.
        Gemini is NOT involved in scoring, correctness, or recovery decisions.
        """
        session = RecoveryRepository.get_session_by_id(db, session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recovery session '{session_id}' not found.",
            )

        if user_id and session.user_id and session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this recovery session.",
            )

        if session.status == RecoverySessionStatus.EVALUATED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This recovery session has already been submitted and evaluated.",
            )

        raw_questions = session.micro_quiz_data or []
        if not raw_questions:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Recovery session has no micro-quiz questions to evaluate.",
            )

        question_map = {q["id"]: q for q in raw_questions}

        # Validate submitted answer keys
        for q_id, chosen in request.selected_answers.items():
            if q_id not in question_map:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Question '{q_id}' does not belong to this recovery session.",
                )
            if chosen not in question_map[q_id]["options"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Selected answer for question '{q_id}' is not among the valid options.",
                )

        # 1. Deterministic scoring
        total_questions = len(raw_questions)
        correct_count = 0
        question_results: list[RecoveryQuestionResult] = []
        answers_for_db: list[dict] = []

        for q in raw_questions:
            qid = q["id"]
            chosen = request.selected_answers.get(qid)
            is_correct = (chosen == q["correct_answer"]) if chosen is not None else False
            if is_correct:
                correct_count += 1

            question_results.append(
                RecoveryQuestionResult(
                    question_id=qid,
                    question=q["question"],
                    selected_answer=chosen,
                    correct_answer=q["correct_answer"],
                    is_correct=is_correct,
                    explanation=q["explanation"],
                    source_timestamp=SourceTimestamp(**q["source_timestamp"]),
                )
            )

            answers_for_db.append({
                "question_id": qid,
                "selected_answer": chosen,
                "is_correct": is_correct,
            })

        post_recovery_accuracy = (
            round((correct_count / total_questions) * 100, 1)
            if total_questions > 0
            else 0.0
        )
        pre_recovery_accuracy = session.pre_recovery_accuracy
        absolute_improvement = round(post_recovery_accuracy - pre_recovery_accuracy, 1)

        # 2. Deterministic recovery classification rule
        recovery_result = cls._compute_recovery_decision(
            total_questions=total_questions,
            post_accuracy=post_recovery_accuracy,
            pre_accuracy=pre_recovery_accuracy,
        )

        result_summary = cls._generate_result_summary(
            recovery_result=recovery_result,
            correct_count=correct_count,
            total_questions=total_questions,
            post_accuracy=post_recovery_accuracy,
            pre_accuracy=pre_recovery_accuracy,
            abs_improvement=absolute_improvement,
        )

        can_retry = (
            recovery_result != RecoveryResultEnum.RECOVERED
            and session.attempt_number < MAX_RECOVERY_ATTEMPTS
        )

        # 3. Persist evaluation atomically in PostgreSQL
        persisted = RecoveryRepository.record_evaluation(
            db=db,
            session_id=session_id,
            post_recovery_accuracy=post_recovery_accuracy,
            absolute_improvement=absolute_improvement,
            total_questions=total_questions,
            correct_count=correct_count,
            recovery_result=recovery_result.value,
            answers=answers_for_db,
        )

        now_str = (
            persisted.evaluated_at.isoformat()
            if persisted and persisted.evaluated_at
            else datetime.now(timezone.utc).isoformat()
        )

        return RecoveryEvaluationResponse(
            session_id=session_id,
            video_id=session.video_id,
            chunk_id=session.chunk_id,
            attempt_number=session.attempt_number,
            total_questions=total_questions,
            correct_count=correct_count,
            pre_recovery_accuracy=pre_recovery_accuracy,
            post_recovery_accuracy=post_recovery_accuracy,
            absolute_improvement=absolute_improvement,
            recovery_result=recovery_result,
            result_summary=result_summary,
            question_results=question_results,
            can_retry=can_retry,
            evaluated_at=now_str,
        )

    @staticmethod
    def _compute_recovery_decision(
        total_questions: int,
        post_accuracy: float,
        pre_accuracy: float,
    ) -> RecoveryResultEnum:
        """
        Applies transparent, configurable engineering heuristics to determine recovery outcome.
        
        Rules:
        - INSUFFICIENT_EVIDENCE: < 2 questions answered.
        - RECOVERED: post_accuracy >= 75% AND (pre_accuracy < 75% OR post_accuracy >= pre_accuracy).
        - IMPROVED: post_accuracy >= 60% AND post_accuracy > pre_accuracy (but < 75%).
        - NOT_RECOVERED: post_accuracy < 60% OR post_accuracy <= pre_accuracy.
        """
        if total_questions < MIN_QUESTIONS_FOR_DECISION:
            return RecoveryResultEnum.INSUFFICIENT_EVIDENCE

        if post_accuracy >= RECOVERY_PASS_THRESHOLD_PCT and (
            pre_accuracy < RECOVERY_PASS_THRESHOLD_PCT or post_accuracy >= pre_accuracy
        ):
            return RecoveryResultEnum.RECOVERED

        if post_accuracy >= IMPROVEMENT_THRESHOLD_PCT and post_accuracy > pre_accuracy:
            return RecoveryResultEnum.IMPROVED

        return RecoveryResultEnum.NOT_RECOVERED

    @staticmethod
    def _generate_result_summary(
        recovery_result: RecoveryResultEnum,
        correct_count: int,
        total_questions: int,
        post_accuracy: float,
        pre_accuracy: float,
        abs_improvement: float,
    ) -> str:
        """Generates honest, explainable outcome summary avoiding exaggerated claims of mastery."""
        if recovery_result == RecoveryResultEnum.INSUFFICIENT_EVIDENCE:
            return (
                f"Fewer than {MIN_QUESTIONS_FOR_DECISION} questions evaluated ({correct_count}/{total_questions}). "
                "Insufficient evidence to verify conceptual recovery."
            )

        if recovery_result == RecoveryResultEnum.RECOVERED:
            delta_str = f"+{abs_improvement}%" if abs_improvement > 0 else "0%"
            return (
                f"Recovery Verified: Scored {correct_count}/{total_questions} ({post_accuracy}%, {delta_str} over baseline {pre_accuracy}%). "
                f"Surpassed the {int(RECOVERY_PASS_THRESHOLD_PCT)}% recovery threshold."
            )

        if recovery_result == RecoveryResultEnum.IMPROVED:
            return (
                f"Performance Improved: Scored {correct_count}/{total_questions} ({post_accuracy}%, +{abs_improvement}% over baseline {pre_accuracy}%). "
                f"Showed meaningful progress but fell short of the {int(RECOVERY_PASS_THRESHOLD_PCT)}% threshold."
            )

        return (
            f"Not Recovered: Scored {correct_count}/{total_questions} ({post_accuracy}% vs baseline {pre_accuracy}%). "
            "We recommend re-watching this specific video section."
        )

    @classmethod
    def get_chunk_recovery_history(
        cls,
        db: Session,
        video_id: str,
        chunk_id: str,
        user_id: Optional[str] = None,
    ) -> list[RecoverySessionClientView]:
        """Returns all past recovery attempts for a specific knowledge chunk."""
        sessions = RecoveryRepository.get_sessions_for_chunk(db, video_id, chunk_id, user_id=user_id)
        views = []
        for s in sessions:
            views.append(cls.get_recovery_session(db, s.id, user_id=user_id))
        return views

    @classmethod
    def get_latest_session_for_chunk(
        cls,
        db: Session,
        video_id: str,
        chunk_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[RecoverySessionClientView]:
        """Returns the most recent recovery session for a specific knowledge chunk."""
        session = RecoveryRepository.get_latest_session_for_chunk(
            db, video_id, chunk_id, user_id=user_id
        )
        if not session:
            return None
        return cls.get_recovery_session(db, session.id, user_id=user_id)

