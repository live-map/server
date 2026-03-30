"""add poll type_status_created index and option vote_count check

Revision ID: 9f8f68de053d
Revises: 3c0e0a6992fa
Create Date: 2026-03-28

P3-22: Composite index for poll listing queries (type + status + created_at)
P3-23: CHECK constraint for non-negative vote_count on poll_options
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '9f8f68de053d'
down_revision: Union[str, Sequence[str], None] = '3c0e0a6992fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # P3-22: Composite index for poll feed queries
    op.create_index(
        'ix_poll_type_status_created',
        'polls',
        ['type', 'status', 'created_at'],
    )

    # P3-23: CHECK constraint for non-negative vote_count
    op.create_check_constraint(
        'ck_poll_option_vote_count_gte_0',
        'poll_options',
        'vote_count >= 0',
    )


def downgrade() -> None:
    op.drop_constraint('ck_poll_option_vote_count_gte_0', 'poll_options', type_='check')
    op.drop_index('ix_poll_type_status_created', table_name='polls')
