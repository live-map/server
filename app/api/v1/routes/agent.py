"""
Autonomous investigation agent endpoints.

POST /api/v1/agent/investigate - Start investigation on a topic
GET /api/v1/agent/status/{id} - Get investigation status
POST /api/v1/agent/scan - Trigger multi-source scan
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agent import InvestigationAgent, NewsScanner
from app.agent.graph import EventCategory, InvestigationReport

router = APIRouter()
logger = logging.getLogger(__name__)

# Store for investigation results (in production, use Redis or DB)
_investigations: dict[str, dict] = {}


class InvestigateRequest(BaseModel):
    """Request to start an investigation."""

    topic: str = Field(..., min_length=10, max_length=500, description="Topic to investigate")
    category: str = Field("other", description="Event category (war, protest, terrorism, etc.)")


class InvestigateResponse(BaseModel):
    """Response from investigation initiation."""

    investigation_id: str
    status: str
    message: str


class ScanRequest(BaseModel):
    """Request to trigger a scan."""

    sources: list[str] = Field(
        default=["gdelt"],
        description="Sources to scan (gdelt, twitter, telegram)"
    )
    keywords: list[str] = Field(
        default=[],
        description="Keywords to filter events"
    )


class ScanResponse(BaseModel):
    """Response from scan."""

    events_found: int
    events: list[dict]


@router.post("/investigate", response_model=InvestigateResponse)
async def start_investigation(request: InvestigateRequest):
    """
    Start an autonomous investigation on a topic.

    The agent will:
    1. Create an investigation plan
    2. Search multiple sources (GDELT, Tavily, Telegram)
    3. Cross-verify collected information
    4. Generate a comprehensive report
    """
    investigation_id = f"inv_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    # Initialize status
    _investigations[investigation_id] = {
        "id": investigation_id,
        "topic": request.topic,
        "category": request.category,
        "status": "started",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "report": None,
    }

    # Run investigation in background using asyncio.create_task
    async def run_investigation():
        try:
            print(f"[AGENT] Starting investigation: {investigation_id}")
            agent = InvestigationAgent()
            report = await agent.investigate(
                event=request.topic,
                category=request.category,
            )
            _investigations[investigation_id]["status"] = "completed"
            _investigations[investigation_id]["report"] = report.model_dump()
            _investigations[investigation_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
            print(f"[AGENT] Investigation completed: {investigation_id}")
        except Exception as e:
            print(f"[AGENT] Investigation failed: {e}")
            _investigations[investigation_id]["status"] = "failed"
            _investigations[investigation_id]["error"] = str(e)

    # Create async task (runs in background)
    task = asyncio.create_task(run_investigation())
    print(f"[AGENT] Task created: {task}")

    return InvestigateResponse(
        investigation_id=investigation_id,
        status="started",
        message=f"Investigation started for: {request.topic}",
    )


@router.get("/status/{investigation_id}")
async def get_investigation_status(investigation_id: str):
    """
    Get the status and results of an investigation.
    """
    if investigation_id not in _investigations:
        raise HTTPException(status_code=404, detail="Investigation not found")

    return _investigations[investigation_id]


@router.post("/scan", response_model=ScanResponse)
async def trigger_scan(request: ScanRequest):
    """
    Trigger a multi-source scan for events.

    Scans configured sources (GDELT, Twitter, Telegram) for recent events
    matching the specified keywords.
    """
    try:
        scanner = NewsScanner()
        events = await scanner.scan_all_sources(
            sources=request.sources,
            keywords=request.keywords if request.keywords else None,
        )

        return ScanResponse(
            events_found=len(events),
            events=[e.model_dump() if hasattr(e, "model_dump") else e for e in events],
        )

    except Exception as e:
        logger.error(f"Scan failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


@router.get("/investigations")
async def list_investigations(
    status: Optional[str] = None,
    limit: int = 10,
):
    """
    List recent investigations.
    """
    investigations = list(_investigations.values())

    if status:
        investigations = [inv for inv in investigations if inv["status"] == status]

    # Sort by started_at descending
    investigations.sort(key=lambda x: x.get("started_at", ""), reverse=True)

    return {
        "total": len(investigations),
        "investigations": investigations[:limit],
    }
