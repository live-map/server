"""
Verification endpoint.

POST /api/v1/verify - Verify news content through 3-stage pipeline
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.feed import Feed
from app.schemas.verify import (
    LocationInfo,
    VerifyDetailedResponse,
    VerifyRequest,
    VerifyResponse,
)
from app.services.verification.pipeline import run_pipeline

router = APIRouter()


async def _save_to_db(
    db: AsyncSession,
    request: VerifyRequest,
    result,
    verification_error: bool = False,
    error_message: str | None = None,
) -> int:
    """Save verification result to database."""
    # Create title from text if not provided
    title = request.title or request.text[:100] + ("..." if len(request.text) > 100 else "")

    # Get first location name if available
    location_name = None
    location_lat = None
    location_lng = None
    if result and result.locations:
        location_name = ", ".join([loc["text"] for loc in result.locations])

    feed = Feed(
        title=title,
        content=request.text,
        source_name=request.source_name or "Unknown",
        source_type=request.source_type or "API",
        category=request.category or "WAR",
        sub_category=request.sub_category or "unknown",
        location_name=location_name,
        location_lat=location_lat,
        location_lng=location_lng,
        published_at=datetime.now(timezone.utc),
        # Overall status
        credibility_score=result.credibility_score if result else 0,
        verification_status="failed" if verification_error else (result.status.value if result else "failed"),
        verification_error=verification_error,
        error_message=error_message,
        stages_completed=sum([
            result.stage1_completed if result else False,
            result.stage2_completed if result else False,
            result.stage3_completed if result else False,
        ]),
        skipped_at_stage=result.skipped_at_stage if result else None,
        skip_reason=result.skip_reason if result else None,
        processing_time_ms=result.processing_time_ms if result else 0,
        tokens_used=result.tokens_used if result else 0,
        # Stage 1
        stage1_completed=result.stage1_completed if result else False,
        stage1_score=result.stage1_result.stage1_score if result and result.stage1_result else None,
        stage1_has_location=result.has_location if result else False,
        stage1_is_duplicate=result.stage1_result.is_duplicate if result and result.stage1_result else False,
        stage1_subjectivity=result.stage1_result.subjectivity_score if result and result.stage1_result else None,
        stage1_fake_prob=result.stage1_result.fake_probability if result and result.stage1_result else None,
        # Stage 2
        stage2_completed=result.stage2_completed if result else False,
        stage2_check_worthy=result.stage2_result.check_worthy_score if result and result.stage2_result else None,
        stage2_has_fact_check=result.stage2_result.has_existing_fact_check if result and result.stage2_result else False,
        stage2_fact_check_ratings=json.dumps(result.stage2_result.fact_check_ratings) if result and result.stage2_result else None,
        # Stage 3
        stage3_completed=result.stage3_completed if result else False,
        stage3_verdict=result.stage3_result.verdict.value if result and result.stage3_result else None,
        stage3_confidence=result.stage3_result.confidence if result and result.stage3_result else None,
        stage3_reasoning=result.stage3_result.reasoning if result and result.stage3_result else None,
        # Embedding
        embedding=result.embedding if result else None,
    )

    db.add(feed)
    await db.commit()
    await db.refresh(feed)
    return feed.id


@router.post("", response_model=VerifyResponse)
async def verify_content(
    request: VerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify news content through the 3-stage verification pipeline.

    **Stages:**
    1. **Stage 1 (Local NLP)**: Location extraction, duplicate detection,
       subjectivity analysis, fake news detection
    2. **Stage 2 (API)**: ClaimBuster check-worthiness, Google Fact Check lookup
    3. **Stage 3 (LLM)**: Mistral Small deep analysis

    **Parameters:**
    - **text** (required): Content to verify (10-5000 chars)
    - **title**: Optional title
    - **source_name**: Source name (default: "Unknown")
    - **source_type**: RSS, TELEGRAM, API (default: "API")
    - **category**: WAR or SECURITY (default: "WAR")
    - **sub_category**: ru-uk, is-ir, etc. (default: "unknown")
    - **skip_stage3**: Skip LLM stage (default: false)
    - **save_to_db**: Save result to DB (default: true)
    """
    result = None
    verification_error = False
    error_message = None
    saved_id = None

    try:
        result = await run_pipeline(
            text=request.text,
            skip_stage3=request.skip_stage3,
        )
    except Exception as e:
        verification_error = True
        error_message = str(e)

    # Save to DB if requested
    if request.save_to_db:
        try:
            saved_id = await _save_to_db(db, request, result, verification_error, error_message)
        except Exception as e:
            # Don't fail the request if DB save fails
            error_message = f"Verification succeeded but DB save failed: {str(e)}"

    if verification_error and not result:
        return VerifyResponse(
            status="failed",
            credibility_score=0,
            locations=[],
            has_location=False,
            stages_completed=0,
            verification_error=True,
            error_message=error_message,
            saved_id=saved_id,
        )

    return VerifyResponse(
        status=result.status.value,
        credibility_score=result.credibility_score,
        locations=[LocationInfo(text=loc["text"], label=loc["label"]) for loc in result.locations],
        has_location=result.has_location,
        stages_completed=sum([result.stage1_completed, result.stage2_completed, result.stage3_completed]),
        skipped_at_stage=result.skipped_at_stage,
        skip_reason=result.skip_reason,
        verification_error=verification_error,
        error_message=error_message,
        processing_time_ms=result.processing_time_ms,
        tokens_used=result.tokens_used,
        saved_id=saved_id,
    )


@router.post("/detailed", response_model=VerifyDetailedResponse)
async def verify_content_detailed(
    request: VerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify content with detailed stage results (for debugging/analysis).

    Returns all intermediate results from each stage.
    """
    result = None
    verification_error = False
    error_message = None
    saved_id = None

    try:
        result = await run_pipeline(
            text=request.text,
            skip_stage3=request.skip_stage3,
        )
    except Exception as e:
        verification_error = True
        error_message = str(e)

    # Save to DB if requested
    if request.save_to_db:
        try:
            saved_id = await _save_to_db(db, request, result, verification_error, error_message)
        except Exception as e:
            error_message = f"Verification succeeded but DB save failed: {str(e)}"

    if verification_error and not result:
        return VerifyDetailedResponse(
            status="failed",
            credibility_score=0,
            locations=[],
            has_location=False,
            stages_completed=0,
            verification_error=True,
            error_message=error_message,
            saved_id=saved_id,
        )

    response = VerifyDetailedResponse(
        status=result.status.value,
        credibility_score=result.credibility_score,
        locations=[LocationInfo(text=loc["text"], label=loc["label"]) for loc in result.locations],
        has_location=result.has_location,
        stages_completed=sum([result.stage1_completed, result.stage2_completed, result.stage3_completed]),
        skipped_at_stage=result.skipped_at_stage,
        skip_reason=result.skip_reason,
        verification_error=verification_error,
        error_message=error_message,
        processing_time_ms=result.processing_time_ms,
        tokens_used=result.tokens_used,
        saved_id=saved_id,
    )

    # Add Stage 1 details
    if result.stage1_result:
        response.stage1_score = result.stage1_result.stage1_score
        response.is_duplicate = result.stage1_result.is_duplicate
        response.subjectivity_score = result.stage1_result.subjectivity_score
        response.fake_probability = result.stage1_result.fake_probability

    # Add Stage 2 details
    if result.stage2_result:
        response.check_worthy_score = result.stage2_result.check_worthy_score
        response.has_existing_fact_check = result.stage2_result.has_existing_fact_check
        response.fact_check_ratings = result.stage2_result.fact_check_ratings

    # Add Stage 3 details
    if result.stage3_result:
        response.verdict = result.stage3_result.verdict.value
        response.confidence = result.stage3_result.confidence
        response.reasoning = result.stage3_result.reasoning

    return response
