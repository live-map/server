"""
Feed endpoints.

GET /api/v1/feeds - List feeds with filters
GET /api/v1/feeds/{id} - Get single feed by ID
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.feed import FeedItem, FeedResponse

router = APIRouter()

# Mock data for Phase 1 (will be replaced with DB in Phase 2)
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


@router.get("", response_model=list[FeedItem])
async def get_feeds(
    category: str = Query(..., description="Category filter: WAR or SECURITY"),
    subCategory: Optional[str] = Query(
        None, description="Sub-category filter: ru-uk, is-ir, KOREA, etc."
    ),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
):
    """
    Get list of verified news feeds.

    Filters:
    - **category** (required): WAR or SECURITY
    - **subCategory** (optional): ru-uk, is-ir, KOREA, CHINA, etc.
    - **limit**: Max items to return (default 20, max 100)
    - **offset**: Items to skip for pagination
    """
    # Filter by category
    filtered = [f for f in MOCK_FEEDS if f["category"] == category]

    # Filter by sub-category if provided
    if subCategory:
        filtered = [f for f in filtered if f["sub_category"] == subCategory]

    # Apply pagination
    paginated = filtered[offset : offset + limit]

    return paginated


@router.get("/{feed_id}", response_model=FeedItem)
async def get_feed(feed_id: int):
    """
    Get a single feed item by ID.

    - **feed_id**: The unique identifier of the feed item
    """
    for feed in MOCK_FEEDS:
        if feed["id"] == feed_id:
            return feed

    raise HTTPException(status_code=404, detail=f"Feed with id {feed_id} not found")
