"""add voter_ip to votes

Revision ID: 3c0e0a6992fa
Revises: e5f6g7h8i9j0
Create Date: 2026-03-09 18:06:52.723551

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c0e0a6992fa'
down_revision: Union[str, Sequence[str], None] = 'e5f6g7h8i9j0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('votes', sa.Column('voter_ip', sa.String(length=45), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('votes', 'voter_ip')
