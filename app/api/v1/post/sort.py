"""
Post Sorting - Sort types, popularity scoring, and dynamic ORDER BY mapping.

Reddit-style time-invariant popularity score:
- Score only changes when engagement (likes/comments/views) changes
- Time component uses absolute creation time, not relative age
- No periodic recomputation needed for time decay
"""

import math
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import desc

from app.models.post import Post

# App epoch for popularity score calculation
EPOCH = datetime(2025, 1, 1, tzinfo=timezone.utc)


class SortType(str, Enum):
    """게시글 정렬 기준."""
    POPULAR = "popular"          # 인기순 (종합 점수)
    NEWEST = "newest"            # 최신순
    MOST_VIEWED = "most_viewed"  # 조회순
    MOST_LIKED = "most_liked"    # 추천순
    DAILY_HOT = "daily_hot"      # 일간 인기순
    WEEKLY_HOT = "weekly_hot"    # 주간 인기순
    MONTHLY_HOT = "monthly_hot"  # 월간 인기순


# Simple sorts: map enum → SQLAlchemy ORDER BY expression
SIMPLE_SORT_MAP: dict[SortType, list] = {
    SortType.POPULAR: [desc(Post.popularity_score), desc(Post.created_at)],
    SortType.NEWEST: [desc(Post.created_at)],
    SortType.MOST_VIEWED: [desc(Post.view_count), desc(Post.created_at)],
    SortType.MOST_LIKED: [desc(Post.like_count), desc(Post.created_at)],
}

# Time-windowed sorts: map enum → timedelta cutoff
TIME_WINDOW_MAP: dict[SortType, timedelta] = {
    SortType.DAILY_HOT: timedelta(days=1),
    SortType.WEEKLY_HOT: timedelta(days=7),
    SortType.MONTHLY_HOT: timedelta(days=30),
}


def compute_popularity_score(
    likes: int,
    comments: int,
    views: int,
    created_at: datetime,
) -> float:
    """
    Reddit-inspired hot score (time-invariant).

    Properties:
    - Logarithmic scaling: first 10 engagements ≈ next 100 ≈ next 1000
    - Time component increases linearly → newer posts naturally rank higher
    - Score never decays on its own → only recompute when engagement changes
    - /45000 divisor ≈ every 12.5 hours, a post needs 10x more engagement

    Args:
        likes: 좋아요 수
        comments: 댓글 수
        views: 조회 수
        created_at: 작성 시각

    Returns:
        float: 인기도 점수
    """
    weighted = likes * 3 + comments * 2 + views * 0.01
    order = math.log10(max(abs(weighted), 1))
    sign = 1 if weighted > 0 else 0

    # Ensure created_at is timezone-aware
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    seconds = (created_at - EPOCH).total_seconds()
    return round(sign * order + seconds / 45000, 7)
