"""
VIDYORA AI - Video Persistence Repository

Encapsulates database operations for Video, VideoTranscript, TranscriptSegment,
and KnowledgeChunk entities with transaction safety and duplicate/idempotency handling.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from db.models import FlashcardDeck, KnowledgeChunk, Quiz, TranscriptSegment, Video, VideoTranscript
from models import TranscriptChunk as PydanticChunk
from models import VideoTranscript as PydanticTranscript

logger = logging.getLogger(__name__)


class VideoRepository:
    """Repository handling persistence operations for educational videos and transcript data."""

    @staticmethod
    def get_by_id(db: Session, video_id: str, user_id: Optional[str] = None) -> Optional[Video]:
        """Fetches a Video by its canonical identifier with optional user isolation."""
        query = db.query(Video).filter(Video.id == video_id)
        if user_id is not None:
            query = query.filter(Video.user_id == user_id)
        return query.first()

    @staticmethod
    def get_video_list(db: Session, user_id: Optional[str] = None) -> list[dict]:
        """
        Retrieves a lightweight summary list of all persisted educational videos.
        Executes a single optimized SQL query using outer joins and group_by to
        aggregate segment, chunk, quiz, and flashcard counts without N+1 query overhead.
        Enforces user ownership isolation when user_id is supplied.
        """
        stmt = (
            select(
                Video.id,
                Video.platform,
                Video.url,
                Video.title,
                Video.status,
                Video.created_at,
                Video.updated_at,
                func.coalesce(VideoTranscript.segment_count, 0).label("segment_count"),
                func.count(func.distinct(KnowledgeChunk.id)).label("chunk_count"),
                func.count(func.distinct(Quiz.id)).label("quiz_count"),
                func.count(func.distinct(FlashcardDeck.id)).label("deck_count"),
            )
            .outerjoin(VideoTranscript, VideoTranscript.video_id == Video.id)
            .outerjoin(KnowledgeChunk, KnowledgeChunk.video_id == Video.id)
            .outerjoin(Quiz, Quiz.video_id == Video.id)
            .outerjoin(FlashcardDeck, FlashcardDeck.video_id == Video.id)
        )
        if user_id is not None:
            stmt = stmt.filter(Video.user_id == user_id)

        stmt = stmt.group_by(Video.id, VideoTranscript.segment_count).order_by(Video.created_at.desc())
        rows = db.execute(stmt).all()
        return [
            {
                "video_id": row.id,
                "platform": row.platform,
                "url": row.url,
                "title": row.title,
                "status": row.status,
                "created_at": row.created_at.isoformat() if row.created_at else "",
                "updated_at": row.updated_at.isoformat() if row.updated_at else "",
                "segment_count": int(row.segment_count),
                "chunk_count": int(row.chunk_count),
                "has_transcript": bool(row.segment_count > 0 or row.chunk_count > 0),
                "has_quiz": bool(row.quiz_count > 0),
                "has_flashcards": bool(row.deck_count > 0),
            }
            for row in rows
        ]

    @staticmethod
    def get_video_workspace(db: Session, video_id: str, user_id: Optional[str] = None) -> Optional[Video]:
        """
        Retrieves a complete video educational workspace for a given video_id.
        Enforces user ownership when user_id is provided.
        """
        stmt = select(Video).filter(Video.id == video_id)
        if user_id is not None:
            stmt = stmt.filter(Video.user_id == user_id)

        stmt = stmt.options(
            joinedload(Video.transcript).selectinload(VideoTranscript.segments),
            selectinload(Video.chunks),
            selectinload(Video.quizzes).selectinload(Quiz.questions),
            selectinload(Video.flashcard_decks).selectinload(FlashcardDeck.cards),
        )
        return db.scalars(stmt).first()


    @staticmethod
    def ensure_video_stub(
        db: Session,
        video_id: str,
        title: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Video:
        """
        Guarantees that a parent Video record exists in the database.
        Prevents foreign key violations when downstream AI services (quiz/flashcards)
        are invoked with synthetic or pre-existing video identifiers.
        """
        existing = db.query(Video).filter(Video.id == video_id).first()
        if existing:
            if user_id and not existing.user_id:
                existing.user_id = user_id
                db.flush()
            return existing

        now = datetime.now(timezone.utc)
        stub = Video(
            id=video_id,
            user_id=user_id,
            url=f"https://www.youtube.com/watch?v={video_id}",
            platform="youtube",
            title=title or f"Video {video_id}",
            status="completed",
            created_at=now,
            updated_at=now,
        )
        db.add(stub)
        db.flush()
        return stub

    @staticmethod
    def save_processed_video(
        db: Session,
        video_id: str,
        url: str,
        platform: str,
        title: Optional[str],
        transcript_data: PydanticTranscript,
        user_id: Optional[str] = None,
    ) -> Video:
        """
        Persists a fully processed video alongside its transcript, segments, and knowledge chunks.
        Associates ownership to user_id.
        """
        now = datetime.now(timezone.utc)
        try:
            # 1. Upsert Video Entity
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                video = Video(
                    id=video_id,
                    user_id=user_id,
                    url=url,
                    platform=platform,
                    title=title,
                    status="completed",
                    error_message=None,
                    created_at=now,
                    updated_at=now,
                )
                db.add(video)
                db.flush()
            else:
                if user_id:
                    video.user_id = user_id
                video.url = url
                video.platform = platform
                video.title = title or video.title
                video.status = "completed"
                video.error_message = None
                video.updated_at = now

                # Clean out existing transcript and chunks to ensure clean replacement
                if video.transcript:
                    db.delete(video.transcript)
                    db.flush()
                db.query(KnowledgeChunk).filter(KnowledgeChunk.video_id == video_id).delete()
                db.flush()

            # 2. Create VideoTranscript
            vt = VideoTranscript(
                video_id=video.id,
                language=transcript_data.language,
                is_generated=transcript_data.is_generated,
                full_text=transcript_data.full_text,
                segment_count=transcript_data.segment_count,
                cleaned_segment_count=transcript_data.cleaned_segment_count,
                created_at=now,
                updated_at=now,
            )
            db.add(vt)
            db.flush()

            # 3. Create TranscriptSegments (both raw and cleaned)
            segments_to_add = []
            for idx, seg in enumerate(transcript_data.segments):
                segments_to_add.append(
                    TranscriptSegment(
                        transcript_id=vt.id,
                        segment_index=idx,
                        text=seg.text,
                        start_time=seg.start,
                        duration=seg.duration,
                        is_cleaned=False,
                        created_at=now,
                    )
                )

            for idx, c_seg in enumerate(transcript_data.cleaned_segments):
                segments_to_add.append(
                    TranscriptSegment(
                        transcript_id=vt.id,
                        segment_index=idx,
                        text=c_seg.text,
                        start_time=c_seg.start,
                        duration=c_seg.duration,
                        is_cleaned=True,
                        created_at=now,
                    )
                )

            if segments_to_add:
                db.add_all(segments_to_add)

            # 4. Create KnowledgeChunks
            chunks_to_add = []
            for chunk in transcript_data.chunks:
                chunks_to_add.append(
                    KnowledgeChunk(
                        id=chunk.chunk_id,
                        video_id=video.id,
                        chunk_index=chunk.chunk_index,
                        text=chunk.text,
                        start_time=chunk.start_time,
                        end_time=chunk.end_time,
                        duration=chunk.duration,
                        word_count=chunk.word_count,
                        segment_start_index=chunk.segment_start_index,
                        segment_end_index=chunk.segment_end_index,
                        created_at=now,
                    )
                )

            if chunks_to_add:
                db.add_all(chunks_to_add)

            db.commit()
            db.refresh(video)
            logger.info("Persisted video %s with %d chunks and %d segments.", video.id, len(chunks_to_add), len(segments_to_add))
            return video

        except Exception as exc:
            db.rollback()
            logger.error("Failed to persist processed video %s: %s", video_id, exc)
            raise

    @staticmethod
    def save_failed_video(
        db: Session,
        video_id: str,
        url: str,
        platform: str,
        title: Optional[str],
        error_message: str,
        user_id: Optional[str] = None,
    ) -> Video:
        """Persists or updates a video entity when extraction or validation fails."""
        now = datetime.now(timezone.utc)
        try:
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                video = Video(
                    id=video_id,
                    user_id=user_id,
                    url=url,
                    platform=platform,
                    title=title,
                    status="failed",
                    error_message=error_message,
                    created_at=now,
                    updated_at=now,
                )
                db.add(video)
            else:
                if user_id:
                    video.user_id = user_id
                video.status = "failed"
                video.error_message = error_message
                video.updated_at = now

            db.commit()
            db.refresh(video)
            return video
        except Exception as exc:
            db.rollback()
            logger.error("Failed to save failed video status for %s: %s", video_id, exc)
            raise

    @staticmethod
    def save_accepted_video(
        db: Session,
        video_id: str,
        url: str,
        platform: str,
        user_id: Optional[str] = None,
    ) -> Video:
        """Persists a video entity in ACCEPTED status (e.g. non-YouTube direct sources)."""
        now = datetime.now(timezone.utc)
        try:
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                video = Video(
                    id=video_id,
                    user_id=user_id,
                    url=url,
                    platform=platform,
                    status="accepted",
                    created_at=now,
                    updated_at=now,
                )
                db.add(video)
            else:
                if user_id:
                    video.user_id = user_id
                video.status = "accepted"
                video.updated_at = now

            db.commit()
            db.refresh(video)
            return video
        except Exception as exc:
            db.rollback()
            logger.error("Failed to save accepted video %s: %s", video_id, exc)
            raise
