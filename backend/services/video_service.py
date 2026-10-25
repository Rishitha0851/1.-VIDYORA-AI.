"""
VIDYORA AI - Video Educational Workspace Service

Orchestrates business logic for listing and restoring persisted educational videos,
transcripts, chunks, quizzes, and flashcard decks from PostgreSQL.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from models import (
    Flashcard as PydanticFlashcard,
    GeneratedFlashcards,
    QuizClientView,
    QuizDifficulty,
    QuizQuestionClient,
    SourceTimestamp,
    TranscriptChunk,
    TranscriptSegment,
    VideoListItem,
    VideoListResponse,
    VideoMetadata,
    VideoPlatform,
    VideoProcessingStatus,
    VideoTranscript,
    VideoWorkspaceResponse,
)
from repositories.video_repository import VideoRepository

logger = logging.getLogger(__name__)


class VideoService:
    """Service layer handling read operations for persisted video workspaces."""

    @staticmethod
    def list_persisted_videos(db: Session, user_id: Optional[str] = None) -> VideoListResponse:
        """
        Retrieves a summary list of all previously processed videos.
        Delegates to VideoRepository for a single aggregated query avoiding N+1 overhead.
        Enforces user isolation if user_id is provided.
        """
        raw_items = VideoRepository.get_video_list(db, user_id=user_id)
        items = []
        for item in raw_items:
            platform_val = (
                VideoPlatform(item["platform"])
                if item["platform"] in [p.value for p in VideoPlatform]
                else VideoPlatform.UNKNOWN
            )
            status_val = (
                VideoProcessingStatus(item["status"])
                if item["status"] in [s.value for s in VideoProcessingStatus]
                else VideoProcessingStatus.COMPLETED
            )
            items.append(
                VideoListItem(
                    video_id=item["video_id"],
                    platform=platform_val,
                    url=item["url"],
                    title=item["title"],
                    status=status_val,
                    created_at=item["created_at"],
                    updated_at=item["updated_at"],
                    segment_count=item["segment_count"],
                    chunk_count=item["chunk_count"],
                    has_transcript=item["has_transcript"],
                    has_quiz=item["has_quiz"],
                    has_flashcards=item["has_flashcards"],
                )
            )
        return VideoListResponse(videos=items, total_count=len(items))

    @staticmethod
    def get_video_workspace(db: Session, video_id: str, user_id: Optional[str] = None) -> Optional[VideoWorkspaceResponse]:
        """
        Reloads a complete educational workspace from PostgreSQL for the given video_id.
        Retrieves video metadata, transcripts, knowledge chunks, latest quiz, and latest
        flashcards without calling external APIs or Gemini.
        Enforces user ownership isolation if user_id is provided.
        """
        video = VideoRepository.get_video_workspace(db, video_id, user_id=user_id)
        if not video:
            return None

        # 1. Build Transcript schema if present
        transcript_pydantic: Optional[VideoTranscript] = None
        if video.transcript:
            raw_segments = []
            cleaned_segments = []
            for seg in video.transcript.segments:
                p_seg = TranscriptSegment(
                    text=seg.text,
                    start=seg.start_time,
                    duration=seg.duration,
                )
                if seg.is_cleaned:
                    cleaned_segments.append(p_seg)
                else:
                    raw_segments.append(p_seg)

            p_chunks = [
                TranscriptChunk(
                    chunk_id=c.id,
                    chunk_index=c.chunk_index,
                    video_id=c.video_id,
                    text=c.text,
                    start_time=c.start_time,
                    end_time=c.end_time,
                    duration=c.duration,
                    word_count=c.word_count,
                    segment_start_index=c.segment_start_index,
                    segment_end_index=c.segment_end_index,
                )
                for c in video.chunks
            ]

            transcript_pydantic = VideoTranscript(
                video_id=video.id,
                language=video.transcript.language,
                is_generated=video.transcript.is_generated,
                full_text=video.transcript.full_text,
                segments=raw_segments,
                segment_count=len(raw_segments),
                cleaned_segments=cleaned_segments,
                cleaned_segment_count=len(cleaned_segments),
                chunks=p_chunks,
                chunk_count=len(p_chunks),
            )

        # 2. Build VideoMetadata
        platform_val = (
            VideoPlatform(video.platform)
            if video.platform in [p.value for p in VideoPlatform]
            else VideoPlatform.UNKNOWN
        )
        status_val = (
            VideoProcessingStatus(video.status)
            if video.status in [s.value for s in VideoProcessingStatus]
            else VideoProcessingStatus.COMPLETED
        )

        metadata = VideoMetadata(
            id=video.id,
            url=video.url,
            platform=platform_val,
            title=video.title,
            status=status_val,
            created_at=video.created_at.isoformat() if video.created_at else "",
            updated_at=video.updated_at.isoformat() if video.updated_at else "",
            error_message=video.error_message,
            transcript=transcript_pydantic,
        )

        # 3. Build latest QuizClientView if any persisted quiz exists
        latest_quiz_view: Optional[QuizClientView] = None
        if video.quizzes:
            # Sort quizzes by created_at descending to select the latest
            latest_quiz = sorted(video.quizzes, key=lambda q: q.created_at, reverse=True)[0]
            client_questions = []
            for q in latest_quiz.questions:
                orig_id = q.id.replace(f"{latest_quiz.id}_", "", 1) if q.id.startswith(f"{latest_quiz.id}_") else q.id
                diff_val = (
                    QuizDifficulty(q.difficulty)
                    if q.difficulty in [d.value for d in QuizDifficulty]
                    else QuizDifficulty.MEDIUM
                )
                client_questions.append(
                    QuizQuestionClient(
                        id=orig_id,
                        question=q.question_text,
                        options=q.options,
                        difficulty=diff_val,
                        source_timestamp=SourceTimestamp(
                            timestamp=q.source_timestamp,
                            formatted_time=q.source_formatted_time,
                            label=q.source_label,
                        ),
                        source_chunk_id=q.source_chunk_id,
                    )
                )

            latest_quiz_view = QuizClientView(
                quiz_id=latest_quiz.id,
                video_id=video.id,
                title=latest_quiz.title,
                instructions=latest_quiz.instructions or "",
                questions=client_questions,
                question_count=len(client_questions),
            )

        # 4. Build latest GeneratedFlashcards if any persisted deck exists
        latest_flashcards_view: Optional[GeneratedFlashcards] = None
        if video.flashcard_decks:
            latest_deck = sorted(video.flashcard_decks, key=lambda d: d.created_at, reverse=True)[0]
            cards = []
            for card in latest_deck.cards:
                orig_id = card.id.replace(f"{latest_deck.id}_", "", 1) if card.id.startswith(f"{latest_deck.id}_") else card.id
                diff_val = (
                    QuizDifficulty(card.difficulty)
                    if card.difficulty in [d.value for d in QuizDifficulty]
                    else QuizDifficulty.MEDIUM
                )
                cards.append(
                    PydanticFlashcard(
                        id=orig_id,
                        front=card.front,
                        back=card.back,
                        difficulty=diff_val,
                        source_timestamp=SourceTimestamp(
                            timestamp=card.source_timestamp,
                            formatted_time=card.source_formatted_time,
                            label=card.source_label,
                        ),
                        source_chunk_id=card.source_chunk_id,
                    )
                )

            latest_flashcards_view = GeneratedFlashcards(
                topic=latest_deck.topic,
                cards=cards,
                card_count=len(cards),
            )

        return VideoWorkspaceResponse(
            video=metadata,
            latest_quiz=latest_quiz_view,
            latest_flashcards=latest_flashcards_view,
            summary=None,
            notes=None,
            available_quizzes_count=len(video.quizzes),
            available_decks_count=len(video.flashcard_decks),
        )
