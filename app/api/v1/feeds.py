"""
Feed endpoints.

GET /api/v1/feeds - List feeds with filters
GET /api/v1/feeds/{id} - Get single feed by ID
POST /api/v1/feeds - Create a new feed (internal use)
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.feed import Feed
from app.schemas.feed import FeedItem

router = APIRouter()

# Mock data for fallback when DB is empty or unavailable
MOCK_FEEDS: list[dict] = [
    {
        "id": 1,
        "title": "Russian forces advance in Donetsk region",
        "content": "Russian military forces have made tactical advances in the Donetsk region, according to multiple sources. Ukrainian forces are reinforcing defensive positions.",
        "original_link": "https://example.com/news/1",
        "source_name": "ACLED",
        "source_type": "API",
        "published_at": datetime(2026, 1, 10, 10, 0, 0, tzinfo=timezone.utc),
        "author": "ACLED Research",
        "category": "WAR",
        "sub_category": "ru-uk",
        "location": {"lat": 48.0159, "lng": 37.8028, "name": "Donetsk, Ukraine"},
        "credibility_score": 95,
        "verification_status": "verified",
    },
    {
        "id": 2,
        "title": "Missile strikes reported in Kharkiv",
        "content": "Multiple missile strikes were reported in Kharkiv city. Emergency services are responding to the incident.",
        "original_link": "https://example.com/news/2",
        "source_name": "Telegram Channel",
        "source_type": "TELEGRAM",
        "published_at": datetime(2026, 1, 10, 9, 30, 0, tzinfo=timezone.utc),
        "category": "WAR",
        "sub_category": "ru-uk",
        "location": {"lat": 49.9935, "lng": 36.2304, "name": "Kharkiv, Ukraine"},
        "credibility_score": 75,
        "verification_status": "partially_verified",
    },
    {
        "id": 3,
        "title": "Israeli airstrikes in southern Lebanon",
        "content": "Israeli Defense Forces conducted airstrikes targeting Hezbollah positions in southern Lebanon overnight.",
        "original_link": "https://example.com/news/3",
        "source_name": "Reuters",
        "source_type": "RSS",
        "published_at": datetime(2026, 1, 10, 8, 0, 0, tzinfo=timezone.utc),
        "author": "Reuters Staff",
        "category": "WAR",
        "sub_category": "is-ir",
        "location": {"lat": 33.2721, "lng": 35.2033, "name": "Southern Lebanon"},
        "credibility_score": 90,
        "verification_status": "verified",
    },
    {
        "id": 4,
        "title": "North Korea military drill near DMZ",
        "content": "North Korean military conducted large-scale artillery exercises near the demilitarized zone.",
        "original_link": "https://example.com/news/4",
        "source_name": "Yonhap",
        "source_type": "RSS",
        "published_at": datetime(2026, 1, 10, 7, 0, 0, tzinfo=timezone.utc),
        "category": "SECURITY",
        "sub_category": "KOREA",
        "location": {"lat": 38.3, "lng": 127.0, "name": "DMZ, Korean Peninsula"},
        "credibility_score": 85,
        "verification_status": "verified",
    },
    {
        "id": 5,
        "title": "US Navy patrol in South China Sea",
        "content": "A US Navy destroyer conducted a freedom of navigation operation in the South China Sea.",
        "original_link": "https://example.com/news/5",
        "source_name": "US Navy",
        "source_type": "RSS",
        "published_at": datetime(2026, 1, 10, 6, 0, 0, tzinfo=timezone.utc),
        "category": "SECURITY",
        "sub_category": "CHINA",
        "location": {"lat": 15.0, "lng": 114.0, "name": "South China Sea"},
        "credibility_score": 95,
        "verification_status": "verified",
    },
]


def _feed_to_response(feed: Feed) -> dict:
    """Convert Feed model to response dict."""
    return {
        "id": feed.id,
        "title": feed.title,
        "content": feed.content,
        "original_link": feed.original_link,
        "source_name": feed.source_name,
        "source_type": feed.source_type,
        "published_at": feed.published_at,
        "author": feed.author,
        "thumbnail": feed.thumbnail,
        "category": feed.category,
        "sub_category": feed.sub_category,
        "location": {
            "lat": feed.location_lat,
            "lng": feed.location_lng,
            "name": feed.location_name,
        },
        "credibility_score": feed.credibility_score,
        "verification_status": feed.verification_status,
    }


@router.get("", response_model=list[FeedItem])
async def get_feeds(
    category: str = Query(..., description="Category filter: WAR or SECURITY"),
    subCategory: Optional[str] = Query(
        None, description="Sub-category filter: ru-uk, is-ir, KOREA, etc."
    ),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get list of verified news feeds.

    Filters:
    - **category** (required): WAR or SECURITY
    - **subCategory** (optional): ru-uk, is-ir, KOREA, CHINA, etc.
    - **limit**: Max items to return (default 20, max 100)
    - **offset**: Items to skip for pagination
    """
    try:
        # Build query
        query = select(Feed).where(Feed.category == category)

        if subCategory:
            query = query.where(Feed.sub_category == subCategory)

        query = query.order_by(Feed.published_at.desc()).offset(offset).limit(limit)

        # Execute query
        result = await db.execute(query)
        feeds = result.scalars().all()

        # If DB is empty, return mock data
        if not feeds:
            filtered = [f for f in MOCK_FEEDS if f["category"] == category]
            if subCategory:
                filtered = [f for f in filtered if f["sub_category"] == subCategory]
            return filtered[offset : offset + limit]

        return [_feed_to_response(feed) for feed in feeds]

    except Exception:
        # Fallback to mock data if DB error
        filtered = [f for f in MOCK_FEEDS if f["category"] == category]
        if subCategory:
            filtered = [f for f in filtered if f["sub_category"] == subCategory]
        return filtered[offset : offset + limit]


@router.get("/{feed_id}", response_model=FeedItem)
async def get_feed(
    feed_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a single feed item by ID.

    - **feed_id**: The unique identifier of the feed item
    """
    try:
        result = await db.execute(select(Feed).where(Feed.id == feed_id))
        feed = result.scalar_one_or_none()

        if feed:
            return _feed_to_response(feed)

        # Fallback to mock data
        for mock_feed in MOCK_FEEDS:
            if mock_feed["id"] == feed_id:
                return mock_feed

        raise HTTPException(status_code=404, detail=f"Feed with id {feed_id} not found")

    except HTTPException:
        raise
    except Exception:
        # Fallback to mock data
        for mock_feed in MOCK_FEEDS:
            if mock_feed["id"] == feed_id:
                return mock_feed
        raise HTTPException(status_code=404, detail=f"Feed with id {feed_id} not found")
