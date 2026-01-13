"""Add channels table for social media source tracking

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-12 12:00:00.000000

This migration creates the channels table to store metadata and
credibility metrics for Telegram channels and X accounts.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create channels table."""
    op.create_table(
        'channels',
        # Primary key
        sa.Column('id', sa.Integer(), nullable=False),

        # Platform identification
        sa.Column('platform', sa.String(50), nullable=False),
        sa.Column('platform_channel_id', sa.String(255), nullable=False),
        sa.Column('username', sa.String(255), nullable=True),
        sa.Column('display_name', sa.String(500), nullable=True),

        # Channel metadata
        sa.Column('subscriber_count', sa.Integer(), nullable=True),
        sa.Column('channel_age_days', sa.Integer(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('description', sa.String(2000), nullable=True),
        sa.Column('language', sa.String(10), nullable=True),

        # Credibility metrics
        sa.Column('credibility_score', sa.Float(), nullable=True),
        sa.Column('tier', sa.Integer(), nullable=False, server_default='5'),

        # Historical accuracy tracking
        sa.Column('total_posts_analyzed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('posts_verified_true', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('posts_verified_false', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('posts_unverifiable', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('historical_accuracy', sa.Float(), nullable=True),

        # Manual overrides
        sa.Column('is_trusted', sa.Boolean(), nullable=True),
        sa.Column('is_blocked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notes', sa.String(2000), nullable=True),

        # Timestamps
        sa.Column('first_seen_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('credibility_updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),

        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('platform', 'platform_channel_id', name='uq_channel_platform_id'),
    )

    # Create indexes
    op.create_index('ix_channels_id', 'channels', ['id'], unique=False)
    op.create_index('ix_channels_platform', 'channels', ['platform'], unique=False)
    op.create_index('ix_channels_tier', 'channels', ['tier'], unique=False)
    op.create_index('ix_channels_credibility_score', 'channels', ['credibility_score'], unique=False)


def downgrade() -> None:
    """Drop channels table."""
    op.drop_index('ix_channels_credibility_score', table_name='channels')
    op.drop_index('ix_channels_tier', table_name='channels')
    op.drop_index('ix_channels_platform', table_name='channels')
    op.drop_index('ix_channels_id', table_name='channels')
    op.drop_table('channels')
