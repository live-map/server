"""add post counters, post_likes, and post_media tables

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-02-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6g7h8"
down_revision: str | None = "b2c3d4e5f6g7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add 4 counter columns to posts, create post_likes and post_media tables."""
    # 1. Add denormalized counter columns to posts
    op.add_column("posts", sa.Column("like_count", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column("posts", sa.Column("view_count", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column("posts", sa.Column("comment_count", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column("posts", sa.Column("popularity_score", sa.Float(), nullable=False, server_default=sa.text("0.0")))

    # 2. Create MediaType enum (if not exists)
    media_type_enum = postgresql.ENUM("IMAGE", "VIDEO", name="MediaType", create_type=False)
    media_type_enum.create(op.get_bind(), checkfirst=True)

    # 3. Create post_likes table
    op.create_table(
        "post_likes",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("post_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(length=25), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id", "user_id", name="uq_post_like_post_user"),
    )
    op.create_index(op.f("ix_post_likes_post_id"), "post_likes", ["post_id"], unique=False)
    op.create_index(op.f("ix_post_likes_user_id"), "post_likes", ["user_id"], unique=False)

    # 4. Create post_media table
    op.create_table(
        "post_media",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("post_id", sa.UUID(), nullable=False),
        sa.Column("media_type", media_type_enum, nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("thumbnail_url", sa.String(length=1000), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_post_media_post_id"), "post_media", ["post_id"], unique=False)
    op.create_index("ix_post_media_post_id_order", "post_media", ["post_id", "order"], unique=False)


def downgrade() -> None:
    """Remove post_media, post_likes tables and counter columns from posts."""
    op.drop_index("ix_post_media_post_id_order", table_name="post_media")
    op.drop_index(op.f("ix_post_media_post_id"), table_name="post_media")
    op.drop_table("post_media")

    op.drop_index(op.f("ix_post_likes_user_id"), table_name="post_likes")
    op.drop_index(op.f("ix_post_likes_post_id"), table_name="post_likes")
    op.drop_table("post_likes")

    op.drop_column("posts", "popularity_score")
    op.drop_column("posts", "comment_count")
    op.drop_column("posts", "view_count")
    op.drop_column("posts", "like_count")
