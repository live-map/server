"""
Simplified verification pipeline.

Stage 1 (Local NLP) → Stage 3 (LLM)

Note: Stage 2 (SearXNG RAG) has been removed.
For comprehensive verification, use the autonomous agent system instead.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from app.services.verification.stage1 import Stage1Result, run_stage1_async
from app.services.verification.stage3 import Stage3Result, run_stage3
from app.services.verification.stage3.mistral import Verdict


class VerificationStatus(str, Enum):
    """Final verification status."""
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    UNVERIFIED = "unverified"
    FALSE = "false"
    SKIPPED = "skipped"


@dataclass
class PipelineResult:
    """Verification pipeline result."""

    # Status
    status: VerificationStatus
    credibility_score: int  # 0-100

    # Location
    locations: list[dict] = field(default_factory=list)
    has_location: bool = False

    # Embedding for DB storage
    embedding: list[float] = field(default_factory=list)

    # Stages completed
    stage1_completed: bool = False
    stage3_completed: bool = False

    # Stage results
    stage1_result: Stage1Result | None = None
    stage3_result: Stage3Result | None = None

    # Skip info
    skipped_at_stage: int | None = None
    skip_reason: str | None = None

    # Metadata
    processing_time_ms: int = 0
    tokens_used: int = 0


def verdict_to_status(verdict: Verdict, confidence: float) -> VerificationStatus:
    """Convert LLM verdict to verification status."""
    if verdict == Verdict.TRUE and confidence >= 0.7:
        return VerificationStatus.VERIFIED
    elif verdict == Verdict.TRUE or verdict == Verdict.PARTIALLY_TRUE:
        return VerificationStatus.PARTIALLY_VERIFIED
    elif verdict == Verdict.FALSE and confidence >= 0.7:
        return VerificationStatus.FALSE
    else:
        return VerificationStatus.UNVERIFIED


async def run_pipeline(
    text: str,
    existing_embeddings: list[tuple[int, list[float]]] | None = None,
    skip_stage3: bool = False,
) -> PipelineResult:
    """
    Run the simplified verification pipeline.

    Stage 1: Local NLP (location extraction, duplicate detection)
    Stage 3: LLM Analysis (final verdict)

    Note: For comprehensive evidence-based verification,
    use the autonomous agent system instead.

    Args:
        text: Text content to verify
        existing_embeddings: List of (feed_id, embedding) for duplicate check
        skip_stage3: Skip LLM stage (for testing/cost saving)

    Returns:
        PipelineResult with verification status and credibility score
    """
    start_time = datetime.now(timezone.utc)
    existing_embeddings = existing_embeddings or []

    # === Stage 1: Local NLP ===
    stage1 = await run_stage1_async(text, existing_embeddings)

    if not stage1.should_continue:
        return PipelineResult(
            status=VerificationStatus.SKIPPED,
            credibility_score=0,
            locations=[{"text": loc.text, "label": loc.label} for loc in stage1.locations],
            has_location=stage1.has_location,
            embedding=stage1.embedding,
            stage1_completed=True,
            stage1_result=stage1,
            skipped_at_stage=1,
            skip_reason=stage1.skip_reason,
            processing_time_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
        )

    # === Stage 3: LLM Analysis ===
    if skip_stage3:
        # Test mode: use Stage 1 score only
        base_score = int(stage1.stage1_score * 70)

        return PipelineResult(
            status=VerificationStatus.UNVERIFIED,
            credibility_score=base_score,
            locations=[{"text": loc.text, "label": loc.label} for loc in stage1.locations],
            has_location=stage1.has_location,
            embedding=stage1.embedding,
            stage1_completed=True,
            stage1_result=stage1,
            skipped_at_stage=3,
            skip_reason="Stage 3 skipped (test mode)",
            processing_time_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
        )

    # Build context for LLM
    context_parts = []
    if stage1.locations:
        context_parts.append(f"Locations: {', '.join(loc.text for loc in stage1.locations)}")
    context_parts.append(f"Stage 1 Score: {stage1.stage1_score:.2f}")
    context = "\n".join(context_parts) if context_parts else None

    stage3 = await run_stage3(text, context=context)

    # Final status
    status = verdict_to_status(stage3.verdict, stage3.confidence)

    return PipelineResult(
        status=status,
        credibility_score=stage3.credibility_score,
        locations=[{"text": loc.text, "label": loc.label} for loc in stage1.locations],
        has_location=stage1.has_location,
        embedding=stage1.embedding,
        stage1_completed=True,
        stage3_completed=True,
        stage1_result=stage1,
        stage3_result=stage3,
        processing_time_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
        tokens_used=stage3.tokens_used,
    )
