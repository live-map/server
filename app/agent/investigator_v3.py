"""
Claim-Level Verification Agent v3.0 (2026 SOTA)

Full pipeline for claim-level fact verification:
1. CLAIM EXTRACTION - VeriScore style atomic claim extraction
1.5. DEDUPLICATION CHECK - Hash + semantic deduplication (NEW)
2. EVIDENCE RETRIEVAL - Document-level search with deduplication
3. QA-BASED VERIFICATION - Per-claim LLM verification
4. VERDICT AGGREGATION - Statistics and reliability scoring
4.5. UPDATE DETECTION - Check for significant new information (NEW)
5. ARTICLE SYNTHESIS - Bilingual AP Style article generation (EN + KO)

Based on:
- AIC CTU (FEVER 8 Winner): Simple RAG, AVeriTeC 0.50
- HerO 2 (AVeriTeC 2025 Runner-up): 4-stage pipeline
- VeriScore: Verifiable claim extraction

References:
- https://arxiv.org/html/2508.04390 (AIC CTU)
- https://arxiv.org/html/2507.11004 (HerO 2)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from tenacity import (
    AsyncRetrying,
    RetryError,
    stop_after_attempt,
    wait_exponential,
)

from .article_generator import ArticleGenerator, GeneratedArticle
from .bilingual_article_generator import BilingualArticleGenerator, BilingualArticle, RelatedSource
from .claim_extraction import ClaimExtractor, ExtractedClaim
from .confidence_scorer import MultiSourceConfidenceScorer, ConfidenceResult
from .config import agent_settings
from .qa_verifier import ClaimVerdict, QAVerifier, VerificationResult
from .tools import ALL_TOOLS
from .tools.search import _is_evidence_recent, _is_excluded_domain


# =============================================================================
# Source Credibility Tiers
# =============================================================================

# Tier-1: Major wire services, government sources
# Using longer, more specific strings to avoid false positives
TIER1_DOMAINS = {
    "reuters.com", "apnews.com", "ap.org", "afp.com",
    ".gov", "state.gov", "whitehouse.gov",
    "un.org", "nato.int", "europa.eu",
}
TIER1_NAMES = {
    "reuters", "associated press", "afp", "agence france-presse",
    "united nations", "nato", "european union",
}

# Tier-2: Major established news organizations
TIER2_DOMAINS = {
    "bbc.com", "bbc.co.uk", "cnn.com", "nytimes.com", "washingtonpost.com",
    "theguardian.com", "economist.com", "wsj.com",
    "npr.org", "pbs.org", "abcnews.go.com", "cbsnews.com", "nbcnews.com",
    "foxnews.com", "aljazeera.com", "kyodonews.net", "en.yna.co.kr",
    "xinhuanet.com", "tass.com",
}
TIER2_NAMES = {
    "bbc", "cnn", "new york times", "washington post",
    "guardian", "economist", "wall street journal",
    "npr", "pbs", "abc news", "cbs news", "nbc news",
    "fox news", "al jazeera", "kyodo", "yonhap", "xinhua", "tass",
}

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class V3Config:
    """Configuration for Claim-Level Verification Agent."""

    # Claim extraction
    MAX_CLAIMS: int = 10

    # Evidence retrieval
    MAX_EVIDENCE_PER_CLAIM: int = 10
    MAX_TOTAL_EVIDENCE: int = 50

    # Rate limiting
    MAX_CONCURRENT_SEARCHES: int = 5
    MAX_CONCURRENT_LLM_CALLS: int = agent_settings.max_concurrent_llm_calls

    # Timeouts (seconds) - from config
    TOOL_TIMEOUT: float = 30.0
    LLM_TIMEOUT: float = agent_settings.llm_timeout_seconds

    # Retry
    MAX_RETRIES: int = 3

    # Input validation
    MIN_INPUT_LENGTH: int = 10
    MAX_INPUT_LENGTH: int = 10000


# =============================================================================
# State Schema
# =============================================================================


class ClaimVerificationState(BaseModel):
    """State for claim-level verification pipeline."""

    # === INPUT ===
    original_text: str = ""
    event_category: str = "general"

    # === STAGE 1: EXTRACTION ===
    claims: list[dict] = Field(default_factory=list)

    # === STAGE 1.5: DEDUPLICATION (NEW) ===
    is_duplicate: bool = False
    matched_event_id: int | None = None
    similarity_score: float | None = None
    skip_reason: str | None = None

    # === STAGE 2: EVIDENCE ===
    evidence_docs: list[dict] = Field(default_factory=list)
    seen_url_hashes: set[str] = Field(default_factory=set)

    # === STAGE 3: VERIFICATION ===
    verdicts: list[dict] = Field(default_factory=list)

    # === STAGE 4: AGGREGATION ===
    supported_claims: list[dict] = Field(default_factory=list)
    refuted_claims: list[dict] = Field(default_factory=list)
    unverifiable_claims: list[dict] = Field(default_factory=list)
    overall_reliability: float = 0.0

    # === STAGE 4.25: MULTI-SOURCE CONFIDENCE (NEW) ===
    confidence_result: dict | None = None
    two_source_satisfied: bool = False

    # === STAGE 4.5: UPDATE DETECTION (NEW) ===
    is_update: bool = False
    update_type: str | None = None
    update_reason: str | None = None

    # === STAGE 5: SYNTHESIS ===
    article: dict | None = None
    article_en: dict | None = None  # English article
    article_ko: dict | None = None  # Korean article

    # === METADATA ===
    current_stage: str = "init"
    errors: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None


# =============================================================================
# Tool Map
# =============================================================================


TOOL_MAP = {tool.name: tool for tool in ALL_TOOLS}


# =============================================================================
# Claim-Level Verification Agent
# =============================================================================


class ClaimVerificationAgent:
    """
    Claim-Level Verification Agent (v3.0)

    5-Stage Pipeline:
    1. EXTRACTOR - Extract atomic verifiable claims
    2. RETRIEVER - Search evidence for each claim
    3. VERIFIER - QA-based verification per claim
    4. AGGREGATOR - Aggregate verdicts and calculate reliability
    5. SYNTHESIZER - Generate AP Style article

    Features:
    - Per-claim verification breakdown
    - Partial truth detection
    - Document-level evidence retrieval
    - Rate limiting and retry
    """

    def __init__(self, config: V3Config | None = None):
        self.config = config or V3Config()

        # Semaphores for rate limiting
        self._search_semaphore = asyncio.Semaphore(
            self.config.MAX_CONCURRENT_SEARCHES
        )

        # Components (LLM rate limiting is handled within each component)
        self.claim_extractor = ClaimExtractor(
            llm_timeout=self.config.LLM_TIMEOUT
        )
        self.qa_verifier = QAVerifier(
            llm_timeout=self.config.LLM_TIMEOUT
        )
        self.article_generator = ArticleGenerator(
            llm_timeout=self.config.LLM_TIMEOUT
        )

        # Bilingual article generator (NEW)
        self.bilingual_generator = BilingualArticleGenerator(
            llm_timeout=self.config.LLM_TIMEOUT + 30.0  # Extra time for bilingual
        )

        # Build graph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the verification pipeline graph."""
        graph = StateGraph(dict)

        # Add nodes
        graph.add_node("extractor", self._extract_claims_node)
        graph.add_node("retriever", self._retrieve_evidence_node)
        graph.add_node("verifier", self._verify_claims_node)
        graph.add_node("aggregator", self._aggregate_verdicts_node)
        graph.add_node("synthesizer", self._synthesize_article_node)

        # Linear flow
        graph.set_entry_point("extractor")
        graph.add_edge("extractor", "retriever")
        graph.add_edge("retriever", "verifier")
        graph.add_edge("verifier", "aggregator")
        graph.add_edge("aggregator", "synthesizer")
        graph.add_edge("synthesizer", END)

        return graph.compile(checkpointer=MemorySaver())

    async def investigate(
        self,
        event: str,
        category: str = "general",
    ) -> dict[str, Any]:
        """
        Run claim-level verification on an event.

        Args:
            event: Event text to verify
            category: Event category

        Returns:
            Investigation result with article and breakdown
        """
        # Input validation
        if not event or not isinstance(event, str):
            logger.warning("Invalid input: event must be a non-empty string")
            return {
                "errors": ["Invalid input: event must be a non-empty string"],
                "completed_at": datetime.utcnow(),
            }

        event = event.strip()

        if len(event) < self.config.MIN_INPUT_LENGTH:
            logger.warning(f"Input too short: {len(event)} chars (min: {self.config.MIN_INPUT_LENGTH})")
            return {
                "errors": [f"Input too short: minimum {self.config.MIN_INPUT_LENGTH} characters required"],
                "completed_at": datetime.utcnow(),
            }

        if len(event) > self.config.MAX_INPUT_LENGTH:
            logger.warning(f"Input too long: {len(event)} chars (max: {self.config.MAX_INPUT_LENGTH})")
            event = event[:self.config.MAX_INPUT_LENGTH]
            logger.info(f"Truncated input to {self.config.MAX_INPUT_LENGTH} characters")

        logger.info(
            "Starting claim-level verification",
            extra={"event": event[:100], "category": category},
        )

        initial_state = {
            "original_text": event,
            "event_category": category,
            "claims": [],
            "evidence_docs": [],
            "seen_url_hashes": set(),
            "verdicts": [],
            "supported_claims": [],
            "refuted_claims": [],
            "unverifiable_claims": [],
            "overall_reliability": 0.0,
            "article": None,
            "current_stage": "extractor",
            "errors": [],
            "started_at": datetime.utcnow(),
            "completed_at": None,
        }

        config = {
            "configurable": {
                "thread_id": f"claim_v3_{datetime.utcnow().isoformat()}"
            },
            "recursion_limit": 20,
        }

        try:
            final_state = await self.graph.ainvoke(initial_state, config)
            final_state["completed_at"] = datetime.utcnow()

            # Calculate duration
            started = final_state.get("started_at", datetime.utcnow())
            duration = (datetime.utcnow() - started).total_seconds()

            logger.info(
                "Investigation complete",
                extra={
                    "duration": f"{duration:.1f}s",
                    "claims": len(final_state.get("claims", [])),
                    "reliability": f"{final_state.get('overall_reliability', 0):.1%}",
                },
            )

            return final_state

        except Exception as e:
            logger.error(f"Investigation failed: {e}")
            return {
                **initial_state,
                "errors": [str(e)],
                "completed_at": datetime.utcnow(),
            }

    # =========================================================================
    # Stage 1: Claim Extraction
    # =========================================================================

    async def _extract_claims_node(self, state: dict) -> dict:
        """Extract verifiable claims from input text."""
        logger.info("Stage 1: Extracting claims")

        text = state.get("original_text", "")

        try:
            result = await self.claim_extractor.extract(text)
            claims = [c.model_dump() for c in result.claims[:self.config.MAX_CLAIMS]]

            logger.info(
                "Claims extracted",
                extra={
                    "total": result.total_extracted,
                    "verifiable": len(claims),
                },
            )

            return {
                **state,
                "claims": claims,
                "current_stage": "retriever",
            }

        except Exception as e:
            logger.error(f"Claim extraction failed: {e}")
            return {
                **state,
                "claims": [],
                "errors": state.get("errors", []) + [f"Extraction: {e}"],
                "current_stage": "retriever",
            }

    # =========================================================================
    # Stage 2: Evidence Retrieval
    # =========================================================================

    async def _retrieve_evidence_node(self, state: dict) -> dict:
        """Retrieve evidence for all claims."""
        logger.info("Stage 2: Retrieving evidence")

        claims = state.get("claims", [])
        if not claims:
            return {**state, "current_stage": "verifier"}

        all_evidence: list[dict] = []
        seen_hashes: set[str] = set()

        # Search for evidence for each claim
        for claim in claims:
            claim_text = claim.get("text", "")
            if not claim_text:
                continue

            try:
                evidence = await self._search_for_claim(claim_text)

                # Deduplicate
                for doc in evidence:
                    url_hash = self._hash_url(doc.get("url", ""))
                    if url_hash not in seen_hashes:
                        seen_hashes.add(url_hash)
                        all_evidence.append(doc)

                        if len(all_evidence) >= self.config.MAX_TOTAL_EVIDENCE:
                            break

            except Exception as e:
                logger.warning(f"Evidence search failed for claim: {e}")

            if len(all_evidence) >= self.config.MAX_TOTAL_EVIDENCE:
                break

        logger.info(
            "Evidence retrieved",
            extra={
                "total_docs": len(all_evidence),
                "unique_sources": len(seen_hashes),
            },
        )

        return {
            **state,
            "evidence_docs": all_evidence,
            "seen_url_hashes": seen_hashes,
            "current_stage": "verifier",
        }

    async def _search_for_claim(self, claim: str) -> list[dict]:
        """Search for evidence for a single claim.

        Runs searches in parallel across multiple tools for better performance.
        """
        # Search tools to use (in order of preference for result ranking)
        search_tools = ["search_news_gdelt", "search_news_ddg", "search_web_free"]

        async def _single_search(tool_name: str) -> list[dict]:
            """Run a single search tool with error handling."""
            tool = TOOL_MAP.get(tool_name)
            if not tool:
                return []

            try:
                async with self._search_semaphore:
                    result = await asyncio.wait_for(
                        tool.ainvoke({"query": claim, "max_results": 5}),
                        timeout=self.config.TOOL_TIMEOUT,
                    )

                results = []
                if isinstance(result, list):
                    for item in result:
                        if isinstance(item, dict) and not item.get("error"):
                            # Double defense: Apply date validation again
                            # (tools already filter, but this catches edge cases)
                            if not _is_evidence_recent(item, max_age_days=30):
                                logger.debug(
                                    f"Investigator rejected old evidence: "
                                    f"{item.get('url', '')[:50]}..."
                                )
                                continue

                            item["source_name"] = item.get("source_name", tool_name)
                            results.append(item)
                return results

            except asyncio.TimeoutError:
                logger.warning(f"Search timeout: {tool_name}")
                return []
            except Exception as e:
                logger.warning(f"Search failed ({tool_name}): {e}")
                return []

        # Run all searches in parallel
        search_tasks = [_single_search(tool_name) for tool_name in search_tools]
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Combine results, preserving tool priority order
        all_results: list[dict] = []
        for i, result in enumerate(search_results):
            if isinstance(result, Exception):
                logger.warning(f"Search task failed: {search_tools[i]}: {result}")
                continue
            if isinstance(result, list):
                for item in result:
                    if len(all_results) >= self.config.MAX_EVIDENCE_PER_CLAIM:
                        break
                    all_results.append(item)

            if len(all_results) >= self.config.MAX_EVIDENCE_PER_CLAIM:
                break

        return all_results

    def _hash_url(self, url: str) -> str:
        """Hash URL for deduplication."""
        if not url:
            return ""
        try:
            parsed = urlparse(url.lower().strip())
            normalized = f"{parsed.netloc}{parsed.path}".rstrip("/")
            return hashlib.md5(normalized.encode()).hexdigest()[:12]
        except Exception:
            return hashlib.md5(url.encode()).hexdigest()[:12]

    def _get_credibility_tier(self, source_name: str, url: str) -> str:
        """Determine credibility tier for a source."""
        source_lower = (source_name or "").lower()
        url_lower = (url or "").lower()

        # Check Tier-1 by domain
        for domain in TIER1_DOMAINS:
            if domain in url_lower:
                return "tier1"

        # Check Tier-1 by name (exact word match for short names)
        for name in TIER1_NAMES:
            if name in source_lower:
                return "tier1"

        # Check Tier-2 by domain
        for domain in TIER2_DOMAINS:
            if domain in url_lower:
                return "tier2"

        # Check Tier-2 by name
        for name in TIER2_NAMES:
            if name in source_lower:
                return "tier2"

        return "tier3"

    def _select_related_sources(
        self,
        evidence_docs: list[dict],
        max_count: int = 5,
    ) -> list[RelatedSource]:
        """
        Select best sources for "Related Sources" section.

        Prioritizes:
        1. Tier-1 sources (Reuters, AP, government)
        2. Tier-2 sources (major news orgs)
        3. Higher relevance scores

        Filters out:
        - Excluded domains (Wikipedia, etc.)
        - Old sources (> 30 days based on published date or URL date pattern)
        """
        if not evidence_docs:
            return []

        # Score and categorize each source
        scored_sources = []
        seen_urls = set()

        for doc in evidence_docs:
            url = doc.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            # Filter out excluded domains (Wikipedia, etc.)
            if _is_excluded_domain(url):
                logger.debug(f"Skipping excluded domain for related: {url}")
                continue

            # 3-Layer date validation for related sources
            if not _is_evidence_recent(doc, max_age_days=30):
                logger.debug(f"Skipping old source for related: {url}")
                continue

            source_name = doc.get("source_name", "")
            title = doc.get("title", "")
            snippet = doc.get("snippet", "")

            # Skip if missing essential info
            if not title and not snippet:
                continue

            tier = self._get_credibility_tier(source_name, url)

            # Calculate score (tier1=100, tier2=50, tier3=10)
            tier_score = {"tier1": 100, "tier2": 50, "tier3": 10}.get(tier, 10)

            # Add relevance/credibility bonus from evidence
            relevance = doc.get("relevance_score", 0.5)
            credibility = doc.get("credibility_score", 0.5)
            bonus = (relevance + credibility) * 20

            total_score = tier_score + bonus

            scored_sources.append({
                "url": url,
                "title": title or source_name or url,
                "source_name": source_name or self._extract_domain(url),
                "snippet": self._truncate_snippet(snippet),
                "credibility_tier": tier,
                "score": total_score,
            })

        # Sort by score descending
        scored_sources.sort(key=lambda x: x["score"], reverse=True)

        # Convert to RelatedSource objects
        return [
            RelatedSource(
                url=s["url"],
                title=s["title"],
                source_name=s["source_name"],
                snippet=s["snippet"],
                credibility_tier=s["credibility_tier"],
            )
            for s in scored_sources[:max_count]
        ]

    def _extract_domain(self, url: str) -> str:
        """Extract domain name from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "")
            return domain.split(".")[0].capitalize() if domain else "Unknown"
        except Exception:
            return "Unknown"

    def _truncate_snippet(self, snippet: str, max_length: int = 150) -> str:
        """Truncate snippet to 1-2 sentences for legal compliance."""
        if not snippet:
            return ""
        # Take first sentence or max_length characters
        snippet = snippet.strip()
        # Find first sentence ending
        for punct in [".", "!", "?"]:
            idx = snippet.find(punct)
            if 20 < idx < max_length:
                return snippet[:idx + 1]
        # Fallback: truncate at max_length
        if len(snippet) > max_length:
            return snippet[:max_length].rsplit(" ", 1)[0] + "..."
        return snippet

    # =========================================================================
    # Stage 3: Claim Verification
    # =========================================================================

    async def _verify_claims_node(self, state: dict) -> dict:
        """Verify each claim against evidence."""
        logger.info("Stage 3: Verifying claims")

        claims = state.get("claims", [])
        evidence_docs = state.get("evidence_docs", [])

        if not claims:
            return {**state, "current_stage": "aggregator"}

        # Convert to ExtractedClaim objects
        claim_objects = [ExtractedClaim(**c) for c in claims]

        try:
            result = await self.qa_verifier.verify_claims(
                claim_objects, evidence_docs
            )

            verdicts = [v.model_dump() for v in result.verdicts]

            logger.info(
                "Claims verified",
                extra={
                    "supported": result.supported_count,
                    "refuted": result.refuted_count,
                    "nei": result.nei_count,
                },
            )

            return {
                **state,
                "verdicts": verdicts,
                "current_stage": "aggregator",
            }

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return {
                **state,
                "verdicts": [],
                "errors": state.get("errors", []) + [f"Verification: {e}"],
                "current_stage": "aggregator",
            }

    # =========================================================================
    # Stage 4: Verdict Aggregation
    # =========================================================================

    async def _aggregate_verdicts_node(self, state: dict) -> dict:
        """Aggregate verdicts and calculate reliability with Two-Source Rule check."""
        logger.info("Stage 4: Aggregating verdicts")

        verdicts = state.get("verdicts", [])

        supported = [v for v in verdicts if v.get("verdict") == "SUPPORTED"]
        refuted = [v for v in verdicts if v.get("verdict") == "REFUTED"]
        unverifiable = [v for v in verdicts if v.get("verdict") == "NOT_ENOUGH_INFO"]

        total = len(verdicts)
        reliability = len(supported) / total if total > 0 else 0.0

        # === Multi-Source Confidence Scoring (Two-Source Rule) ===
        evidence_docs = state.get("evidence_docs", [])

        # Build unique source list with credibility tiers
        seen_sources = set()
        evidence_sources = []
        for doc in evidence_docs:
            source_name = doc.get("source_name", "unknown")
            url = doc.get("url", "")

            # Deduplicate by source name
            if source_name in seen_sources:
                continue
            seen_sources.add(source_name)

            tier = self._get_credibility_tier(source_name, url)
            # Map tier1/tier2/tier3 to expected format
            tier_mapping = {
                "tier1": "tier1_news",
                "tier2": "tier2_news",
                "tier3": "tier3_social",
            }
            evidence_sources.append({
                "name": source_name,
                "tier": tier_mapping.get(tier, "tier2_news"),
            })

        # Calculate multi-source confidence
        scorer = MultiSourceConfidenceScorer()
        confidence_result = scorer.calculate_confidence(evidence_sources)

        # Log Two-Source Rule status
        if not confidence_result.two_source_satisfied:
            logger.warning(
                f"Two-Source Rule not satisfied: "
                f"{state.get('original_text', '')[:40]}... "
                f"(sources: {len(evidence_sources)})"
            )
        else:
            logger.info(
                f"Two-Source Rule satisfied: {confidence_result.source_count} sources, "
                f"confidence={confidence_result.score:.2f}"
            )

        logger.info(
            "Aggregation complete",
            extra={
                "supported": len(supported),
                "refuted": len(refuted),
                "unverifiable": len(unverifiable),
                "reliability": f"{reliability:.1%}",
                "confidence_score": f"{confidence_result.score:.2f}",
                "two_source_satisfied": confidence_result.two_source_satisfied,
            },
        )

        return {
            **state,
            "supported_claims": supported,
            "refuted_claims": refuted,
            "unverifiable_claims": unverifiable,
            "overall_reliability": reliability,
            "confidence_result": confidence_result.to_dict(),
            "two_source_satisfied": confidence_result.two_source_satisfied,
            "current_stage": "synthesizer",
        }

    # =========================================================================
    # Stage 5: Article Synthesis (Bilingual)
    # =========================================================================

    async def _synthesize_article_node(self, state: dict) -> dict:
        """Generate bilingual AP Style article from verified claims."""
        logger.info("Stage 5: Synthesizing bilingual article (EN + KO)")

        # Check if marked as duplicate - skip synthesis
        if state.get("is_duplicate"):
            logger.info("Skipping synthesis for duplicate event")
            return {
                **state,
                "article": None,
                "current_stage": "done",
            }

        # === GATE 3: Evidence Sufficiency ===
        if agent_settings.evidence_gate_enabled:
            supported_claims = state.get("supported_claims", [])
            total_claims = len(state.get("claims", []))

            min_supported = agent_settings.min_supported_claims
            min_ratio = agent_settings.min_evidence_ratio

            if len(supported_claims) < min_supported:
                logger.info(
                    f"[GATE3-REJECT] Insufficient evidence: "
                    f"{len(supported_claims)}/{min_supported} supported claims"
                )
                return {
                    **state,
                    "article": None,
                    "article_en": None,
                    "article_ko": None,
                    "skip_reason": "insufficient_evidence",
                    "current_stage": "done",
                }

            if total_claims > 0:
                ratio = len(supported_claims) / total_claims
                if ratio < min_ratio:
                    logger.info(
                        f"[GATE3-REJECT] Low evidence ratio: "
                        f"{ratio:.2%} < {min_ratio:.0%}"
                    )
                    return {
                        **state,
                        "article": None,
                        "article_en": None,
                        "article_ko": None,
                        "skip_reason": "low_evidence_ratio",
                        "current_stage": "done",
                    }

        # Reconstruct VerificationResult
        verdicts = state.get("verdicts", [])
        verdict_objects = [ClaimVerdict(**v) for v in verdicts]

        verification_result = VerificationResult(
            verdicts=verdict_objects,
            supported_count=len(state.get("supported_claims", [])),
            refuted_count=len(state.get("refuted_claims", [])),
            nei_count=len(state.get("unverifiable_claims", [])),
            overall_reliability=state.get("overall_reliability", 0.0),
        )

        # Extract source URLs
        evidence_docs = state.get("evidence_docs", [])
        sources = list({
            doc.get("url") or doc.get("source_name", "unknown")
            for doc in evidence_docs
            if doc.get("url") or doc.get("source_name")
        })

        # Select related sources for "Related Sources" section
        related_sources = self._select_related_sources(evidence_docs, max_count=5)
        logger.info(f"Selected {len(related_sources)} related sources")

        try:
            # Generate bilingual article if Korean is enabled
            if agent_settings.generate_korean:
                bilingual_article = await self.bilingual_generator.generate(
                    event_summary=state.get("original_text", "")[:500],
                    verification_result=verification_result,
                    sources=sources,
                    related_sources=related_sources,
                )

                # Convert to dicts for storage
                article_en = {
                    "headline": bilingual_article.headline_en,
                    "lead": bilingual_article.lead_en,
                    "nut_graph": bilingual_article.nut_graph_en,
                    "body": bilingual_article.body_en,
                    "full_text": bilingual_article.full_text_en,
                }
                article_ko = {
                    "headline": bilingual_article.headline_ko,
                    "lead": bilingual_article.lead_ko,
                    "nut_graph": bilingual_article.nut_graph_ko,
                    "body": bilingual_article.body_ko,
                    "full_text": bilingual_article.full_text_ko,
                }

                logger.info(
                    "Bilingual article generated",
                    extra={
                        "word_count_en": bilingual_article.word_count_en,
                        "word_count_ko": bilingual_article.word_count_ko,
                        "related_sources_count": len(related_sources),
                    },
                )

                return {
                    **state,
                    "article": bilingual_article.model_dump(),
                    "article_en": article_en,
                    "article_ko": article_ko,
                    "related_sources": [s.model_dump() for s in related_sources],
                    "current_stage": "done",
                }
            else:
                # Fallback to English-only article
                article = await self.article_generator.generate(
                    event_summary=state.get("original_text", "")[:500],
                    verification_result=verification_result,
                    sources=sources,
                )

                logger.info(
                    "Article generated (English only)",
                    extra={
                        "word_count": article.metadata.word_count,
                        "related_sources_count": len(related_sources),
                    },
                )

                return {
                    **state,
                    "article": article.model_dump(),
                    "article_en": {
                        "headline": article.headline,
                        "lead": article.lead,
                        "nut_graph": article.nut_graph,
                        "body": article.body,
                        "full_text": article.full_text,
                    },
                    "article_ko": None,
                    "related_sources": [s.model_dump() for s in related_sources],
                    "current_stage": "done",
                }

        except Exception as e:
            logger.error(f"Article generation failed: {e}")
            return {
                **state,
                "article": None,
                "article_en": None,
                "article_ko": None,
                "errors": state.get("errors", []) + [f"Synthesis: {e}"],
                "current_stage": "done",
            }


# =============================================================================
# Convenience Functions
# =============================================================================


async def investigate_claim_level(
    event: str,
    category: str = "general",
) -> dict[str, Any]:
    """
    Run claim-level verification on an event.

    Args:
        event: Event text to verify
        category: Event category

    Returns:
        Investigation result
    """
    agent = ClaimVerificationAgent()
    return await agent.investigate(event, category)


def print_investigation_result(result: dict) -> None:
    """Print investigation result to console."""
    article = result.get("article", {})

    if article and article.get("full_text"):
        print(article["full_text"])
    else:
        print("=" * 70)
        print("INVESTIGATION RESULT")
        print("=" * 70)
        print(f"\nClaims Extracted: {len(result.get('claims', []))}")
        print(f"Evidence Documents: {len(result.get('evidence_docs', []))}")
        print(f"Verdicts: {len(result.get('verdicts', []))}")
        print(f"  - Supported: {len(result.get('supported_claims', []))}")
        print(f"  - Refuted: {len(result.get('refuted_claims', []))}")
        print(f"  - Unverifiable: {len(result.get('unverifiable_claims', []))}")
        print(f"Reliability: {result.get('overall_reliability', 0):.1%}")

        if result.get("errors"):
            print(f"\nErrors: {result['errors']}")

        print("=" * 70)


# =============================================================================
# Alias for compatibility
# =============================================================================

InvestigationAgentV3 = ClaimVerificationAgent
