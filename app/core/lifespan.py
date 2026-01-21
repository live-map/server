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
    from app.agent import ClaimVerificationAgent, NewsScanner

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

        # Start investigation for each significant event (using v3 Claim-Level Agent)
        agent = ClaimVerificationAgent()
        for i, event in enumerate(events[:3]):  # Limit to 3 investigations per scan
            event_desc = event.get("description") or event.get("title", "Unknown event")
            category = event.get("category", "other")

            print(f"\n[SCANNER] [{i+1}] Investigating: {event_desc[:80]}...")

            try:
                # Add timeout to investigation (5 minutes max)
                result = await asyncio.wait_for(
                    agent.investigate(
                        event=event_desc,
                        category=category,
                    ),
                    timeout=300.0,  # 5 minutes
                )

                # v3: Output the generated article (AP Style)
                article = result.get("article")
                if article and article.get("full_text"):
                    print("\n" + article["full_text"])
                else:
                    # Fallback: Show raw results
                    print("\n" + "=" * 70)
                    print(f"📰 ARTICLE [{i+1}] - {category.upper()}")
                    print("=" * 70)

                    # Claims extracted
                    claims = result.get("claims", [])
                    print(f"\n📋 CLAIMS EXTRACTED: {len(claims)}")
                    for c in claims[:5]:
                        print(f"  • {c.get('text', '')[:100]}")

                    # Verdicts
                    supported = result.get("supported_claims", [])
                    refuted = result.get("refuted_claims", [])
                    unverified = result.get("unverifiable_claims", [])

                    if supported:
                        print(f"\n✅ SUPPORTED ({len(supported)}):")
                        for v in supported[:3]:
                            print(f"  • {v.get('claim_text', '')[:100]}")
                            print(f"    Confidence: {v.get('confidence', 0)}/5")

                    if refuted:
                        print(f"\n❌ REFUTED ({len(refuted)}):")
                        for v in refuted[:3]:
                            print(f"  • {v.get('claim_text', '')[:100]}")
                            print(f"    Reason: {v.get('reasoning', '')[:100]}")

                    if unverified:
                        print(f"\n❓ UNVERIFIED ({len(unverified)}):")
                        for v in unverified[:3]:
                            print(f"  • {v.get('claim_text', '')[:100]}")

                    reliability = result.get("overall_reliability", 0)
                    print(f"\n📊 RELIABILITY: {reliability:.1%}")

                    sources = result.get("evidence_docs", [])
                    print(f"\n📰 SOURCES ({len(sources)}):")
                    seen = set()
                    for s in sources[:10]:
                        name = s.get("source_name", s.get("source", "unknown"))
                        if name not in seen:
                            seen.add(name)
                            print(f"  • {name}")

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
