"""Initial VIDYORA AI persistence schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-05 17:15:00.000000

Establishes relational persistence foundation for:
1. users
2. videos
3. video_transcripts
4. transcript_segments
5. knowledge_chunks
6. quizzes
7. quiz_questions
8. quiz_attempts
9. quiz_answers
10. flashcard_decks
11. flashcards
12. learner_progress
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. users
    # -----------------------------------------------------------------------
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=True),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
        sa.UniqueConstraint('email', name=op.f('uq_users_email')),
        sa.UniqueConstraint('username', name=op.f('uq_users_username')),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # -----------------------------------------------------------------------
    # 2. videos
    # -----------------------------------------------------------------------
    op.create_table(
        'videos',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('platform', sa.String(length=32), nullable=False, server_default='youtube'),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='submitted'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_videos_user_id_users'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_videos')),
    )
    op.create_index(op.f('ix_videos_user_id'), 'videos', ['user_id'], unique=False)
    op.create_index(op.f('ix_videos_status'), 'videos', ['status'], unique=False)
    op.create_index(op.f('ix_videos_created_at'), 'videos', ['created_at'], unique=False)

    # -----------------------------------------------------------------------
    # 3. video_transcripts
    # -----------------------------------------------------------------------
    op.create_table(
        'video_transcripts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('video_id', sa.String(length=64), nullable=False),
        sa.Column('language', sa.String(length=16), nullable=False, server_default='en'),
        sa.Column('is_generated', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('full_text', sa.Text(), nullable=False),
        sa.Column('segment_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cleaned_segment_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], name=op.f('fk_video_transcripts_video_id_videos'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_video_transcripts')),
        sa.UniqueConstraint('video_id', name=op.f('uq_video_transcripts_video_id')),
    )
    op.create_index(op.f('ix_video_transcripts_video_id'), 'video_transcripts', ['video_id'], unique=True)

    # -----------------------------------------------------------------------
    # 4. transcript_segments
    # -----------------------------------------------------------------------
    op.create_table(
        'transcript_segments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('transcript_id', sa.String(length=36), nullable=False),
        sa.Column('segment_index', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('start_time', sa.Float(), nullable=False),
        sa.Column('duration', sa.Float(), nullable=False),
        sa.Column('is_cleaned', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['transcript_id'], ['video_transcripts.id'], name=op.f('fk_transcript_segments_transcript_id_video_transcripts'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_transcript_segments')),
    )
    op.create_index(op.f('ix_transcript_segments_transcript_id'), 'transcript_segments', ['transcript_id'], unique=False)
    op.create_index('ix_transcript_segments_transcript_time', 'transcript_segments', ['transcript_id', 'start_time'], unique=False)
    op.create_index('ix_transcript_segments_transcript_order', 'transcript_segments', ['transcript_id', 'segment_index'], unique=False)

    # -----------------------------------------------------------------------
    # 5. knowledge_chunks
    # -----------------------------------------------------------------------
    op.create_table(
        'knowledge_chunks',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('video_id', sa.String(length=64), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('start_time', sa.Float(), nullable=False),
        sa.Column('end_time', sa.Float(), nullable=False),
        sa.Column('duration', sa.Float(), nullable=False),
        sa.Column('word_count', sa.Integer(), nullable=False),
        sa.Column('segment_start_index', sa.Integer(), nullable=False),
        sa.Column('segment_end_index', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], name=op.f('fk_knowledge_chunks_video_id_videos'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_chunks')),
        sa.UniqueConstraint('video_id', 'chunk_index', name='uq_knowledge_chunks_video_chunk_index'),
    )
    op.create_index(op.f('ix_knowledge_chunks_video_id'), 'knowledge_chunks', ['video_id'], unique=False)
    op.create_index('ix_knowledge_chunks_video_order', 'knowledge_chunks', ['video_id', 'chunk_index'], unique=False)
    op.create_index('ix_knowledge_chunks_video_time', 'knowledge_chunks', ['video_id', 'start_time'], unique=False)

    # -----------------------------------------------------------------------
    # 6. quizzes
    # -----------------------------------------------------------------------
    op.create_table(
        'quizzes',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('video_id', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('model_used', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], name=op.f('fk_quizzes_video_id_videos'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_quizzes')),
    )
    op.create_index(op.f('ix_quizzes_video_id'), 'quizzes', ['video_id'], unique=False)
    op.create_index(op.f('ix_quizzes_created_at'), 'quizzes', ['created_at'], unique=False)

    # -----------------------------------------------------------------------
    # 7. quiz_questions
    # -----------------------------------------------------------------------
    op.create_table(
        'quiz_questions',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('quiz_id', sa.String(length=64), nullable=False),
        sa.Column('source_chunk_id', sa.String(length=64), nullable=True),
        sa.Column('question_order', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('options', sa.JSON(), nullable=False),
        sa.Column('correct_answer', sa.Text(), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('difficulty', sa.String(length=16), nullable=False, server_default='medium'),
        sa.Column('source_timestamp', sa.Float(), nullable=False),
        sa.Column('source_formatted_time', sa.String(length=16), nullable=False),
        sa.Column('source_label', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['quiz_id'], ['quizzes.id'], name=op.f('fk_quiz_questions_quiz_id_quizzes'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_chunk_id'], ['knowledge_chunks.id'], name=op.f('fk_quiz_questions_source_chunk_id_knowledge_chunks'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_quiz_questions')),
    )
    op.create_index(op.f('ix_quiz_questions_quiz_id'), 'quiz_questions', ['quiz_id'], unique=False)
    op.create_index(op.f('ix_quiz_questions_source_chunk_id'), 'quiz_questions', ['source_chunk_id'], unique=False)
    op.create_index('ix_quiz_questions_quiz_order', 'quiz_questions', ['quiz_id', 'question_order'], unique=False)

    # -----------------------------------------------------------------------
    # 8. quiz_attempts
    # -----------------------------------------------------------------------
    op.create_table(
        'quiz_attempts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('quiz_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('total_questions', sa.Integer(), nullable=False),
        sa.Column('correct_count', sa.Integer(), nullable=False),
        sa.Column('score_percentage', sa.Float(), nullable=False),
        sa.Column('performance_tier', sa.String(length=32), nullable=False),
        sa.Column('performance_summary', sa.Text(), nullable=True),
        sa.Column('weak_chunk_ids', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['quiz_id'], ['quizzes.id'], name=op.f('fk_quiz_attempts_quiz_id_quizzes'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_quiz_attempts_user_id_users'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_quiz_attempts')),
    )
    op.create_index(op.f('ix_quiz_attempts_quiz_id'), 'quiz_attempts', ['quiz_id'], unique=False)
    op.create_index(op.f('ix_quiz_attempts_user_id'), 'quiz_attempts', ['user_id'], unique=False)
    op.create_index(op.f('ix_quiz_attempts_created_at'), 'quiz_attempts', ['created_at'], unique=False)

    # -----------------------------------------------------------------------
    # 9. quiz_answers
    # -----------------------------------------------------------------------
    op.create_table(
        'quiz_answers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('attempt_id', sa.String(length=36), nullable=False),
        sa.Column('question_id', sa.String(length=64), nullable=False),
        sa.Column('selected_answer', sa.Text(), nullable=True),
        sa.Column('is_correct', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['attempt_id'], ['quiz_attempts.id'], name=op.f('fk_quiz_answers_attempt_id_quiz_attempts'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['quiz_questions.id'], name=op.f('fk_quiz_answers_question_id_quiz_questions'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_quiz_answers')),
        sa.UniqueConstraint('attempt_id', 'question_id', name='uq_quiz_answers_attempt_question'),
    )
    op.create_index(op.f('ix_quiz_answers_attempt_id'), 'quiz_answers', ['attempt_id'], unique=False)
    op.create_index(op.f('ix_quiz_answers_question_id'), 'quiz_answers', ['question_id'], unique=False)

    # -----------------------------------------------------------------------
    # 10. flashcard_decks
    # -----------------------------------------------------------------------
    op.create_table(
        'flashcard_decks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('video_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('topic', sa.String(length=255), nullable=False),
        sa.Column('model_used', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_flashcard_decks_user_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], name=op.f('fk_flashcard_decks_video_id_videos'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_flashcard_decks')),
    )
    op.create_index(op.f('ix_flashcard_decks_video_id'), 'flashcard_decks', ['video_id'], unique=False)
    op.create_index(op.f('ix_flashcard_decks_user_id'), 'flashcard_decks', ['user_id'], unique=False)

    # -----------------------------------------------------------------------
    # 11. flashcards
    # -----------------------------------------------------------------------
    op.create_table(
        'flashcards',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('deck_id', sa.String(length=36), nullable=False),
        sa.Column('source_chunk_id', sa.String(length=64), nullable=True),
        sa.Column('card_order', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('front', sa.Text(), nullable=False),
        sa.Column('back', sa.Text(), nullable=False),
        sa.Column('difficulty', sa.String(length=16), nullable=False, server_default='medium'),
        sa.Column('source_timestamp', sa.Float(), nullable=False),
        sa.Column('source_formatted_time', sa.String(length=16), nullable=False),
        sa.Column('source_label', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['deck_id'], ['flashcard_decks.id'], name=op.f('fk_flashcards_deck_id_flashcard_decks'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_chunk_id'], ['knowledge_chunks.id'], name=op.f('fk_flashcards_source_chunk_id_knowledge_chunks'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_flashcards')),
    )
    op.create_index(op.f('ix_flashcards_deck_id'), 'flashcards', ['deck_id'], unique=False)
    op.create_index(op.f('ix_flashcards_source_chunk_id'), 'flashcards', ['source_chunk_id'], unique=False)
    op.create_index('ix_flashcards_deck_order', 'flashcards', ['deck_id', 'card_order'], unique=False)

    # -----------------------------------------------------------------------
    # 12. learner_progress
    # -----------------------------------------------------------------------
    op.create_table(
        'learner_progress',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('video_id', sa.String(length=64), nullable=False),
        sa.Column('chunk_id', sa.String(length=64), nullable=True),
        sa.Column('mastery_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('review_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('needs_revision', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['chunk_id'], ['knowledge_chunks.id'], name=op.f('fk_learner_progress_chunk_id_knowledge_chunks'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_learner_progress_user_id_users'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], name=op.f('fk_learner_progress_video_id_videos'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_learner_progress')),
        sa.UniqueConstraint('user_id', 'video_id', 'chunk_id', name='uq_learner_progress_user_video_chunk'),
    )
    op.create_index(op.f('ix_learner_progress_user_id'), 'learner_progress', ['user_id'], unique=False)
    op.create_index(op.f('ix_learner_progress_video_id'), 'learner_progress', ['video_id'], unique=False)
    op.create_index(op.f('ix_learner_progress_chunk_id'), 'learner_progress', ['chunk_id'], unique=False)
    op.create_index('ix_learner_progress_user_mastery', 'learner_progress', ['user_id', 'mastery_score'], unique=False)
    op.create_index('ix_learner_progress_revision', 'learner_progress', ['user_id', 'needs_revision'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse topological order (children before parents)
    op.drop_table('learner_progress')
    op.drop_table('flashcards')
    op.drop_table('flashcard_decks')
    op.drop_table('quiz_answers')
    op.drop_table('quiz_attempts')
    op.drop_table('quiz_questions')
    op.drop_table('quizzes')
    op.drop_table('knowledge_chunks')
    op.drop_table('transcript_segments')
    op.drop_table('video_transcripts')
    op.drop_table('videos')
    op.drop_table('users')
