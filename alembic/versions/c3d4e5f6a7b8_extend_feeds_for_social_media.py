"""Extend feeds table for social media sources

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-01-12 12:30:00.000000

This migration extends the feeds table to support:
- Social media platform tracking (Telegram, X)
- Channel foreign key relationship
- Stage 0 preprocessing results
- Repost detection fields
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add social media and Stage 0 fields to feeds table."""

    # === Social Media Source Fields ===
    op.add_column('feeds', sa.Column('platform', sa.String(50), nullable=True))
    op.add_column('feeds', sa.Column('channel_id', sa.Integer(), nullable=True))
    op.add_column('feeds', sa.Column('original_message_id', sa.String(255), nullable=True))
    op.add_column('feeds', sa.Column('is_repost', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('feeds', sa.Column('original_source_id', sa.String(255), nullable=True))
    op.add_column('feeds', sa.Column('channel_credibility_score', sa.Float(), nullable=True))

    # === Stage 0: Preprocessing Results ===
    op.add_column('feeds', sa.Column('stage0_completed', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('feeds', sa.Column('normalized_text', sa.Text(), nullable=True))
    op.add_column('feeds', sa.Column('extracted_coordinates', sa.Text(), nullable=True))
    op.add_column('feeds', sa.Column('detected_terminology', sa.Text(), nullable=True))

    # === Foreign Key ===
    op.create_foreign_key(
        'fk_feeds_channel_id',
        'feeds', 'channels',
        ['channel_id'], ['id'],
        ondelete='SET NULL'
    )

    # === Indexes ===
    op.create_index('ix_feeds_platform', 'feeds', ['platform'], unique=False)
    op.create_index('ix_feeds_channel_id', 'feeds', ['channel_id'], unique=False)


def downgrade() -> None:
    """Remove social media and Stage 0 fields from feeds table."""

    # Drop indexes
    op.drop_index('ix_feeds_channel_id', table_name='feeds')
    op.drop_index('ix_feeds_platform', table_name='feeds')

    # Drop foreign key
    op.drop_constraint('fk_feeds_channel_id', 'feeds', type_='foreignkey')

    # Drop Stage 0 columns
    op.drop_column('feeds', 'detected_terminology')
    op.drop_column('feeds', 'extracted_coordinates')
    op.drop_column('feeds', 'normalized_text')
    op.drop_column('feeds', 'stage0_completed')

    # Drop social media columns
    op.drop_column('feeds', 'channel_credibility_score')
    op.drop_column('feeds', 'original_source_id')
    op.drop_column('feeds', 'is_repost')
    op.drop_column('feeds', 'original_message_id')
    op.drop_column('feeds', 'channel_id')
    op.drop_column('feeds', 'platform')
