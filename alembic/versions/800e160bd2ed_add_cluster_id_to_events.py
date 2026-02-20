"""add_cluster_id_to_events

Revision ID: 800e160bd2ed
Revises: d4e5f6a7b8c9
Create Date: 2026-01-21 12:18:03.475048

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '800e160bd2ed'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('articles', sa.Column('is_corrected', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('articles', sa.Column('correction_note', sa.Text(), nullable=True))
    op.add_column('articles', sa.Column('corrected_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('articles', sa.Column('original_content_snapshot', sa.Text(), nullable=True))
    op.add_column('events', sa.Column('cluster_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_events_cluster_id'), 'events', ['cluster_id'], unique=False)
    op.add_column('feeds', sa.Column('stage2_verdict', sa.String(length=50), nullable=True))
    op.add_column('feeds', sa.Column('stage2_confidence', sa.Float(), nullable=True))
    op.add_column('feeds', sa.Column('stage2_evidence_summary', sa.Text(), nullable=True))
    op.drop_column('feeds', 'stage2_fact_check_ratings')
    op.drop_column('feeds', 'stage2_has_fact_check')
    op.drop_column('feeds', 'stage2_check_worthy')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('feeds', sa.Column('stage2_check_worthy', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
    op.add_column('feeds', sa.Column('stage2_has_fact_check', sa.BOOLEAN(), autoincrement=False, nullable=False))
    op.add_column('feeds', sa.Column('stage2_fact_check_ratings', sa.TEXT(), autoincrement=False, nullable=True))
    op.drop_column('feeds', 'stage2_evidence_summary')
    op.drop_column('feeds', 'stage2_confidence')
    op.drop_column('feeds', 'stage2_verdict')
    op.drop_index(op.f('ix_events_cluster_id'), table_name='events')
    op.drop_column('events', 'cluster_id')
    op.drop_column('articles', 'original_content_snapshot')
    op.drop_column('articles', 'corrected_at')
    op.drop_column('articles', 'correction_note')
    op.drop_column('articles', 'is_corrected')
