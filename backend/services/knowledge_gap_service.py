"""
VIDYORA AI - Deterministic Learner Knowledge Gap Engine

Analyzes chronological quiz assessment outcomes to identify persistent conceptual
weaknesses, emerging gaps, and mastery trajectories at the knowledge-chunk level.
Strictly deterministic, explainable, and free of external LLM dependencies.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from db.models import KnowledgeChunk
from models import (
    ChunkKnowledgeGap,
    KnowledgeGapClassification,
    LearnerOverallKnowledgeGapsResponse,
    PerformanceTrend,
    SourceTimestamp,
    VideoKnowledgeGapsResponse,
    VideoKnowledgeGapSummary,
)
from repositories.analytics_repository import AnalyticsRepository
from repositories.recovery_repository import RecoveryRepository

logger = logging.getLogger(__name__)


class KnowledgeGapService:
    """
    Deterministic domain service calculating chunk-level learner performance
    and explainable knowledge gap profiles from historical quiz attempts.
    """

    @staticmethod
    def format_timestamp(seconds: float) -> str:
        """Converts floating point seconds into MM:SS notation."""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"

    @staticmethod
    def compute_chunk_metrics(observations: list[dict]) -> dict:
        """
        Derives granular assessment performance metrics from a chronological
        sequence of learner answer observations for a single chunk.
        
        Args:
            observations: Chronologically sorted list of dicts:
                          [{"is_correct": bool, "attempt_id": str, "created_at": datetime}, ...]
        """
        total = len(observations)
        if total == 0:
            return {
                "total_observations": 0,
                "correct_count": 0,
                "incorrect_count": 0,
                "unanswered_count": 0,
                "accuracy": 0.0,
                "confidence_level": "None (0 observations)",
                "distinct_attempts_count": 0,
                "most_recent_result": None,
                "most_recent_attempt_at": None,
                "consecutive_incorrect_count": 0,
                "consecutive_correct_count": 0,
                "has_demonstrated_mastery": False,
            }

        correct_count = sum(1 for o in observations if o["is_correct"])
        unanswered_count = sum(1 for o in observations if o.get("is_unanswered"))
        incorrect_count = sum(
            1 for o in observations if not o["is_correct"] and not o.get("is_unanswered")
        )
        answered_count = total - unanswered_count
        # Calculate accuracy based on answered questions; if none answered, accuracy is 0.0
        accuracy = round(correct_count / answered_count, 3) if answered_count > 0 else 0.0

        if answered_count == 0:
            confidence_level = "None (0 answered)"
        elif answered_count == 1:
            confidence_level = "Low (1 observation)"
        elif answered_count in (2, 3):
            confidence_level = f"Moderate ({answered_count} observations)"
        else:
            confidence_level = f"High ({answered_count} observations)"

        distinct_attempts = len({o["attempt_id"] for o in observations})
        latest_obs = observations[-1]
        most_recent_result = latest_obs["is_correct"]
        most_recent_attempt_at = (
            latest_obs["created_at"].isoformat()
            if latest_obs.get("created_at")
            else None
        )

        # Count consecutive incorrect outcomes from latest backward (excluding skipped/unanswered)
        consecutive_incorrect = 0
        for o in reversed(observations):
            if o.get("is_unanswered"):
                break
            if not o["is_correct"]:
                consecutive_incorrect += 1
            else:
                break

        # Count consecutive correct outcomes from latest backward
        consecutive_correct = 0
        for o in reversed(observations):
            if o["is_correct"]:
                consecutive_correct += 1
            else:
                break

        has_demonstrated_mastery = (
            (correct_count >= 2 and consecutive_correct >= 2)
            or (answered_count >= 2 and accuracy == 1.0)
        )

        return {
            "total_observations": total,
            "correct_count": correct_count,
            "incorrect_count": incorrect_count,
            "unanswered_count": unanswered_count,
            "accuracy": accuracy,
            "confidence_level": confidence_level,
            "distinct_attempts_count": distinct_attempts,
            "most_recent_result": most_recent_result,
            "most_recent_attempt_at": most_recent_attempt_at,
            "consecutive_incorrect_count": consecutive_incorrect,
            "consecutive_correct_count": consecutive_correct,
            "has_demonstrated_mastery": has_demonstrated_mastery,
        }

    @staticmethod
    def classify_chunk(metrics: dict) -> tuple[KnowledgeGapClassification, str]:
        """
        Applies transparent, explainable heuristic thresholds to assign a
        pedagogical classification to a knowledge chunk.
        
        Distinguishes unanswered (skipped) questions from genuine conceptual misconceptions.
        
        Returns:
            (KnowledgeGapClassification, reason_string)
        """
        total = metrics["total_observations"]
        acc = metrics["accuracy"]
        ci = metrics["consecutive_incorrect_count"]
        recent = metrics["most_recent_result"]
        unanswered = metrics.get("unanswered_count", 0)
        answered = total - unanswered

        # 1. Insufficient Data
        if total == 0:
            return (
                KnowledgeGapClassification.INSUFFICIENT_DATA,
                "No quiz questions answered for this concept yet.",
            )

        if answered <= 1:
            if answered == 0:
                return (
                    KnowledgeGapClassification.INSUFFICIENT_DATA,
                    f"{unanswered} question(s) skipped without answering. Answer assessment questions to evaluate conceptual grasp.",
                )
            if metrics["incorrect_count"] == 1:
                unanswered_note = f" (along with {unanswered} skipped question(s))" if unanswered > 0 else ""
                return (
                    KnowledgeGapClassification.INSUFFICIENT_DATA,
                    f"Single isolated mistake observed{unanswered_note}. Further assessment required to determine if a persistent gap exists.",
                )
            else:
                return (
                    KnowledgeGapClassification.INSUFFICIENT_DATA,
                    "Initial correct response observed. Additional observations required to confirm mastery.",
                )

        # 2. Weak Classification (Repeated or severe errors on answered questions)
        # Condition A: 2 or more consecutive errors on recent attempts
        if ci >= 2:
            return (
                KnowledgeGapClassification.WEAK,
                f"Repeated incorrect responses ({ci} consecutive errors) on recent attempts.",
            )

        # Condition B: Consistently low accuracy (< 40%) across multiple answered questions
        if answered >= 2 and acc < 0.40:
            unanswered_note = f" ({unanswered} skipped)" if unanswered > 0 else ""
            return (
                KnowledgeGapClassification.WEAK,
                f"Consistently low accuracy ({round(acc * 100, 1)}%) across {answered} answered assessment questions{unanswered_note}.",
            )

        # 3. Strong Classification (High accuracy + demonstrated recent success)
        if answered >= 2 and acc >= 0.75 and recent is True:
            return (
                KnowledgeGapClassification.STRONG,
                f"Consistently high accuracy ({round(acc * 100, 1)}%) with demonstrated recent mastery.",
            )

        # 4. Developing Classification (Mixed performance or high accuracy with recent slip)
        if answered >= 2 and acc >= 0.75 and recent is False:
            return (
                KnowledgeGapClassification.DEVELOPING,
                f"High historical accuracy ({round(acc * 100, 1)}%) but slipped on most recent attempt. Reinforcement advised.",
            )

        return (
            KnowledgeGapClassification.DEVELOPING,
            f"Mixed performance ({round(acc * 100, 1)}% accuracy) across {answered} answered questions requiring reinforcement.",
        )

    @staticmethod
    def compute_trend(observations: list[dict]) -> tuple[PerformanceTrend, str]:
        """
        Determines whether learner performance on a chunk is improving,
        stable, declining, or unconfirmed based on chronological answers.
        
        Returns:
            (PerformanceTrend, trend_reason)
        """
        total = len(observations)
        if total < 2:
            return (
                PerformanceTrend.INSUFFICIENT_DATA,
                "Insufficient attempt history to identify a performance trend.",
            )

        # For exactly 2 observations, compare transition between attempt 1 and 2
        if total == 2:
            first = observations[0]["is_correct"]
            second = observations[1]["is_correct"]
            if not first and second:
                return (
                    PerformanceTrend.IMPROVING,
                    "Corrected earlier mistake on the most recent attempt.",
                )
            elif first and not second:
                return (
                    PerformanceTrend.DECLINING,
                    "Incorrect on most recent attempt after initial correct answer.",
                )
            else:
                return (
                    PerformanceTrend.STABLE,
                    "Consistent performance across initial attempts.",
                )

        # For 3 or more observations: split chronologically into earlier and recent windows
        split_idx = total // 2
        early_window = observations[:split_idx]
        recent_window = observations[split_idx:]

        early_acc = sum(1 for o in early_window if o["is_correct"]) / len(early_window)
        recent_acc = sum(1 for o in recent_window if o["is_correct"]) / len(recent_window)
        delta = round(recent_acc - early_acc, 3)

        if delta >= 0.25:
            return (
                PerformanceTrend.IMPROVING,
                f"Performance improved (+{round(delta * 100, 1)}% accuracy) between earlier and recent attempts.",
            )
        elif delta <= -0.25:
            return (
                PerformanceTrend.DECLINING,
                f"Performance declined ({round(delta * 100, 1)}% accuracy) on recent attempts.",
            )
        else:
            return (
                PerformanceTrend.STABLE,
                "Performance has remained steady across assessment attempts.",
            )

    @staticmethod
    def derive_concept_name(chunk_text: str, chunk_index: int) -> str:
        """
        Derives an explainable topic/concept name from the chunk text deterministically.
        """
        clean = chunk_text.strip()
        if not clean:
            return f"Concept #{chunk_index + 1}"
        first_line = clean.split('\n')[0].strip()
        for sep in ['. ', '? ', '! ', ': ']:
            if sep in first_line:
                first_line = first_line.split(sep)[0].strip()
                break
        if len(first_line) > 65:
            first_line = first_line[:62].rsplit(' ', 1)[0] + '...'
        for filler in ["So, ", "And ", "Now, ", "Well, ", "In this part, ", "Here, ", "So "]:
            if first_line.startswith(filler):
                first_line = first_line[len(filler):].capitalize()
        return first_line if len(first_line) >= 4 else f"Concept #{chunk_index + 1}"

    @staticmethod
    def derive_recommended_action(
        classification: KnowledgeGapClassification,
        has_recovered: bool,
        unanswered_count: int,
        is_in_progress: bool = False,
    ) -> str:
        """Provides an actionable, explainable next learning step for the student."""
        if has_recovered:
            return "Improvement demonstrated. Review key takeaways to reinforce long-term retention."
        if is_in_progress:
            return "Recovery session in progress. Complete the practice micro-quiz to evaluate your understanding."
        if classification == KnowledgeGapClassification.WEAK:
            return "Needs targeted recovery. Review the source lecture moment and take the recovery micro-quiz."
        if classification == KnowledgeGapClassification.DEVELOPING:
            return "Reinforcement advised. Ask Ask VIDYORA tutor questions to clarify lingering conceptual doubts."
        if classification == KnowledgeGapClassification.STRONG:
            return "Concept mastered. Maintain proficiency by practicing related lecture topics."
        if unanswered_count > 0:
            return "Unanswered questions detected. Take the quiz again to evaluate your understanding."
        return "Attempt quiz questions grounded in this section to assess your understanding."

    @staticmethod
    def derive_recovery_status(
        classification: KnowledgeGapClassification,
        latest_recovery_result: Optional[str],
        has_recovered: bool,
        is_in_progress: bool = False,
    ) -> str:
        """
        Computes the current lifecycle status:
        - 'improvement_demonstrated': successfully recovered or improved
        - 'recovery_in_progress': actively engaged in recovery session
        - 'needs_review': weak or developing without completed recovery
        - 'mastered': strong mastery demonstrated
        - 'unassessed': insufficient diagnostic data
        """
        if has_recovered or latest_recovery_result in ("RECOVERED", "IMPROVED"):
            return "improvement_demonstrated"
        if is_in_progress:
            return "recovery_in_progress"
        if latest_recovery_result == "NOT_RECOVERED":
            return "needs_review"
        if classification in (KnowledgeGapClassification.WEAK, KnowledgeGapClassification.DEVELOPING):
            return "needs_review"
        if classification == KnowledgeGapClassification.STRONG:
            return "mastered"
        return "unassessed"

    @classmethod
    def analyze_video_knowledge_gaps(
        cls,
        db: Session,
        video_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[VideoKnowledgeGapsResponse]:
        """
        Analyzes knowledge gaps for all chunks associated with a specific educational video.
        Returns None if the video does not exist.
        """
        if not AnalyticsRepository.video_exists(db, video_id, user_id=user_id):
            return None

        chunks = AnalyticsRepository.get_chunks_for_video(db, video_id, user_id=user_id)
        raw_observations = AnalyticsRepository.get_chunk_answer_observations_for_video(
            db, video_id, user_id=user_id
        )

        # Group observations by chunk_id
        obs_by_chunk: dict[str, list[dict]] = {c.id: [] for c in chunks}
        for o in raw_observations:
            cid = o["chunk_id"]
            if cid in obs_by_chunk:
                obs_by_chunk[cid].append(o)

        gap_items: list[ChunkKnowledgeGap] = []
        weak_chunk_ids: list[str] = []
        total_assessed_obs = 0
        total_correct_obs = 0

        weak_count = 0
        dev_count = 0
        strong_count = 0
        insufficient_count = 0

        for chunk in chunks:
            c_obs = obs_by_chunk.get(chunk.id, [])
            metrics = cls.compute_chunk_metrics(c_obs)
            classification, reason = cls.classify_chunk(metrics)
            trend, _ = cls.compute_trend(c_obs)

            if classification == KnowledgeGapClassification.WEAK:
                weak_count += 1
                weak_chunk_ids.append(chunk.id)
            elif classification == KnowledgeGapClassification.DEVELOPING:
                dev_count += 1
            elif classification == KnowledgeGapClassification.STRONG:
                strong_count += 1
            else:
                insufficient_count += 1

            total_assessed_obs += metrics["total_observations"]
            total_correct_obs += metrics["correct_count"]

            formatted_time = cls.format_timestamp(chunk.start_time)
            snippet = (chunk.text[:120] + "...") if len(chunk.text) > 120 else chunk.text

            latest_session = RecoveryRepository.get_latest_session_for_chunk(
                db, video_id, chunk.id, user_id=user_id
            )
            is_in_progress = bool(latest_session and latest_session.status != "EVALUATED")
            latest_rec = latest_session.recovery_result if (latest_session and latest_session.status == "EVALUATED") else None
            has_rec = (latest_rec == "RECOVERED")
            has_demonstrated_improvement = (latest_rec in ("RECOVERED", "IMPROVED"))

            concept_name = cls.derive_concept_name(chunk.text, chunk.chunk_index)
            unanswered_cnt = metrics.get("unanswered_count", 0)
            rec_action = cls.derive_recommended_action(
                classification, has_demonstrated_improvement, unanswered_cnt, is_in_progress
            )
            rec_status = cls.derive_recovery_status(
                classification, latest_rec, has_rec, is_in_progress
            )

            gap_items.append(
                ChunkKnowledgeGap(
                    chunk_id=chunk.id,
                    chunk_index=chunk.chunk_index,
                    video_id=video_id,
                    source_timestamp=SourceTimestamp(
                        timestamp=chunk.start_time,
                        formatted_time=formatted_time,
                        label=f"Chunk {chunk.chunk_index + 1} ({formatted_time})",
                    ),
                    classification=classification,
                    trend=trend,
                    accuracy=metrics["accuracy"],
                    confidence_level=metrics.get("confidence_level"),
                    recovery_session_id=latest_session.id if latest_session else None,
                    total_observations=metrics["total_observations"],
                    correct_count=metrics["correct_count"],
                    incorrect_count=metrics["incorrect_count"],
                    unanswered_count=unanswered_cnt,
                    concept_name=concept_name,
                    recommended_action=rec_action,
                    recovery_status=rec_status,
                    distinct_attempts_count=metrics["distinct_attempts_count"],
                    most_recent_result=metrics["most_recent_result"],
                    most_recent_attempt_at=metrics["most_recent_attempt_at"],
                    consecutive_incorrect_count=metrics["consecutive_incorrect_count"],
                    consecutive_correct_count=metrics["consecutive_correct_count"],
                    has_demonstrated_mastery=metrics["has_demonstrated_mastery"],
                    reason=reason,
                    chunk_summary_text=snippet,
                    latest_recovery_result=latest_rec,
                    has_recovered=has_rec,
                )
            )

        overall_accuracy = (
            round(total_correct_obs / total_assessed_obs, 3)
            if total_assessed_obs > 0
            else 0.0
        )
        assessed_chunks = len([g for g in gap_items if g.total_observations > 0])

        # Priority sort: WEAK first, then DEVELOPING, then STRONG, then INSUFFICIENT_DATA
        priority_map = {
            KnowledgeGapClassification.WEAK: 0,
            KnowledgeGapClassification.DEVELOPING: 1,
            KnowledgeGapClassification.STRONG: 2,
            KnowledgeGapClassification.INSUFFICIENT_DATA: 3,
        }
        sorted_gaps = sorted(
            gap_items,
            key=lambda g: (priority_map[g.classification], g.chunk_index),
        )

        recovered_chunks_count = len([g for g in gap_items if g.has_recovered or g.recovery_status == "improvement_demonstrated"])
        recovery_in_progress_count = len([g for g in gap_items if g.recovery_status == "recovery_in_progress"])

        summary = VideoKnowledgeGapSummary(
            total_chunks=len(chunks),
            assessed_chunks=assessed_chunks,
            weak_chunks_count=weak_count,
            developing_chunks_count=dev_count,
            strong_chunks_count=strong_count,
            insufficient_data_count=insufficient_count,
            overall_accuracy=overall_accuracy,
            recovered_chunks_count=recovered_chunks_count,
            recovery_in_progress_count=recovery_in_progress_count,
        )

        return VideoKnowledgeGapsResponse(
            video_id=video_id,
            summary=summary,
            weak_chunk_ids=weak_chunk_ids,
            gaps=sorted_gaps,
        )

    @classmethod
    def analyze_learner_overall_gaps(
        cls,
        db: Session,
        user_id: Optional[str] = None,
    ) -> LearnerOverallKnowledgeGapsResponse:
        """
        Synthesizes a cross-video mastery profile for a learner,
        identifying weak concepts across all assessed lectures.
        """
        chunks, raw_observations = AnalyticsRepository.get_all_chunk_answer_observations(
            db, user_id=user_id
        )

        obs_by_chunk: dict[str, list[dict]] = {c.id: [] for c in chunks}
        video_ids_seen = set()
        for o in raw_observations:
            cid = o["chunk_id"]
            if cid in obs_by_chunk:
                obs_by_chunk[cid].append(o)
            if o.get("video_id"):
                video_ids_seen.add(o["video_id"])

        gap_items: list[ChunkKnowledgeGap] = []
        weak_chunk_ids: list[str] = []
        total_assessed_obs = 0
        total_correct_obs = 0

        weak_count = 0
        dev_count = 0
        strong_count = 0
        insufficient_count = 0

        for chunk in chunks:
            c_obs = obs_by_chunk.get(chunk.id, [])
            metrics = cls.compute_chunk_metrics(c_obs)
            classification, reason = cls.classify_chunk(metrics)
            trend, _ = cls.compute_trend(c_obs)

            if classification == KnowledgeGapClassification.WEAK:
                weak_count += 1
                weak_chunk_ids.append(chunk.id)
            elif classification == KnowledgeGapClassification.DEVELOPING:
                dev_count += 1
            elif classification == KnowledgeGapClassification.STRONG:
                strong_count += 1
            else:
                insufficient_count += 1

            total_assessed_obs += metrics["total_observations"]
            total_correct_obs += metrics["correct_count"]

            formatted_time = cls.format_timestamp(chunk.start_time)
            snippet = (chunk.text[:120] + "...") if len(chunk.text) > 120 else chunk.text

            latest_session = RecoveryRepository.get_latest_session_for_chunk(
                db, chunk.video_id, chunk.id, user_id=user_id
            )
            latest_rec = (
                latest_session.evaluation_result
                if latest_session and latest_session.evaluation_result
                else None
            )
            has_rec = (latest_rec == "RECOVERED")
            is_in_progress = bool(
                latest_session and latest_session.status != "EVALUATED"
            )

            concept_name = cls.derive_concept_name(chunk.text, chunk.chunk_index)
            unanswered_cnt = metrics.get("unanswered_count", 0)
            rec_action = cls.derive_recommended_action(classification, has_rec, unanswered_cnt)
            rec_status = cls.derive_recovery_status(
                classification, latest_rec, has_rec, is_in_progress
            )

            gap_items.append(
                ChunkKnowledgeGap(
                    chunk_id=chunk.id,
                    chunk_index=chunk.chunk_index,
                    video_id=chunk.video_id,
                    source_timestamp=SourceTimestamp(
                        timestamp=chunk.start_time,
                        formatted_time=formatted_time,
                        label=f"Chunk {chunk.chunk_index + 1} ({formatted_time})",
                    ),
                    classification=classification,
                    trend=trend,
                    accuracy=metrics["accuracy"],
                    confidence_level=metrics.get("confidence_level"),
                    recovery_session_id=latest_session.id if latest_session else None,
                    total_observations=metrics["total_observations"],
                    correct_count=metrics["correct_count"],
                    incorrect_count=metrics["incorrect_count"],
                    unanswered_count=unanswered_cnt,
                    concept_name=concept_name,
                    recommended_action=rec_action,
                    recovery_status=rec_status,
                    distinct_attempts_count=metrics["distinct_attempts_count"],
                    most_recent_result=metrics["most_recent_result"],
                    most_recent_attempt_at=metrics["most_recent_attempt_at"],
                    consecutive_incorrect_count=metrics["consecutive_incorrect_count"],
                    consecutive_correct_count=metrics["consecutive_correct_count"],
                    has_demonstrated_mastery=metrics["has_demonstrated_mastery"],
                    reason=reason,
                    chunk_summary_text=snippet,
                    latest_recovery_result=latest_rec,
                    has_recovered=has_rec,
                )
            )

        overall_accuracy = (
            round(total_correct_obs / total_assessed_obs, 3)
            if total_assessed_obs > 0
            else 0.0
        )
        assessed_chunks = len([g for g in gap_items if g.total_observations > 0])

        priority_map = {
            KnowledgeGapClassification.WEAK: 0,
            KnowledgeGapClassification.DEVELOPING: 1,
            KnowledgeGapClassification.STRONG: 2,
            KnowledgeGapClassification.INSUFFICIENT_DATA: 3,
        }
        sorted_gaps = sorted(
            gap_items,
            key=lambda g: (priority_map[g.classification], g.accuracy),
        )

        recovered_chunks_count = len([g for g in gap_items if g.has_recovered or g.recovery_status == "improvement_demonstrated"])
        recovery_in_progress_count = len([g for g in gap_items if g.recovery_status == "recovery_in_progress"])

        summary = VideoKnowledgeGapSummary(
            total_chunks=len(chunks),
            assessed_chunks=assessed_chunks,
            weak_chunks_count=weak_count,
            developing_chunks_count=dev_count,
            strong_chunks_count=strong_count,
            insufficient_data_count=insufficient_count,
            overall_accuracy=overall_accuracy,
            recovered_chunks_count=recovered_chunks_count,
            recovery_in_progress_count=recovery_in_progress_count,
        )

        return LearnerOverallKnowledgeGapsResponse(
            user_id=user_id,
            summary=summary,
            weak_chunk_ids=weak_chunk_ids,
            gaps=sorted_gaps,
            videos_analyzed=len(video_ids_seen),
        )
