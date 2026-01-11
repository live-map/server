"""
RAG-based verification pipeline.

Retrieves evidence from SearXNG and verifies claims using NLI.
"""

import logging
import time

from app.services.verification.stage2_rag.evidence_checker import EvidenceChecker
from app.services.verification.stage2_rag.evidence_retriever import EvidenceRetriever
from app.services.verification.stage2_rag.models import (
    RAGVerdict,
    RAGVerificationResult,
)

logger = logging.getLogger(__name__)


class RAGVerificationPipeline:
    """
    RAG-based claim verification pipeline.

    Pipeline:
    1. Search for evidence using SearXNG
    2. Check each evidence against the claim using NLI
    3. Aggregate results to determine final verdict
    """

    def __init__(
        self,
        searxng_url: str | None = None,
        nli_model: str | None = None,
    ):
        self.retriever = EvidenceRetriever(searxng_url)
        self.checker = EvidenceChecker(nli_model)

    def _generate_search_queries(self, claim: str) -> list[str]:
        """
        Generate search queries from claim.

        Creates variations to find more diverse evidence.
        """
        queries = [claim]

        # Add fact-check specific query
        queries.append(f"fact check {claim}")

        return queries

    def _summarize_evidence(
        self, supporting: list, refuting: list, neutral: list
    ) -> str:
        """Generate a summary of the evidence found."""
        parts = []

        if supporting:
            sources = list(set(e.evidence.source for e in supporting[:3]))
            parts.append(f"{len(supporting)}개 소스가 지지 ({', '.join(sources)})")

        if refuting:
            sources = list(set(e.evidence.source for e in refuting[:3]))
            parts.append(f"{len(refuting)}개 소스가 반박 ({', '.join(sources)})")

        if not parts:
            return "관련 증거를 찾지 못함"

        return "; ".join(parts)

    async def verify(
        self,
        claim: str,
        num_results: int = 10,
        min_evidence_for_verdict: int = 2,
    ) -> RAGVerificationResult:
        """
        Verify a claim using RAG pipeline.

        Args:
            claim: The claim to verify
            num_results: Number of search results to retrieve
            min_evidence_for_verdict: Minimum supporting/refuting evidence
                                      needed for a definitive verdict

        Returns:
            RAGVerificationResult with verdict, confidence, and sources
        """
        start_time = time.time()

        # Step 1: Generate search queries
        queries = self._generate_search_queries(claim)

        # Step 2: Retrieve evidence
        evidences = await self.retriever.search_multiple_queries(
            queries, num_results_per_query=num_results // len(queries)
        )

        if not evidences:
            return RAGVerificationResult(
                verdict=RAGVerdict.NO_EVIDENCE,
                confidence=0.0,
                evidence_summary="검색 결과 없음",
                sources=[],
                claim_supported_by=0,
                claim_refuted_by=0,
                total_evidence_found=0,
                check_results=[],
                processing_time_ms=int((time.time() - start_time) * 1000),
            )

        # Step 3: Check each evidence against the claim
        check_results = self.checker.check_batch(claim, evidences[:num_results])

        # Step 4: Categorize results
        supporting = [r for r in check_results if r.verdict == "SUPPORTS"]
        refuting = [r for r in check_results if r.verdict == "REFUTES"]
        neutral = [r for r in check_results if r.verdict == "NEUTRAL"]

        # Step 5: Determine final verdict
        num_supporting = len(supporting)
        num_refuting = len(refuting)

        if num_supporting >= min_evidence_for_verdict and num_supporting > num_refuting:
            verdict = RAGVerdict.SUPPORTED
            # Confidence based on ratio and trusted sources
            trusted_supporting = sum(
                1 for r in supporting if r.evidence.is_trusted_source
            )
            confidence = min(
                0.5 + (num_supporting / num_results) * 0.3 + (trusted_supporting * 0.1),
                1.0,
            )
        elif num_refuting >= min_evidence_for_verdict and num_refuting > num_supporting:
            verdict = RAGVerdict.REFUTED
            trusted_refuting = sum(1 for r in refuting if r.evidence.is_trusted_source)
            confidence = min(
                0.5 + (num_refuting / num_results) * 0.3 + (trusted_refuting * 0.1),
                1.0,
            )
        else:
            verdict = RAGVerdict.UNCERTAIN
            confidence = 0.5

        # Step 6: Prepare sources for response
        # Prioritize trusted sources and high-scoring evidence
        top_evidence = sorted(
            check_results,
            key=lambda x: (
                x.evidence.is_trusted_source,
                max(x.entailment_score, x.contradiction_score),
            ),
            reverse=True,
        )[:5]

        sources = [
            {
                "url": r.evidence.url,
                "title": r.evidence.title,
                "snippet": r.evidence.text[:200] + "..."
                if len(r.evidence.text) > 200
                else r.evidence.text,
                "source": r.evidence.source,
                "verdict": r.verdict,
                "is_trusted": r.evidence.is_trusted_source,
            }
            for r in top_evidence
        ]

        processing_time = int((time.time() - start_time) * 1000)

        return RAGVerificationResult(
            verdict=verdict,
            confidence=confidence,
            evidence_summary=self._summarize_evidence(supporting, refuting, neutral),
            sources=sources,
            claim_supported_by=num_supporting,
            claim_refuted_by=num_refuting,
            total_evidence_found=len(evidences),
            check_results=check_results,
            processing_time_ms=processing_time,
        )


# Singleton instance
_pipeline_instance: RAGVerificationPipeline | None = None


def get_rag_pipeline() -> RAGVerificationPipeline:
    """Get or create the RAG verification pipeline instance."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = RAGVerificationPipeline()
    return _pipeline_instance
