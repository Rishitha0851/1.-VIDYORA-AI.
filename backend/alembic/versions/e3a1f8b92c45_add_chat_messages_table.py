"""add_chat_messages_table

Revision ID: e3a1f8b92c45
Revises: 5c0a9a22f8d1
Create Date: 2026-10-24 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3a1f8b92c45'
down_revision: Union[str, Sequence[str], None] = '5c0a9a22f8d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('video_id', sa.String(length=64), sa.ForeignKey('videos.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=False),
        sa.Column('sources', sa.JSON(), nullable=False),
        sa.Column('model_used', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 2. Indexes for fast user-scoped and video-scoped conversation retrieval
    op.create_index('ix_chat_messages_video_id', 'chat_messages', ['video_id'])
    op.create_index('ix_chat_messages_user_id', 'chat_messages', ['user_id'])
    op.create_index('ix_chat_messages_user_video', 'chat_messages', ['user_id', 'video_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_chat_messages_user_video', table_name='chat_messages')
    op.drop_index('ix_chat_messages_user_id', table_name='chat_messages')
    op.drop_index('ix_chat_messages_video_id', table_name='chat_messages')
    op.drop_table('chat_messages')
