"""seed demo hackathon user + add ai_metrics column

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-02-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d4e5f6g7h8i9"
down_revision: str | None = "c3d4e5f6g7h8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEMO_USER_ID = "demo_hackathon_user"


def upgrade() -> None:
    # Add missing ai_metrics column to polls table
    op.add_column("polls", sa.Column("ai_metrics", postgresql.JSON(), nullable=True))

    # Seed demo user
    op.execute(
        sa.text(
            """
            INSERT INTO users (id, name, email, role, created_at, updated_at)
            VALUES (:id, :name, :email, 'USER', NOW(), NOW())
            ON CONFLICT (id) DO NOTHING
            """
        ).bindparams(
            id=DEMO_USER_ID,
            name="Demo User",
            email="demo@grapoll.kr",
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM users WHERE id = :id").bindparams(id=DEMO_USER_ID)
    )
    op.drop_column("polls", "ai_metrics")
