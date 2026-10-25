"""add_pgvector_and_chunk_embeddings

Revision ID: 7a8e9d1f3b20
Revises: 00d68d8a0fab
Create Date: 2026-10-07 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from config import settings


# revision identifiers, used by Alembic.
revision: str = '7a8e9d1f3b20'
down_revision: Union[str, Sequence[str], None] = '00d68d8a0fab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Create chunk_embeddings table
    op.create_table(
        'chunk_embeddings',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('chunk_id', sa.String(length=64), sa.ForeignKey('knowledge_chunks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('video_id', sa.String(length=64), sa.ForeignKey('videos.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('embedding', Vector(settings.embedding_dimension), nullable=False),
        sa.Column('model_name', sa.String(length=64), nullable=False),
        sa.Column('dimension', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('chunk_id', 'model_name', name='uq_chunk_embeddings_chunk_model'),
    )

    # 3. Create btree indexes for fast filtered lookups
    op.create_index('ix_chunk_embeddings_chunk_id', 'chunk_embeddings', ['chunk_id'])
    op.create_index('ix_chunk_embeddings_video_id', 'chunk_embeddings', ['video_id'])
    op.create_index('ix_chunk_embeddings_user_id', 'chunk_embeddings', ['user_id'])
    op.create_index('ix_chunk_embeddings_user_video', 'chunk_embeddings', ['user_id', 'video_id'])
    op.create_index('ix_chunk_embeddings_model', 'chunk_embeddings', ['model_name'])

    # 4. Create HNSW index for cosine distance vector search
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chunk_embeddings_vector_hnsw "
        "ON chunk_embeddings USING hnsw (embedding vector_cosine_ops);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunk_embeddings_vector_hnsw;")
    op.drop_table('chunk_embeddings')
