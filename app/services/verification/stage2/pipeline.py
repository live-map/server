"""
Stage 2 Pipeline: External API verification.

Combines:
- RAG Pipeline (NEW): SearXNG + NLI-based evidence verification
- ClaimBuster: Check-worthiness scoring (fallback)
- Google Fact Check: Search existing fact-checks

Decision logic:
- If RAG finds strong evidence (SUPPORTED/REFUTED with high confidence) → Skip Stage 3
- If existing fact-check found with high confidence → Skip Stage 3 (save $)
- Otherwise → Continue to Stage 3 for LLM analysis
"""

from dataclasses import dataclass, field

from app.config import settings
from app.services.verification.stage2 import claimbuster, google_fc


@dataclass
class RAGResult:
    """RAG verification results."""

    verdict: str = "UNCERTAIN"  # SUPPORTED, REFUTED, UNCERTAIN, NO_EVIDENCE
    confidence: float = 0.0
    evidence_summary: str = ""
    sources: list[dict] = field(default_factory=list)
    claim_supported_by: int = 0
    claim_refuted_by: int = 0
    total_evidence_found: int = 0
    processing_time_ms: int = 0


@dataclass
class Stage2Result:
    """Complete Stage 2 verification result."""

    # RAG (NEW)
    rag_verdict: str = "UNCERTAIN"
    rag_confidence: float = 0.0
    rag_evidence_summary: str = ""
    rag_sources: list[dict] = field(default_factory=list)
    rag_supported_by: int = 0
    rag_refuted_by: int = 0
    rag_enabled: bool = False

    # ClaimBuster
    check_worthy_score: float = 0.5
    is_check_worthy: bool = True
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
    confidence_threshold: float = 0.75,
    use_rag: bool | None = None,
) -> Stage2Result:
    """
    Run Stage 2 verification pipeline.

    Args:
        text: Text content to verify
        claimbuster_api_key: Optional ClaimBuster API key
        google_api_key: Optional Google API key
        confidence_threshold: Threshold to skip Stage 3
        use_rag: Whether to use RAG pipeline (default from settings)

    Returns:
        Stage2Result with verification details
    """
    # Initialize result
    rag_verdict = "UNCERTAIN"
    rag_confidence = 0.0
    rag_evidence_summary = ""
    rag_sources = []
    rag_supported_by = 0
    rag_refuted_by = 0
    rag_enabled = False

    # Determine if RAG should be used
    if use_rag is None:
        use_rag = settings.ENABLE_RAG_STAGE2

    # Run RAG pipeline if enabled
    if use_rag:
        try:
            from app.services.verification.stage2_rag import RAGVerificationPipeline

            rag_pipeline = RAGVerificationPipeline()
            rag_result = await rag_pipeline.verify(text)

            rag_enabled = True
            rag_verdict = rag_result.verdict.value
            rag_confidence = rag_result.confidence
            rag_evidence_summary = rag_result.evidence_summary
            rag_sources = rag_result.sources
            rag_supported_by = rag_result.claim_supported_by
            rag_refuted_by = rag_result.claim_refuted_by

        except Exception as e:
            # RAG failed, continue with fallback
            rag_evidence_summary = f"RAG error: {str(e)}"

    # Run ClaimBuster check (fallback/additional)
    cb_result = await claimbuster.score_claim(text, api_key=claimbuster_api_key)

    # Run Google Fact Check
    gfc_result = await google_fc.search_fact_checks(text, api_key=google_api_key)

    # Calculate confidence based on RAG and existing fact-checks
    confidence = 0.0
    skip_stage3 = False
    skip_reason = None

    # Priority 1: RAG results (if available and confident)
    if rag_enabled and rag_verdict in ["SUPPORTED", "REFUTED"]:
        confidence = rag_confidence
        if rag_confidence >= confidence_threshold:
            skip_stage3 = True
            skip_reason = f"RAG: {rag_verdict} ({rag_supported_by} 지지, {rag_refuted_by} 반박, confidence={rag_confidence:.2f})"

    # Priority 2: Google Fact Check (existing fact-checks)
    if not skip_stage3 and gfc_result.has_fact_check and gfc_result.ratings:
        rating_scores = [google_fc.interpret_rating(r) for r in gfc_result.ratings]
        gfc_confidence = sum(rating_scores) / len(rating_scores)

        if gfc_confidence >= confidence_threshold or gfc_confidence <= (1 - confidence_threshold):
            confidence = gfc_confidence
            skip_stage3 = True
            if gfc_confidence >= confidence_threshold:
                skip_reason = f"Existing fact-check: verified (confidence={gfc_confidence:.2f})"
            else:
                skip_reason = f"Existing fact-check: false (confidence={gfc_confidence:.2f})"

    # Use RAG confidence if higher
    if rag_enabled and rag_confidence > confidence:
        confidence = rag_confidence

    return Stage2Result(
        # RAG
        rag_verdict=rag_verdict,
        rag_confidence=rag_confidence,
        rag_evidence_summary=rag_evidence_summary,
        rag_sources=rag_sources,
        rag_supported_by=rag_supported_by,
        rag_refuted_by=rag_refuted_by,
        rag_enabled=rag_enabled,
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
