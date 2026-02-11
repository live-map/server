"""Add poll tables

Revision ID: f1a2b3c4d5e6
Revises: be8b3c3a2f2f, a9b7b29fc14f
Create Date: 2026-02-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = ('be8b3c3a2f2f', 'a9b7b29fc14f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create poll-related tables."""

    # === polls ===
    op.create_table(
        'polls',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(25), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('image_url', sa.String(1000), nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('type', sa.String(20), nullable=False, server_default='SUGGESTED'),
        sa.Column('status', sa.String(20), nullable=False, server_default='ACTIVE'),
        sa.Column('interaction_type', sa.String(30), nullable=False, server_default='SINGLE_CHOICE'),
        sa.Column('total_votes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('view_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ai_content', sa.Text(), nullable=True),
        sa.Column('ai_updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_polls_user_id', 'polls', ['user_id'])

    # === poll_options ===
    op.create_table(
        'poll_options',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('poll_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('text', sa.String(200), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('vote_count', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['poll_id'], ['polls.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_poll_options_poll_id', 'poll_options', ['poll_id'])

    # === poll_sources ===
    op.create_table(
        'poll_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('poll_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('source_type', sa.String(20), nullable=False, server_default='OTHER'),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['poll_id'], ['polls.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_poll_sources_poll_id', 'poll_sources', ['poll_id'])

    # === votes ===
    op.create_table(
        'votes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(25), nullable=False),
        sa.Column('poll_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('option_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('slider_value', sa.Integer(), nullable=True),
        sa.Column('selected_option_ids', postgresql.JSON(), nullable=True),
        sa.Column('ranking_data', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['poll_id'], ['polls.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['option_id'], ['poll_options.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('user_id', 'poll_id', name='uq_votes_user_poll'),
    )
    op.create_index('ix_votes_user_id', 'votes', ['user_id'])
    op.create_index('ix_votes_poll_id', 'votes', ['poll_id'])

    # === poll_comments ===
    op.create_table(
        'poll_comments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('poll_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(25), nullable=False),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('option_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('likes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('depth', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['poll_id'], ['polls.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_id'], ['poll_comments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['option_id'], ['poll_options.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_poll_comments_poll_id', 'poll_comments', ['poll_id'])
    op.create_index('ix_poll_comments_user_id', 'poll_comments', ['user_id'])
    op.create_index('ix_poll_comments_parent_id', 'poll_comments', ['parent_id'])


def downgrade() -> None:
    """Drop poll-related tables."""
    op.drop_table('poll_comments')
    op.drop_table('votes')
    op.drop_table('poll_sources')
    op.drop_table('poll_options')
    op.drop_table('polls')
