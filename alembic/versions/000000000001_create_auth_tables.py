"""Create NextAuth tables (users, accounts, sessions, verification_tokens)

Revision ID: 000000000001
Revises:
Create Date: 2026-01-09 00:00:00.000000

These tables are normally created by Prisma/NextAuth on the frontend,
but we need them in the migration chain since other tables reference users.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '000000000001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create auth tables."""
    # users
    op.create_table(
        'users',
        sa.Column('id', sa.String(25), primary_key=True),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('email', sa.String(255), nullable=True, unique=True, index=True),
        sa.Column('email_verified', sa.DateTime(timezone=True), nullable=True),
        sa.Column('hashed_password', sa.String(255), nullable=True),
        sa.Column('image', sa.String(1000), nullable=True),
        sa.Column('role', sa.String(10), nullable=False, server_default='USER'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # accounts
    op.create_table(
        'accounts',
        sa.Column('id', sa.String(25), primary_key=True),
        sa.Column('user_id', sa.String(25), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', sa.String(255), nullable=False),
        sa.Column('provider', sa.String(255), nullable=False),
        sa.Column('provider_account_id', sa.String(255), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.Integer(), nullable=True),
        sa.Column('token_type', sa.String(255), nullable=True),
        sa.Column('scope', sa.String(255), nullable=True),
        sa.Column('id_token', sa.Text(), nullable=True),
        sa.Column('session_state', sa.String(255), nullable=True),
        sa.UniqueConstraint('provider', 'provider_account_id', name='uq_accounts_provider_account'),
    )

    # sessions
    op.create_table(
        'sessions',
        sa.Column('id', sa.String(25), primary_key=True),
        sa.Column('session_token', sa.String(255), unique=True, nullable=False),
        sa.Column('user_id', sa.String(25), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('expires', sa.DateTime(timezone=True), nullable=False),
    )

    # verification_tokens
    op.create_table(
        'verification_tokens',
        sa.Column('identifier', sa.String(255), primary_key=True),
        sa.Column('token', sa.String(255), primary_key=True),
        sa.Column('expires', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('identifier', 'token', name='verification_tokens_identifier_token_key'),
    )


def downgrade() -> None:
    """Drop auth tables."""
    op.drop_table('verification_tokens')
    op.drop_table('sessions')
    op.drop_table('accounts')
    op.drop_table('users')
