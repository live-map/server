"""
VerificationToken model - mirrors the frontend Prisma VerificationToken schema.

This model stores email verification tokens used by NextAuth.js
for passwordless login and email verification flows.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VerificationToken(Base):
    """
    VerificationToken model matching the frontend Prisma VerificationToken schema.

    Table name: 'verification_tokens' (matches Prisma @@map("verification_tokens"))

    Stores verification tokens for email verification and magic link login.
    Each token is uniquely identified by the combination of identifier and token.
    """

    __tablename__ = "verification_tokens"

    # Composite primary key (identifier + token)
    # Note: Prisma doesn't have an explicit id field, using identifier as part of composite key
    identifier: Mapped[str] = mapped_column(String(255), primary_key=True)
    token: Mapped[str] = mapped_column(String(255), primary_key=True)

    # Token expiration
    expires: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Unique constraint on identifier + token (redundant with composite PK but explicit)
    __table_args__ = (
        UniqueConstraint("identifier", "token", name="verification_tokens_identifier_token_key"),
    )

    def __repr__(self) -> str:
        return f"<VerificationToken(identifier='{self.identifier}', expires='{self.expires}')>"
