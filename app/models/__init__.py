"""SQLAlchemy models."""

# Backend domain models
from app.models.post import Post
from app.models.post_media import MediaType, PostMedia
from app.models.post_like import PostLike
from app.models.comment import Comment
from app.models.poll import Poll, PollType, PollStatus, InteractionType
from app.models.poll_option import PollOption
from app.models.poll_source import PollSource, SourceType
from app.models.vote import Vote
from app.models.poll_comment import PollComment
from app.models.poll_comment_like import PollCommentLike

# Auth/NextAuth models (synced with frontend Prisma schema)
from app.models.user import User
from app.models.account import Account
from app.models.session import Session
from app.models.verification_token import VerificationToken

__all__ = [
    # Backend domain models
    "Post",
    "PostMedia",
    "PostLike",
    "MediaType",
    "Comment",
    # Poll models
    "Poll",
    "PollType",
    "PollStatus",
    "InteractionType",
    "PollOption",
    "PollSource",
    "SourceType",
    "Vote",
    "PollComment",
    "PollCommentLike",
    # Auth/NextAuth models
    "User",
    "Account",
    "Session",
    "VerificationToken",
]
