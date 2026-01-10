"""
Verification endpoint.

POST /api/v1/verify - Verify news content through 3-stage pipeline
"""

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.schemas.verify import (
    LocationInfo,
    VerifyDetailedResponse,
    VerifyRequest,
    VerifyResponse,
)
from app.services.verification.pipeline import run_pipeline

router = APIRouter()


@router.post("", response_model=VerifyResponse)
async def verify_content(request: VerifyRequest):
    """
    Verify news content through the 3-stage verification pipeline.

    **Stages:**
    1. **Stage 1 (Local NLP)**: Location extraction, duplicate detection,
       subjectivity analysis, fake news detection
    2. **Stage 2 (API)**: ClaimBuster check-worthiness, Google Fact Check lookup
    3. **Stage 3 (LLM)**: Mistral Small deep analysis

    **Filtering:**
    - ~70% filtered at Stage 1 (no location, duplicate, low quality)
    - ~10-15% resolved at Stage 2 (existing fact-check found)
    - ~15-20% require Stage 3 LLM analysis

    **Cost:**
    - Stage 1 & 2: Free
    - Stage 3: ~$0.00014 per request
    """
    try:
        # Run pipeline (Stage 1 is CPU-bound, run in threadpool for first part)
        result = await run_pipeline(
            text=request.text,
            skip_stage3=request.skip_stage3,
        )

        return VerifyResponse(
            status=result.status.value,
            credibility_score=result.credibility_score,
            locations=[LocationInfo(text=loc["text"], label=loc["label"]) for loc in result.locations],
            has_location=result.has_location,
            stages_completed=sum([result.stage1_completed, result.stage2_completed, result.stage3_completed]),
            skipped_at_stage=result.skipped_at_stage,
            skip_reason=result.skip_reason,
            processing_time_ms=result.processing_time_ms,
            tokens_used=result.tokens_used,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@router.post("/detailed", response_model=VerifyDetailedResponse)
async def verify_content_detailed(request: VerifyRequest):
    """
    Verify content with detailed stage results (for debugging/analysis).

    Returns all intermediate results from each stage.
    """
    try:
        result = await run_pipeline(
            text=request.text,
            skip_stage3=request.skip_stage3,
        )

        response = VerifyDetailedResponse(
            status=result.status.value,
            credibility_score=result.credibility_score,
            locations=[LocationInfo(text=loc["text"], label=loc["label"]) for loc in result.locations],
            has_location=result.has_location,
            stages_completed=sum([result.stage1_completed, result.stage2_completed, result.stage3_completed]),
            skipped_at_stage=result.skipped_at_stage,
            skip_reason=result.skip_reason,
            processing_time_ms=result.processing_time_ms,
            tokens_used=result.tokens_used,
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

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")
