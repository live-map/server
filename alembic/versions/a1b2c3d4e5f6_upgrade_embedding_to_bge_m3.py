"""Upgrade embedding to BGE-M3 (1024 dimensions)

Revision ID: a1b2c3d4e5f6
Revises: 026b33487ab5
Create Date: 2026-01-11 22:30:00.000000

This migration upgrades the embedding model from all-MiniLM-L6-v2 (384 dim)
to BGE-M3 (1024 dim) for better multilingual support and accuracy.

BREAKING CHANGE: Existing embeddings will be cleared and need re-generation.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '026b33487ab5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade embedding column from 384 to 1024 dimensions.

    Steps:
    1. Clear existing embeddings (incompatible with new model)
    2. Drop old embedding column
    3. Create new embedding column with 1024 dimensions

    Note: All feeds will need re-verification to generate new embeddings.
    """
    # Step 1: Clear existing embeddings
    op.execute("UPDATE feeds SET embedding = NULL")

    # Step 2: Drop old column
    op.drop_column('feeds', 'embedding')

    # Step 3: Create new column with 1024 dimensions (BGE-M3)
    op.add_column('feeds', sa.Column('embedding', sa.Text(), nullable=True))


def downgrade() -> None:
    """
    Downgrade embedding column from 1024 to 384 dimensions.

    Note: This will lose all BGE-M3 embeddings.
    """
    # Clear embeddings
    op.execute("UPDATE feeds SET embedding = NULL")

    # Drop new column
    op.drop_column('feeds', 'embedding')

    # Recreate old column with 384 dimensions
    op.add_column('feeds', sa.Column('embedding', sa.Text(), nullable=True))
