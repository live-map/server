"""
Full verification pipeline (3단계/4단계 필수 통과).

V1 Flow (News articles):
1. Stage 1 (Local NLP) - Filter ~70% of content
   - No location → skip (기사화 불가)
   - Duplicate → skip
   - Score < 0.3 → skip
2. Stage 2 (CRAG + NLI) - Evidence-based verification
3. Stage 3 (LLM) - Final verdict + Articleization

V2 Flow (Social media):
0. Stage 0 (Preprocessing) - Text normalization, coordinate extraction
1. Stage 1 (Source Credibility) - Channel-based scoring, location OPTIONAL
   - Duplicate → skip
   - Blocked channel → skip
   - Score < 0.3 → skip
2. Stage 2 (Multi-source CRAG) - Telegram + OSINT + News
3. Stage 3 (LLM) - Final verdict + Articleization
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from app.config import settings
from app.services.verification.stage0_preprocessing import Stage0Result, run_stage0
from app.services.verification.stage1 import (
    Stage1Result,
    Stage1ResultV2,
    run_stage1_async,
    run_stage1_v2_async,
)
from app.services.verification.stage2 import Stage2Result, run_stage2
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
    """Complete verification pipeline result."""

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
    stage2_completed: bool = False
    stage3_completed: bool = False

    # Stage results (for debugging/logging)
    stage1_result: Stage1Result | None = None
    stage2_result: Stage2Result | None = None
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
    Run the full 3-stage verification pipeline.

    Args:
        text: Text content to verify
        existing_embeddings: List of (feed_id, embedding) for duplicate check
        skip_stage3: Skip LLM stage (for testing/cost saving)

    Returns:
        PipelineResult with verification status and credibility score
    """
    start_time = datetime.now(timezone.utc)
    existing_embeddings = existing_embeddings or []

    # === Stage 1: Local NLP (parallel execution) ===
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

    # === Stage 2: CRAG + NLI (필수 실행) ===
    stage2 = await run_stage2(text)

    # === Stage 3: LLM Analysis (필수 실행) ===
    # skip_stage3는 테스트 용도로만 사용 (프로덕션에서는 항상 False)
    if skip_stage3:
        # 테스트 모드: Stage 1 + 2 결과만으로 임시 점수 산출
        base_score = int(stage1.stage1_score * 50)  # 0-50 from Stage 1
        base_score += int(stage2.confidence * 30)  # 0-30 from RAG

        return PipelineResult(
            status=VerificationStatus.UNVERIFIED,
            credibility_score=base_score,
            locations=[{"text": loc.text, "label": loc.label} for loc in stage1.locations],
            has_location=stage1.has_location,
            embedding=stage1.embedding,
            stage1_completed=True,
            stage2_completed=True,
            stage1_result=stage1,
            stage2_result=stage2,
            skipped_at_stage=3,
            skip_reason="Stage 3 skipped (test mode only)",
            processing_time_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
        )

    # Build context for LLM (Stage 1 + Stage 2 결과 종합)
    context_parts = []

    # Stage 1 정보
    if stage1.locations:
        context_parts.append(f"Locations: {', '.join(loc.text for loc in stage1.locations)}")
    context_parts.append(f"Stage 1 Score: {stage1.stage1_score:.2f}")

    # Stage 2 RAG 검증 정보
    context_parts.append(f"Evidence Verdict: {stage2.verdict} (confidence: {stage2.confidence:.2f})")
    context_parts.append(f"Cross-source: {stage2.supported_by} support, {stage2.refuted_by} refute")
    if stage2.evidence_summary:
        context_parts.append(f"Summary: {stage2.evidence_summary}")

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
        stage2_completed=True,
        stage3_completed=True,
        stage1_result=stage1,
        stage2_result=stage2,
        stage3_result=stage3,
        processing_time_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
        tokens_used=stage3.tokens_used,
    )


# =============================================================================
# V2: Social Media Optimized Pipeline (4-stage)
# =============================================================================


@dataclass
class PipelineResultV2:
    """Complete verification pipeline result (v2 - social media)."""

    # Status
    status: VerificationStatus
    credibility_score: int  # 0-100

    # Location
    locations: list[dict] = field(default_factory=list)
    has_location: bool = False

    # Coordinates from Stage 0
    has_coordinates: bool = False
    coordinates: list[dict] = field(default_factory=list)

    # Channel info
    channel_tier: int = 5
    channel_credibility: float = 0.0

    # Embedding for DB storage
    embedding: list[float] = field(default_factory=list)

    # Stages completed
    stage0_completed: bool = False
    stage1_completed: bool = False
    stage2_completed: bool = False
    stage3_completed: bool = False

    # Stage results
    stage0_result: Stage0Result | None = None
    stage1_result: Stage1ResultV2 | None = None
    stage2_result: Stage2Result | None = None
    stage3_result: Stage3Result | None = None

    # Skip info
    skipped_at_stage: int | None = None
    skip_reason: str | None = None

    # Metadata
    processing_time_ms: int = 0
    tokens_used: int = 0
    is_repost: bool = False
    platform: str | None = None


async def run_pipeline_v2(
    text: str,
    existing_embeddings: list[tuple[int, list[float]]] | None = None,
    channel_info: dict | None = None,
    platform: str | None = None,
    skip_stage3: bool = False,
) -> PipelineResultV2:
    """
    Run the full 4-stage verification pipeline (v2 - social media).

    Changes from v1:
    - Stage 0 preprocessing (normalization, coordinate extraction)
    - Channel credibility is primary factor (not location)
    - Location is OPTIONAL
    - Dynamic duplicate threshold based on text length

    Args:
        text: Text content to verify
        existing_embeddings: List of (feed_id, embedding) for duplicate check
        channel_info: Channel metadata dict with keys:
            - subscriber_count, channel_age_days, is_verified,
            - historical_accuracy, is_trusted, is_blocked
        platform: Source platform (TELEGRAM, X)
        skip_stage3: Skip LLM stage (for testing/cost saving)

    Returns:
        PipelineResultV2 with verification status and credibility score
    """
    start_time = datetime.now(timezone.utc)
    existing_embeddings = existing_embeddings or []
    channel_info = channel_info or {}

    # === Stage 0: Preprocessing ===
    stage0 = run_stage0(text, platform=platform)

    # Check if text is too short after normalization
    if stage0.is_too_short:
        return PipelineResultV2(
            status=VerificationStatus.SKIPPED,
            credibility_score=0,
            stage0_completed=True,
            stage0_result=stage0,
            skipped_at_stage=0,
            skip_reason=f"Text too short after normalization ({stage0.text_length} chars)",
            processing_time_ms=stage0.processing_time_ms,
            is_repost=stage0.is_repost,
            platform=platform,
        )

    # Use normalized text for subsequent stages
    processed_text = stage0.normalized_text

    # === Stage 1: Source Credibility (v2) ===
    stage1 = await run_stage1_v2_async(
        processed_text,
        existing_embeddings=existing_embeddings,
        channel_info=channel_info,
        stage0_result=stage0,
    )

    if not stage1.should_continue:
        return PipelineResultV2(
            status=VerificationStatus.SKIPPED,
            credibility_score=0,
            locations=[{"text": loc.text, "label": loc.label} for loc in stage1.locations],
            has_location=stage1.has_location,
            has_coordinates=stage0.has_coordinates,
            coordinates=[{"lat": c["lat"], "lng": c["lng"]} for c in (
                [] if not stage0.coordinates_json else __import__("json").loads(stage0.coordinates_json)
            )],
            channel_tier=stage1.channel_tier,
            channel_credibility=stage1.channel_credibility.score,
            embedding=stage1.embedding,
            stage0_completed=True,
            stage1_completed=True,
            stage0_result=stage0,
            stage1_result=stage1,
            skipped_at_stage=1,
            skip_reason=stage1.skip_reason,
            processing_time_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
            is_repost=stage0.is_repost,
            platform=platform,
        )

    # === Stage 2: CRAG + NLI (multi-source in future) ===
    stage2 = await run_stage2(processed_text)

    # === Stage 3: LLM Analysis ===
    if skip_stage3:
        # Test mode: Stage 0 + 1 + 2 results for temporary score
        base_score = int(stage1.stage1_score * 40)  # 0-40 from Stage 1
        base_score += int(stage2.confidence * 40)   # 0-40 from RAG
        base_score += 10 if stage0.has_coordinates else 0  # Bonus for coords
        base_score += 10 if stage1.has_location else 0     # Bonus for location

        return PipelineResultV2(
            status=VerificationStatus.UNVERIFIED,
            credibility_score=min(base_score, 100),
            locations=[{"text": loc.text, "label": loc.label} for loc in stage1.locations],
            has_location=stage1.has_location,
            has_coordinates=stage0.has_coordinates,
            channel_tier=stage1.channel_tier,
            channel_credibility=stage1.channel_credibility.score,
            embedding=stage1.embedding,
            stage0_completed=True,
            stage1_completed=True,
            stage2_completed=True,
            stage0_result=stage0,
            stage1_result=stage1,
            stage2_result=stage2,
            skipped_at_stage=3,
            skip_reason="Stage 3 skipped (test mode only)",
            processing_time_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
            is_repost=stage0.is_repost,
            platform=platform,
        )

    # Build context for LLM (Stage 0 + 1 + 2 results)
    context_parts = []

    # Stage 0 info
    if stage0.has_military_content:
        context_parts.append("Contains military terminology")
    if stage0.is_repost:
        context_parts.append(f"Repost/forward from: {stage0.original_source or 'unknown'}")
    if stage0.has_coordinates:
        context_parts.append(f"Coordinates extracted: lat={stage0.primary_latitude}, lng={stage0.primary_longitude}")

    # Stage 1 info
    if stage1.locations:
        context_parts.append(f"Locations: {', '.join(loc.text for loc in stage1.locations)}")
    context_parts.append(f"Channel tier: {stage1.channel_tier} (credibility: {stage1.channel_credibility.score:.2f})")
    context_parts.append(f"Stage 1 Score: {stage1.stage1_score:.2f}")

    # Stage 2 RAG info
    context_parts.append(f"Evidence Verdict: {stage2.verdict} (confidence: {stage2.confidence:.2f})")
    context_parts.append(f"Cross-source: {stage2.supported_by} support, {stage2.refuted_by} refute")
    if stage2.evidence_summary:
        context_parts.append(f"Summary: {stage2.evidence_summary}")

    context = "\n".join(context_parts) if context_parts else None

    stage3 = await run_stage3(processed_text, context=context)

    # Final status
    status = verdict_to_status(stage3.verdict, stage3.confidence)

    return PipelineResultV2(
        status=status,
        credibility_score=stage3.credibility_score,
        locations=[{"text": loc.text, "label": loc.label} for loc in stage1.locations],
        has_location=stage1.has_location,
        has_coordinates=stage0.has_coordinates,
        channel_tier=stage1.channel_tier,
        channel_credibility=stage1.channel_credibility.score,
        embedding=stage1.embedding,
        stage0_completed=True,
        stage1_completed=True,
        stage2_completed=True,
        stage3_completed=True,
        stage0_result=stage0,
        stage1_result=stage1,
        stage2_result=stage2,
        stage3_result=stage3,
        processing_time_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
        tokens_used=stage3.tokens_used,
        is_repost=stage0.is_repost,
        platform=platform,
    )


async def run_pipeline_auto(
    text: str,
    existing_embeddings: list[tuple[int, list[float]]] | None = None,
    channel_info: dict | None = None,
    platform: str | None = None,
    skip_stage3: bool = False,
    use_v2: bool | None = None,
) -> PipelineResult | PipelineResultV2:
    """
    Auto-select pipeline version based on settings or parameter.

    Args:
        text: Text content to verify
        existing_embeddings: List of (feed_id, embedding) for duplicate check
        channel_info: Channel metadata (v2 only)
        platform: Source platform (v2 only)
        skip_stage3: Skip LLM stage
        use_v2: Override settings.USE_PIPELINE_V2

    Returns:
        PipelineResult (v1) or PipelineResultV2 (v2)
    """
    should_use_v2 = use_v2 if use_v2 is not None else settings.USE_PIPELINE_V2

    if should_use_v2:
        return await run_pipeline_v2(
            text=text,
            existing_embeddings=existing_embeddings,
            channel_info=channel_info,
            platform=platform,
            skip_stage3=skip_stage3,
        )
    else:
        return await run_pipeline(
            text=text,
            existing_embeddings=existing_embeddings,
            skip_stage3=skip_stage3,
        )
