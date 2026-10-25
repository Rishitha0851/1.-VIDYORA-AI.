"""widen_quiz_question_id_to_128

Revision ID: 5c0a9a22f8d1
Revises: 7a8e9d1f3b20
Create Date: 2026-10-17 20:49:52.368958

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c0a9a22f8d1'
down_revision: Union[str, Sequence[str], None] = '7a8e9d1f3b20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: widen QuizQuestion.id and QuizAnswer.question_id to VARCHAR(128)."""
    # 1. Drop foreign key constraint referencing quiz_questions.id
    op.drop_constraint('fk_quiz_answers_question_id_quiz_questions', 'quiz_answers', type_='foreignkey')

    # 2. Alter primary key column on quiz_questions
    op.alter_column(
        'quiz_questions',
        'id',
        existing_type=sa.String(length=64),
        type_=sa.String(length=128),
        existing_nullable=False,
    )

    # 3. Alter foreign key column on quiz_answers
    op.alter_column(
        'quiz_answers',
        'question_id',
        existing_type=sa.String(length=64),
        type_=sa.String(length=128),
        existing_nullable=False,
    )

    # 4. Re-create foreign key constraint
    op.create_foreign_key(
        'fk_quiz_answers_question_id_quiz_questions',
        'quiz_answers',
        'quiz_questions',
        ['question_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    """Downgrade schema: revert QuizQuestion.id and QuizAnswer.question_id to VARCHAR(64)."""
    # 1. Drop foreign key constraint referencing quiz_questions.id
    op.drop_constraint('fk_quiz_answers_question_id_quiz_questions', 'quiz_answers', type_='foreignkey')

    # 2. Alter foreign key column on quiz_answers
    op.alter_column(
        'quiz_answers',
        'question_id',
        existing_type=sa.String(length=128),
        type_=sa.String(length=64),
        existing_nullable=False,
    )

    # 3. Alter primary key column on quiz_questions
    op.alter_column(
        'quiz_questions',
        'id',
        existing_type=sa.String(length=128),
        type_=sa.String(length=64),
        existing_nullable=False,
    )

    # 4. Re-create foreign key constraint
    op.create_foreign_key(
        'fk_quiz_answers_question_id_quiz_questions',
        'quiz_answers',
        'quiz_questions',
        ['question_id'],
        ['id'],
        ondelete='CASCADE',
    )
