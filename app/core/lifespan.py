"""
Application lifespan events.

Handles startup and shutdown operations.
- Configures logging
- Cleans up old logs
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI

logger = logging.getLogger(__name__)

# Store current log file path for reference
_current_log_file: str | None = None


def setup_logging():
    """Configure logging with per-session file output.

    Each server start creates a new timestamped log file:
    - Console: All activity with timestamp (HH:MM:SS format)
    - File: logs/grapoll_YYYY-MM-DD_HH-MM-SS.log
    """
    global _current_log_file

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # === Console handler ===
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)

    # === File handler (timestamped per session) ===
    log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
    os.makedirs(log_dir, exist_ok=True)

    # Create timestamped log filename for this session
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = f"grapoll_{timestamp}.log"
    log_path = os.path.join(log_dir, log_filename)
    _current_log_file = log_path

    # Also create/update a symlink to the latest log for convenience
    latest_link = os.path.join(log_dir, "grapoll_latest.log")
    try:
        if os.path.islink(latest_link):
            os.unlink(latest_link)
        os.symlink(log_filename, latest_link)
    except OSError:
        pass

    file_handler = logging.FileHandler(
        log_path,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    # Clear existing handlers and add both
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Set specific loggers
    logging.getLogger("app").setLevel(logging.DEBUG)

    # Reduce noise from libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # Log startup
    logger.info(f"Logging initialized - session log: {log_path}")


def cleanup_old_logs(keep_days: int = 7):
    """Remove log files older than keep_days."""
    log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
    if not os.path.exists(log_dir):
        return

    cutoff_time = datetime.now().timestamp() - (keep_days * 24 * 60 * 60)
    removed_count = 0

    for filename in os.listdir(log_dir):
        if not filename.endswith(".log"):
            continue
        if filename in ("grapoll_latest.log", "livemap_latest.log"):
            continue

        filepath = os.path.join(log_dir, filename)
        if os.path.isfile(filepath):
            file_mtime = os.path.getmtime(filepath)
            if file_mtime < cutoff_time:
                try:
                    os.remove(filepath)
                    removed_count += 1
                except OSError:
                    pass

    if removed_count > 0:
        logger.info(f"Cleaned up {removed_count} old log files (older than {keep_days} days)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    # Setup logging first (creates new timestamped log file)
    setup_logging()

    # Clean up old logs (keep last 7 days)
    cleanup_old_logs(keep_days=7)

    # Initialize Research Service (optional - depends on API keys)
    try:
        from app.services.research.config import ai_settings

        if ai_settings.research_enabled:
            from app.services.research.service import ResearchService

            app.state.research_service = ResearchService()
            logger.info("Research Agent initialized (AI research enabled)")
        else:
            app.state.research_service = None
            logger.info("Research Agent disabled (API keys not configured)")
    except Exception as e:
        app.state.research_service = None
        logger.warning(f"Research Agent initialization failed: {e}")

    print("\n" + "=" * 60)
    print("  Grapoll API - 여론조사 플랫폼")
    print("=" * 60 + "\n")

    yield

    # Dispose DB engine with timeout
    import asyncio
    try:
        from app.core.database import engine
        await asyncio.wait_for(engine.dispose(), timeout=10.0)
    except asyncio.TimeoutError:
        logger.warning("Database dispose timed out after 10s")

    print("[SHUTDOWN] Grapoll API stopped.")
