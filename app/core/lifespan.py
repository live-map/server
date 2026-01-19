"""
Application lifespan events.

Handles startup and shutdown operations.
- Configures logging
- Starts scheduled scanner (every 15 minutes)
- Runs initial scan on startup
"""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agent.config import agent_settings

logger = logging.getLogger(__name__)

# Global task reference for cleanup
_scanner_task: asyncio.Task | None = None


def setup_logging():
    """Configure logging to show all agent activity."""
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Console handler with detailed format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(formatter)

    # Clear existing handlers and add new one
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)

    # Set specific loggers
    logging.getLogger("app").setLevel(logging.DEBUG)
    logging.getLogger("app.agent").setLevel(logging.DEBUG)

    # Reduce noise from libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


async def run_scheduled_scan():
    """Run a single scan cycle and trigger investigations for significant events."""
    from app.agent import InvestigationAgent, NewsScanner

    print("\n" + "=" * 60)
    print("[SCANNER] Starting scheduled scan...")
    print("=" * 60)

    try:
        scanner = NewsScanner()
        events = await scanner.scan_all_sources()

        if not events:
            print("[SCANNER] No significant events found")
            return

        print(f"[SCANNER] Found {len(events)} significant events")

        # Show detected events
        for i, event in enumerate(events):
            desc = event.get("description", "N/A")
            cat = event.get("category", "other")
            sources = event.get("sources", [])
            print(f"  [{i+1}] [{cat.upper()}] {desc[:80]}")
            print(f"       Sources: {', '.join(sources[:3])}")

        # Start investigation for each significant event
        agent = InvestigationAgent()
        for i, event in enumerate(events[:3]):  # Limit to 3 investigations per scan
            event_desc = event.get("description") or event.get("title", "Unknown event")
            category = event.get("category", "other")

            print(f"\n[SCANNER] [{i+1}] Investigating: {event_desc[:80]}...")

            try:
                # Add timeout to investigation (5 minutes max)
                report = await asyncio.wait_for(
                    agent.investigate(
                        event=event_desc,
                        category=category,
                    ),
                    timeout=300.0,  # 5 minutes
                )

                # Output the investigation report
                print("\n" + "=" * 70)
                print(f"📰 REPORT [{i+1}] - {category.upper()}")
                print("=" * 70)

                print(f"\n📝 SUMMARY: {report.event_summary}")

                if report.location:
                    print(f"📍 LOCATION: {report.location}")

                if report.timeline:
                    print(f"\n⏱️ TIMELINE:")
                    for item in report.timeline[:5]:
                        print(f"  • {item}")

                if report.verified_facts:
                    print(f"\n✅ VERIFIED FACTS ({len(report.verified_facts)}):")
                    for fact in report.verified_facts[:5]:
                        claim = fact.get("claim", str(fact))
                        confidence = fact.get("confidence", "N/A")
                        print(f"  • {claim[:100]}")
                        print(f"    Confidence: {confidence}")

                if report.unverified_claims:
                    print(f"\n⚠️ UNVERIFIED ({len(report.unverified_claims)}):")
                    for claim in report.unverified_claims[:3]:
                        print(f"  • {claim[:100]}")

                if report.sources:
                    print(f"\n📰 SOURCES ({len(report.sources)}):")
                    for source in report.sources[:10]:
                        print(f"  • {source}")

                if report.media:
                    print(f"\n🎬 MEDIA: {len(report.media)} items")

                print("\n" + "=" * 70 + "\n")

            except asyncio.TimeoutError:
                print(f"[SCANNER] [{i+1}] Investigation timed out after 5 minutes")
                logger.error(f"Investigation timed out for: {event_desc[:50]}")
            except Exception as e:
                print(f"[SCANNER] [{i+1}] Investigation failed: {e}")
                import traceback
                traceback.print_exc()

    except Exception as e:
        print(f"[SCANNER] Scan failed: {e}")
        import traceback
        traceback.print_exc()


async def scanner_loop():
    """Run scanner in a loop every N minutes with error recovery."""
    interval = agent_settings.scan_interval_minutes * 60  # Convert to seconds
    retry_delay = 60  # Wait 60s before retrying after error

    print(f"\n[SCHEDULER] Scanner will run every {agent_settings.scan_interval_minutes} minutes")
    print("[SCHEDULER] Running initial scan NOW...\n")

    # Run immediately on startup
    try:
        await run_scheduled_scan()
    except Exception as e:
        logger.error(f"[SCHEDULER] Initial scan failed: {e}")
        print(f"[SCHEDULER] Initial scan failed: {e}")

    # Then run on schedule with error recovery
    while True:
        print(f"\n[SCHEDULER] Next scan in {agent_settings.scan_interval_minutes} minutes...")
        await asyncio.sleep(interval)
        try:
            await run_scheduled_scan()
        except Exception as e:
            logger.error(f"[SCHEDULER] Scan failed, retrying in {retry_delay}s: {e}")
            print(f"[SCHEDULER] Scan failed: {e}")
            await asyncio.sleep(retry_delay)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    global _scanner_task

    # Setup logging first
    setup_logging()

    # Validate required configuration
    if not agent_settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is required. Please set it in your environment or .env file."
        )

    print("\n" + "=" * 60)
    print("  LIVEMAP API - Starting...")
    print("=" * 60)
    print(f"  LLM Model: {agent_settings.llm_model}")
    print(f"  Scan Interval: {agent_settings.scan_interval_minutes} min")
    print(f"  GDELT Enabled: {agent_settings.gdelt_enabled}")
    print(f"  Twitter Enabled: {agent_settings.twitter_enabled}")
    print(f"  Telegram Enabled: {agent_settings.telegram_enabled}")
    print(f"  OpenAI API Key: {'✓ Set' if agent_settings.openai_api_key else '✗ Missing'}")
    print("=" * 60 + "\n")

    # Start scanner in background
    _scanner_task = asyncio.create_task(scanner_loop())

    yield

    # Cleanup on shutdown with timeouts
    if _scanner_task:
        print("\n[SCHEDULER] Stopping scanner...")
        _scanner_task.cancel()
        try:
            await asyncio.wait_for(_scanner_task, timeout=10.0)
        except asyncio.CancelledError:
            pass
        except asyncio.TimeoutError:
            logger.warning("Scanner task did not cancel within 10s")

    # Dispose DB engine with timeout
    try:
        from app.core.database import engine
        await asyncio.wait_for(engine.dispose(), timeout=10.0)
    except asyncio.TimeoutError:
        logger.warning("Database dispose timed out after 10s")

    print("[SHUTDOWN] Livemap API stopped.")
