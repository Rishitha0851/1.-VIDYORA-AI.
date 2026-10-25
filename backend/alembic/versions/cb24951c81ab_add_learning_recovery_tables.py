"""add_learning_recovery_tables

Revision ID: cb24951c81ab
Revises: 0001_initial_schema
Create Date: 2026-10-05 21:25:01.485458

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cb24951c81ab'
down_revision: Union[str, Sequence[str], None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('learning_recovery_sessions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('video_id', sa.String(length=64), nullable=False),
        sa.Column('chunk_id', sa.String(length=64), nullable=False),
        sa.Column('source_timestamp', sa.Float(), nullable=False),
        sa.Column('source_formatted_time', sa.String(length=16), nullable=False),
        sa.Column('originating_evidence', sa.Text(), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='CREATED'),
        sa.Column('explanation_title', sa.String(length=255), nullable=True),
        sa.Column('targeted_explanation', sa.Text(), nullable=True),
        sa.Column('worked_example', sa.Text(), nullable=True),
        sa.Column('key_takeaway', sa.Text(), nullable=True),
        sa.Column('micro_quiz_data', sa.JSON(), nullable=True),
        sa.Column('pre_recovery_accuracy', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('post_recovery_accuracy', sa.Float(), nullable=True),
        sa.Column('absolute_improvement', sa.Float(), nullable=True),
        sa.Column('total_questions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('correct_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('recovery_result', sa.String(length=32), nullable=True),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['chunk_id'], ['knowledge_chunks.id'], name=op.f('fk_learning_recovery_sessions_chunk_id_knowledge_chunks'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_learning_recovery_sessions_user_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], name=op.f('fk_learning_recovery_sessions_video_id_videos'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_learning_recovery_sessions'))
    )
    op.create_index(op.f('ix_learning_recovery_sessions_chunk_id'), 'learning_recovery_sessions', ['chunk_id'], unique=False)
    op.create_index(op.f('ix_learning_recovery_sessions_status'), 'learning_recovery_sessions', ['status'], unique=False)
    op.create_index(op.f('ix_learning_recovery_sessions_user_id'), 'learning_recovery_sessions', ['user_id'], unique=False)
    op.create_index(op.f('ix_learning_recovery_sessions_video_id'), 'learning_recovery_sessions', ['video_id'], unique=False)
    op.create_index('ix_recovery_video_chunk', 'learning_recovery_sessions', ['video_id', 'chunk_id'], unique=False)

    op.create_table('recovery_quiz_answers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('question_id', sa.String(length=64), nullable=False),
        sa.Column('selected_answer', sa.Text(), nullable=True),
        sa.Column('is_correct', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['learning_recovery_sessions.id'], name=op.f('fk_recovery_quiz_answers_session_id_learning_recovery_sessions'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_recovery_quiz_answers'))
    )
    op.create_index(op.f('ix_recovery_quiz_answers_session_id'), 'recovery_quiz_answers', ['session_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_recovery_quiz_answers_session_id'), table_name='recovery_quiz_answers')
    op.drop_table('recovery_quiz_answers')
    op.drop_index('ix_recovery_video_chunk', table_name='learning_recovery_sessions')
    op.drop_index(op.f('ix_learning_recovery_sessions_video_id'), table_name='learning_recovery_sessions')
    op.drop_index(op.f('ix_learning_recovery_sessions_user_id'), table_name='learning_recovery_sessions')
    op.drop_index(op.f('ix_learning_recovery_sessions_status'), table_name='learning_recovery_sessions')
    op.drop_index(op.f('ix_learning_recovery_sessions_chunk_id'), table_name='learning_recovery_sessions')
    op.drop_table('learning_recovery_sessions')
