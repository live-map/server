"""Add events and articles tables for bilingual storage and deduplication

Revision ID: d4e5f6a7b8c9
Revises: a1b2c3d4e5f6
Create Date: 2026-01-21 00:00:00.000000

This migration adds:
1. events table - For tracking unique news events (story chains)
2. articles table - For storing bilingual articles (EN/KO)

Features:
- Event deduplication via hash and semantic similarity
- Bilingual article storage (English + Korean)
- Update detection via fact_hash
- Story chain linking via event_id
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create events and articles tables.
    """
    # === Create events table ===
    op.create_table(
        'events',
        # Primary key
        sa.Column('id', sa.Integer(), primary_key=True, index=True),

        # Unique identifier for fast hash-based lookup
        sa.Column('event_hash', sa.String(64), unique=True, index=True, nullable=False),

        # Canonical title
        sa.Column('canonical_title', sa.String(500), nullable=False),

        # Embedding for semantic similarity (BGE-M3: 1024 dims)
        sa.Column('embedding', sa.Text(), nullable=True),

        # Key facts for update detection
        sa.Column('key_entities', sa.Text(), nullable=True),
        sa.Column('key_facts', sa.Text(), nullable=True),
        sa.Column('fact_hash', sa.String(64), index=True, nullable=False),

        # Classification
        sa.Column('category', sa.String(50), index=True, nullable=False),
        sa.Column('sub_category', sa.String(50), index=True, nullable=True),

        # Statistics
        sa.Column('first_reported_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('article_count', sa.Integer(), default=1, nullable=False),

        # Status
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False, index=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # === Create articles table ===
    op.create_table(
        'articles',
        # Primary key
        sa.Column('id', sa.Integer(), primary_key=True, index=True),

        # Link to event
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False, index=True),

        # Update tracking
        sa.Column('is_update', sa.Boolean(), default=False, nullable=False),
        sa.Column('update_type', sa.String(50), nullable=True),
        sa.Column('update_reason', sa.Text(), nullable=True),

        # === English Content ===
        sa.Column('headline_en', sa.String(500), nullable=False),
        sa.Column('lead_en', sa.Text(), nullable=False),
        sa.Column('nut_graph_en', sa.Text(), nullable=True),
        sa.Column('body_en', sa.Text(), nullable=False),
        sa.Column('full_text_en', sa.Text(), nullable=False),

        # === Korean Content ===
        sa.Column('headline_ko', sa.String(500), nullable=False),
        sa.Column('lead_ko', sa.Text(), nullable=False),
        sa.Column('nut_graph_ko', sa.Text(), nullable=True),
        sa.Column('body_ko', sa.Text(), nullable=False),
        sa.Column('full_text_ko', sa.Text(), nullable=False),

        # === Verification Metadata ===
        sa.Column('claims_total', sa.Integer(), default=0, nullable=False),
        sa.Column('claims_verified', sa.Integer(), default=0, nullable=False),
        sa.Column('claims_refuted', sa.Integer(), default=0, nullable=False),
        sa.Column('claims_unverifiable', sa.Integer(), default=0, nullable=False),
        sa.Column('verification_score', sa.Float(), default=0.0, nullable=False),

        # Source tracking
        sa.Column('source_count', sa.Integer(), default=0, nullable=False),
        sa.Column('sources_json', sa.Text(), nullable=True),

        # === Status ===
        sa.Column('status', sa.String(20), default='published', nullable=False, index=True),
        sa.Column('is_ai_generated', sa.Boolean(), default=True, nullable=False),
        sa.Column('is_human_reviewed', sa.Boolean(), default=False, nullable=False),

        # === Timestamps ===
        sa.Column('published_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )



def downgrade() -> None:
    """
    Drop events and articles tables.
    """
    # Drop tables (articles first due to foreign key)
    op.drop_table('articles')
    op.drop_table('events')
