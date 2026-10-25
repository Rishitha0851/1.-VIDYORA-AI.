"""
VIDYORA AI - Embedding & Vector Repository (Step 17)

Data access layer managing pgvector storage, idempotent chunk embedding persistence,
and user-isolated semantic similarity vector retrieval.
"""

import logging
from typing import List, Optional, Set, Tuple
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from db.models import ChunkEmbedding, KnowledgeChunk, Video

logger = logging.getLogger(__name__)


class EmbeddingRepository:
    """Repository handling all database operations for vector embeddings and similarity queries."""

    @classmethod
    def get_unembedded_chunks(
        cls,
        db: Session,
        video_id: str,
        user_id: str,
        model_name: str,
    ) -> List[KnowledgeChunk]:
        """
        Retrieves all KnowledgeChunks for a user's video that do not yet have
        an embedding stored for the specified model_name. Preserves chunk order.
        """
        # Subquery of chunk IDs that already have an embedding for this model
        existing_subq = (
            select(ChunkEmbedding.chunk_id)
            .where(
                and_(
                    ChunkEmbedding.video_id == video_id,
                    ChunkEmbedding.user_id == user_id,
                    ChunkEmbedding.model_name == model_name,
                )
            )
            .scalar_subquery()
        )

        chunks = (
            db.query(KnowledgeChunk)
            .join(Video, KnowledgeChunk.video_id == Video.id)
            .filter(
                and_(
                    KnowledgeChunk.video_id == video_id,
                    Video.user_id == user_id,
                    KnowledgeChunk.id.not_in(existing_subq),
                )
            )
            .order_by(KnowledgeChunk.chunk_index.asc())
            .all()
        )

        return chunks

    @classmethod
    def get_already_embedded_chunk_count(
        cls,
        db: Session,
        video_id: str,
        user_id: str,
        model_name: str,
    ) -> int:
        """Returns the number of chunks for this video that already have embeddings."""
        return (
            db.query(ChunkEmbedding)
            .filter(
                and_(
                    ChunkEmbedding.video_id == video_id,
                    ChunkEmbedding.user_id == user_id,
                    ChunkEmbedding.model_name == model_name,
                )
            )
            .count()
        )

    @classmethod
    def bulk_save_embeddings(
        cls,
        db: Session,
        embeddings: List[ChunkEmbedding],
    ) -> List[ChunkEmbedding]:
        """Persists a list of ChunkEmbedding entities transactionally."""
        if not embeddings:
            return []

        db.add_all(embeddings)
        db.commit()
        return embeddings

    @classmethod
    def search_similar_chunks(
        cls,
        db: Session,
        query_vector: List[float],
        user_id: str,
        video_id: Optional[str] = None,
        top_k: int = 5,
        similarity_threshold: Optional[float] = None,
    ) -> List[Tuple[KnowledgeChunk, float, Optional[str]]]:
        """
        Executes an authenticated, user-isolated pgvector semantic similarity search.
        
        Security Invariants:
        - Strict user_id ownership predicate ensures cross-user vector isolation.
        - Returns a tuple of (KnowledgeChunk, cosine_similarity, video_title).
        """
        # Cosine distance in pgvector: <=> operator
        distance_expr = ChunkEmbedding.embedding.cosine_distance(query_vector)
        # Cosine similarity in range [-1.0, 1.0]: 1.0 - cosine_distance
        similarity_expr = 1.0 - distance_expr

        query = (
            db.query(
                KnowledgeChunk,
                similarity_expr.label("similarity"),
                Video.title.label("video_title"),
            )
            .join(ChunkEmbedding, KnowledgeChunk.id == ChunkEmbedding.chunk_id)
            .join(Video, KnowledgeChunk.video_id == Video.id)
            .filter(
                and_(
                    ChunkEmbedding.user_id == user_id,
                    Video.user_id == user_id,
                )
            )
        )

        # Optional scoping to a specific video
        if video_id:
            query = query.filter(ChunkEmbedding.video_id == video_id)

        # Optional minimum similarity cutoff
        if similarity_threshold is not None:
            query = query.filter(similarity_expr >= similarity_threshold)

        # Order by ascending distance (highest cosine similarity first)
        results = (
            query.order_by(distance_expr.asc())
            .limit(top_k)
            .all()
        )

        return results
