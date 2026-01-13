"""
Collector management endpoints.

POST /api/v1/collector/run - Manually trigger collection
GET /api/v1/collector/status - Get scheduler status
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.core.config import settings
from app.services.collector.telegram import TelegramCollector
from app.services.scheduler import get_scheduler, run_once

router = APIRouter()


@router.get("/status")
async def get_collector_status():
    """Get collector and scheduler status."""
    collector = TelegramCollector()
    scheduler = get_scheduler()

    return {
        "telegram_configured": collector.is_configured,
        "scheduler_enabled": settings.ENABLE_SCHEDULER,
        "scheduler_running": scheduler.running if scheduler else False,
        "configured_channels": settings.TELEGRAM_CHANNELS.split(",") if settings.TELEGRAM_CHANNELS else [],
    }


@router.post("/run")
async def run_collection(background_tasks: BackgroundTasks, channels: list[str] | None = None):
    """
    Manually trigger a collection run.

    This runs in the background and returns immediately.
    """
    collector = TelegramCollector()

    if not collector.is_configured:
        raise HTTPException(
            status_code=400,
            detail="Telegram not configured. Set TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE in .env",
        )

    # Run in background
    background_tasks.add_task(run_once, channels)

    return {
        "status": "started",
        "message": "Collection job started in background",
        "channels": channels or "default channels",
    }


@router.get("/channels")
async def list_telegram_channels():
    """List available Telegram channels (requires Telegram to be configured)."""
    collector = TelegramCollector()

    if not collector.is_configured:
        raise HTTPException(
            status_code=400,
            detail="Telegram not configured",
        )

    try:
        channels = await collector.list_channels()
        return {"channels": channels, "count": len(channels)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list channels: {str(e)}")
    finally:
        await collector.disconnect()
