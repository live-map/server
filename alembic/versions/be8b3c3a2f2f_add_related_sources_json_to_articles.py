"""add_related_sources_json_to_articles

Revision ID: be8b3c3a2f2f
Revises: 800e160bd2ed
Create Date: 2026-01-23 22:57:13.656666

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'be8b3c3a2f2f'
down_revision: Union[str, Sequence[str], None] = '800e160bd2ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add related_sources_json column to articles table."""
    op.add_column(
        'articles',
        sa.Column('related_sources_json', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    """Remove related_sources_json column from articles table."""
    op.drop_column('articles', 'related_sources_json')
