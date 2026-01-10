"""
Background scheduler for periodic tasks.

Runs collection and verification on a schedule.
Default: Every 15 minutes.
"""

import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.feed import Feed
from app.services.collector.telegram import CollectedMessage, TelegramCollector
from app.services.verification.pipeline import VerificationStatus, run_pipeline

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None

# Configuration
COLLECTION_INTERVAL_MINUTES = 15
HOURS_TO_LOOK_BACK = 1
MESSAGES_PER_CHANNEL = 50


async def get_existing_embeddings(db: AsyncSession) -> list[tuple[int, list[float]]]:
    """Get existing embeddings from database for duplicate detection."""
    result = await db.execute(
        select(Feed.id, Feed.embedding).where(Feed.embedding.isnot(None)).limit(1000)
    )
    return [(row[0], row[1]) for row in result.fetchall()]


async def save_verified_feed(
    db: AsyncSession,
    message: CollectedMessage,
    pipeline_result,
) -> Feed | None:
    """Save verified message to database."""
    if pipeline_result.status == VerificationStatus.SKIPPED:
        return None

    # Get primary location
    location_name = None
    location_lat = None
    location_lng = None

    if pipeline_result.locations:
        location_name = pipeline_result.locations[0].get("text")
        # Note: Geocoding would be needed to get lat/lng
        # For now, we just store the name

    feed = Feed(
        title=message.text[:200] if len(message.text) > 200 else message.text,
        content=message.text,
        source_name=message.channel_name,
        source_type="TELEGRAM",
        category="WAR",  # Default, could be classified by LLM
        sub_category="UNCLASSIFIED",
        published_at=message.date,
        location_name=location_name,
        location_lat=location_lat,
        location_lng=location_lng,
        credibility_score=pipeline_result.credibility_score,
        verification_status=pipeline_result.status.value,
        embedding=pipeline_result.embedding,
    )

    db.add(feed)
    await db.commit()
    await db.refresh(feed)

    logger.info(f"Saved feed {feed.id}: {feed.title[:50]}...")
    return feed


async def run_collection_job(channels: list[str] | None = None):
    """
    Run the collection and verification job.

    1. Collect messages from Telegram channels
    2. Run verification pipeline on each message
    3. Save verified messages to database
    """
    logger.info("Starting collection job...")
    start_time = datetime.now(timezone.utc)

    collector = TelegramCollector()

    if not collector.is_configured:
        logger.warning("Telegram not configured, skipping collection")
        return

    try:
        # Collect messages
        messages = await collector.collect_from_channels(
            channels=channels,
            limit_per_channel=MESSAGES_PER_CHANNEL,
            hours_ago=HOURS_TO_LOOK_BACK,
        )

        if not messages:
            logger.info("No new messages to process")
            return

        # Process each message
        async with AsyncSessionLocal() as db:
            # Get existing embeddings for duplicate detection
            existing_embeddings = await get_existing_embeddings(db)

            verified_count = 0
            skipped_count = 0

            for message in messages:
                try:
                    # Run verification
                    result = await run_pipeline(
                        text=message.text,
                        existing_embeddings=existing_embeddings,
                    )

                    if result.status == VerificationStatus.SKIPPED:
                        skipped_count += 1
                        continue

                    # Save to database
                    feed = await save_verified_feed(db, message, result)
                    if feed:
                        verified_count += 1
                        # Add new embedding to list for next iteration
                        if result.embedding:
                            existing_embeddings.append((feed.id, result.embedding))

                except Exception as e:
                    logger.error(f"Failed to process message {message.message_id}: {e}")

            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(
                f"Collection job completed: {verified_count} verified, "
                f"{skipped_count} skipped in {elapsed:.1f}s"
            )

    except Exception as e:
        logger.error(f"Collection job failed: {e}")
    finally:
        await collector.disconnect()


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def start_scheduler(channels: list[str] | None = None):
    """
    Start the background scheduler.

    Args:
        channels: List of Telegram channel usernames to monitor
    """
    scheduler = get_scheduler()

    # Add collection job
    scheduler.add_job(
        run_collection_job,
        trigger=IntervalTrigger(minutes=COLLECTION_INTERVAL_MINUTES),
        id="telegram_collection",
        name="Telegram Collection & Verification",
        replace_existing=True,
        kwargs={"channels": channels},
    )

    scheduler.start()
    logger.info(f"Scheduler started: collecting every {COLLECTION_INTERVAL_MINUTES} minutes")


def stop_scheduler():
    """Stop the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        logger.info("Scheduler stopped")
    _scheduler = None


async def run_once(channels: list[str] | None = None):
    """Run collection job once (for testing)."""
    await run_collection_job(channels=channels)
