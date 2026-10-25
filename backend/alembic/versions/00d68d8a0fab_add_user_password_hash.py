"""add_user_password_hash

Revision ID: 00d68d8a0fab
Revises: cb24951c81ab
Create Date: 2026-10-07 12:59:55.013665

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '00d68d8a0fab'
down_revision: Union[str, Sequence[str], None] = 'cb24951c81ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add hashed_password to users table."""
    op.add_column('users', sa.Column('hashed_password', sa.String(length=255), nullable=False))


def downgrade() -> None:
    """Downgrade schema: remove hashed_password from users table."""
    op.drop_column('users', 'hashed_password')
