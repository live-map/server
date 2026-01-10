"""
Stage 2 Pipeline: External API verification.

Combines:
- ClaimBuster: Check-worthiness scoring
- Google Fact Check: Search existing fact-checks

Decision logic:
- If existing fact-check found with high confidence → Skip Stage 3 (save $)
- Otherwise → Continue to Stage 3 for LLM analysis
"""

from dataclasses import dataclass, field

from app.services.verification.stage2 import claimbuster, google_fc


@dataclass
class Stage2Result:
    """Complete Stage 2 verification result."""

    # ClaimBuster
    check_worthy_score: float
    is_check_worthy: bool
    claimbuster_error: str | None = None

    # Google Fact Check
    has_existing_fact_check: bool = False
    matched_claim: str | None = None
    fact_check_ratings: list[str] = field(default_factory=list)
    fact_check_sources: list[google_fc.FactCheckSource] = field(default_factory=list)
    google_fc_error: str | None = None

    # Overall
    confidence: float = 0.0  # 0.0-1.0
    skip_stage3: bool = False
    skip_reason: str | None = None


async def run_stage2(
    text: str,
    claimbuster_api_key: str | None = None,
    google_api_key: str | None = None,
    confidence_threshold: float = 0.85,
) -> Stage2Result:
    """
    Run Stage 2 verification pipeline.

    Args:
        text: Text content to verify
        claimbuster_api_key: Optional ClaimBuster API key
        google_api_key: Optional Google API key
        confidence_threshold: Threshold to skip Stage 3

    Returns:
        Stage2Result with verification details
    """
    # Run ClaimBuster check
    cb_result = await claimbuster.score_claim(text, api_key=claimbuster_api_key)

    # Run Google Fact Check
    gfc_result = await google_fc.search_fact_checks(text, api_key=google_api_key)

    # Calculate confidence based on existing fact-checks
    confidence = 0.0
    skip_stage3 = False
    skip_reason = None

    if gfc_result.has_fact_check and gfc_result.ratings:
        # Average the ratings
        rating_scores = [google_fc.interpret_rating(r) for r in gfc_result.ratings]
        confidence = sum(rating_scores) / len(rating_scores)

        if confidence >= confidence_threshold or confidence <= (1 - confidence_threshold):
            # High confidence in either direction → skip Stage 3
            skip_stage3 = True
            if confidence >= confidence_threshold:
                skip_reason = f"Existing fact-check: verified (confidence={confidence:.2f})"
            else:
                skip_reason = f"Existing fact-check: false (confidence={confidence:.2f})"

    return Stage2Result(
        # ClaimBuster
        check_worthy_score=cb_result.score,
        is_check_worthy=cb_result.is_check_worthy,
        claimbuster_error=cb_result.error,
        # Google Fact Check
        has_existing_fact_check=gfc_result.has_fact_check,
        matched_claim=gfc_result.matched_claim,
        fact_check_ratings=gfc_result.ratings,
        fact_check_sources=gfc_result.sources,
        google_fc_error=gfc_result.error,
        # Overall
        confidence=confidence,
        skip_stage3=skip_stage3,
        skip_reason=skip_reason,
    )
