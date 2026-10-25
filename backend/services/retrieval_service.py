"""
VIDYORA AI - Semantic Retrieval Service (Step 17)

Provides user-isolated, cosine similarity semantic vector search over persisted
Knowledge Chunks using PostgreSQL pgvector.
"""

import logging
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from repositories.embedding_repository import EmbeddingRepository
from repositories.video_repository import VideoRepository
from services.embedding_service import embedding_service, EmbeddingServiceError
from models import (
    RagRetrieveRequest,
    RagRetrieveResponse,
    RetrievedChunkResult,
)

logger = logging.getLogger(__name__)


def format_seconds(seconds: float) -> str:
    """Formats raw seconds into standard MM:SS or HH:MM:SS format for player seeking."""
    secs = int(max(0, seconds))
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


class RetrievalService:
    """Service executing semantic similarity queries grounded in authenticated learner videos."""

    @classmethod
    def retrieve_chunks(
        cls,
        db: Session,
        user_id: str,
        request: RagRetrieveRequest,
    ) -> RagRetrieveResponse:
        """
        Executes semantic vector similarity retrieval.
        
        Security Invariants:
        1. Strict User Isolation: Can only match chunks belonging to videos owned by user_id.
        2. IDOR Prevention: If a specific video_id is provided, validates that it exists and
           belongs to user_id; returns 404 otherwise.
        3. Configurable top_k and similarity_threshold.
        4. Timestamp Preservation: Each result carries exact start_time, end_time, and formatted
           timestamps for instant YouTube player navigation.
        """
        query_text = request.query.strip()
        if not query_text:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Search query cannot be empty or whitespace.",
            )

        # IDOR check if scoping to a specific video
        if request.video_id:
            video = VideoRepository.get_by_id(db, video_id=request.video_id, user_id=user_id)
            if not video:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Video '{request.video_id}' not found or you do not have permission to access it.",
                )

        # Generate query vector
        try:
            query_vector = embedding_service.generate_embedding(query_text)
        except EmbeddingServiceError as exc:
            logger.error("Embedding generation failed for query: %s", exc.message)
            raise HTTPException(
                status_code=exc.status_code,
                detail=f"Failed to process search query: {exc.message}",
            )

        # Query pgvector via repository
        raw_matches = EmbeddingRepository.search_similar_chunks(
            db=db,
            query_vector=query_vector,
            user_id=user_id,
            video_id=request.video_id,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
        )

        results: list[RetrievedChunkResult] = []
        for chunk, similarity, video_title in raw_matches:
            results.append(
                RetrievedChunkResult(
                    chunk_id=chunk.id,
                    video_id=chunk.video_id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    similarity=round(float(similarity), 4),
                    start_time=chunk.start_time,
                    end_time=chunk.end_time,
                    source_formatted_start=format_seconds(chunk.start_time),
                    source_formatted_end=format_seconds(chunk.end_time),
                    video_title=video_title,
                )
            )

        return RagRetrieveResponse(
            query=query_text,
            results_count=len(results),
            results=results,
        )
