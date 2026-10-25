"""
VIDYORA AI - Chunk Indexing Service (Step 17)

Coordinates controlled, idempotent vector indexing for KnowledgeChunks.
Generates embeddings only for unembedded chunks, preserving chunk order,
timestamps, and foreign key boundaries.
"""

import logging
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from db.models import ChunkEmbedding, Video
from repositories.embedding_repository import EmbeddingRepository
from repositories.video_repository import VideoRepository
from services.embedding_service import embedding_service, EmbeddingServiceError
from models import IndexVideoChunksResponse

logger = logging.getLogger(__name__)


class IndexingService:
    """Service orchestrating batch embedding and vector indexing of knowledge chunks."""

    @classmethod
    def index_video_chunks(
        cls,
        db: Session,
        video_id: str,
        user_id: str,
    ) -> IndexVideoChunksResponse:
        """
        Indexes all KnowledgeChunks of a user's video that do not yet possess
        embeddings for the currently active embedding model.
        
        Guarantees:
        - Strict user ownership validation.
        - Idempotent: Skips chunks already indexed under the current model.
        - Preserves chunk ordering and timestamps.
        - Graceful failure: Raises clean HTTPExceptions if provider fails.
        """
        # 1. Verify video exists and is owned by the authenticated user
        video = VideoRepository.get_by_id(db, video_id=video_id, user_id=user_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video '{video_id}' not found or you do not have permission to access it.",
            )

        model_name = embedding_service.get_model_name()
        dimension = embedding_service.get_dimension()

        # 2. Count existing chunks and find unembedded ones
        unembedded_chunks = EmbeddingRepository.get_unembedded_chunks(
            db=db,
            video_id=video_id,
            user_id=user_id,
            model_name=model_name,
        )
        already_indexed = EmbeddingRepository.get_already_embedded_chunk_count(
            db=db,
            video_id=video_id,
            user_id=user_id,
            model_name=model_name,
        )
        total_chunks = len(unembedded_chunks) + already_indexed

        if not unembedded_chunks:
            logger.info("All %d chunks for video %s are already indexed.", total_chunks, video_id)
            return IndexVideoChunksResponse(
                video_id=video_id,
                indexed_chunks=0,
                already_indexed_chunks=already_indexed,
                total_chunks=total_chunks,
                model_used=model_name,
            )

        # 3. Generate embeddings in batch
        texts_to_embed = [chunk.text for chunk in unembedded_chunks]
        try:
            vectors = embedding_service.generate_embeddings_batch(texts_to_embed)
        except EmbeddingServiceError as exc:
            logger.error("Failed to generate embeddings for video %s: %s", video_id, exc.message)
            raise HTTPException(
                status_code=exc.status_code,
                detail=f"Embedding generation failed: {exc.message}",
            )

        # 4. Construct ChunkEmbedding entities
        embeddings_to_save = []
        for chunk, vec in zip(unembedded_chunks, vectors):
            emb_entity = ChunkEmbedding(
                chunk_id=chunk.id,
                video_id=video_id,
                user_id=user_id,
                embedding=vec,
                model_name=model_name,
                dimension=dimension,
            )
            embeddings_to_save.append(emb_entity)

        # 5. Bulk persist transactionally
        EmbeddingRepository.bulk_save_embeddings(db, embeddings_to_save)
        logger.info(
            "Successfully indexed %d new chunks for video %s (total %d).",
            len(embeddings_to_save),
            video_id,
            total_chunks,
        )

        return IndexVideoChunksResponse(
            video_id=video_id,
            indexed_chunks=len(embeddings_to_save),
            already_indexed_chunks=already_indexed,
            total_chunks=total_chunks,
            model_used=model_name,
        )
