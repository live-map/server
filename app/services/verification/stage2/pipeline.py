"""
Stage 2 Pipeline: RAG-based Evidence Verification.

신규 뉴스 검증을 위한 증거 기반 검증 파이프라인:
- SearXNG로 다른 뉴스 소스에서 교차 확인
- mDeBERTa NLI로 주장-증거 매칭
- CRAG 패턴으로 저품질 증거 필터링

3-Stage Mandatory Pipeline:
- Stage 2 결과는 Stage 3로 전달 (스킵 없음)
- Stage 3에서 최종 판정 + 기사화
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Stage2Result:
    """Stage 2 RAG verification result."""

    # RAG 결과
    verdict: str = "UNCERTAIN"  # SUPPORTED, REFUTED, UNCERTAIN, NO_EVIDENCE
    confidence: float = 0.0
    evidence_summary: str = ""
    sources: list[dict] = field(default_factory=list)
    supported_by: int = 0
    refuted_by: int = 0
    total_evidence: int = 0

    # 처리 정보
    processing_time_ms: int = 0
    error: str | None = None


async def run_stage2(text: str) -> Stage2Result:
    """
    Run Stage 2 RAG-based verification.

    신규 뉴스에 대해:
    1. SearXNG로 다른 뉴스 소스 검색
    2. mDeBERTa NLI로 주장-증거 매칭
    3. CRAG 패턴으로 품질 평가 및 교정적 검색
    4. 교차 소스 확인으로 최종 판정

    Args:
        text: 검증할 뉴스 텍스트

    Returns:
        Stage2Result with RAG verification results
    """
    try:
        from app.services.verification.stage2_rag import get_rag_pipeline

        rag_pipeline = get_rag_pipeline()
        result = await rag_pipeline.verify(text)

        return Stage2Result(
            verdict=result.verdict.value,
            confidence=result.confidence,
            evidence_summary=result.evidence_summary,
            sources=result.sources,
            supported_by=result.claim_supported_by,
            refuted_by=result.claim_refuted_by,
            total_evidence=result.total_evidence_found,
            processing_time_ms=result.processing_time_ms,
        )

    except Exception as e:
        logger.error(f"Stage 2 RAG verification failed: {e}")
        return Stage2Result(
            verdict="UNCERTAIN",
            confidence=0.0,
            evidence_summary="검증 실패",
            error=str(e),
        )
