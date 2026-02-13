"""
Run research agent on all polls sequentially.

Usage:
    PYTHONPATH=. uv run python scripts/run_all_research.py
"""

import asyncio
import logging
import time

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.services.research.service import ResearchService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    svc = ResearchService()
    if not svc.enabled:
        print("Research agent is not enabled. Check API keys.")
        return

    # Get all polls
    async with factory() as session:
        result = await session.execute(
            text("SELECT id, title FROM polls WHERE is_deleted = false ORDER BY created_at")
        )
        polls = result.fetchall()

    print(f"\n{'='*60}")
    print(f"Running research agent on {len(polls)} polls")
    print(f"{'='*60}\n")

    success = 0
    failed = 0

    for i, (poll_id, title) in enumerate(polls, 1):
        print(f"[{i:2d}/{len(polls)}] {title}")
        start = time.time()

        try:
            async with factory() as session:
                await svc.run_research(poll_id, session)

            status = svc.get_status(str(poll_id))
            elapsed = time.time() - start

            if status["status"] == "completed":
                print(f"       ✓ Completed in {elapsed:.1f}s")
                success += 1
            else:
                print(f"       ✗ Failed: {status.get('error', 'unknown')}")
                failed += 1

        except Exception as e:
            elapsed = time.time() - start
            print(f"       ✗ Error ({elapsed:.1f}s): {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Done: {success} success, {failed} failed")
    print(f"{'='*60}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
