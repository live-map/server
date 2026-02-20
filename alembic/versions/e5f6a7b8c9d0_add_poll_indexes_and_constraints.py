"""add poll indexes and check constraints

Revision ID: e5f6a7b8c9d0
Revises: f1a2b3c4d5e6
Create Date: 2026-02-17 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite index and check constraints to polls table."""
    # B-2: Composite index for status + total_votes (hot debate query optimization)
    op.create_index(
        'ix_polls_status_total_votes',
        'polls',
        ['status', 'total_votes'],
    )

    # C-15: Check constraints for non-negative counters
    op.create_check_constraint(
        'ck_polls_total_votes_non_negative',
        'polls',
        'total_votes >= 0',
    )
    op.create_check_constraint(
        'ck_polls_view_count_non_negative',
        'polls',
        'view_count >= 0',
    )



def downgrade() -> None:
    """Remove indexes and constraints."""
    op.drop_constraint('ck_polls_view_count_non_negative', 'polls', type_='check')
    op.drop_constraint('ck_polls_total_votes_non_negative', 'polls', type_='check')
    op.drop_index('ix_polls_status_total_votes', table_name='polls')
