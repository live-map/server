"""
QA-Based Claim Verification Module (2026 SOTA)

Verifies claims using Question-Answering approach with LLM.
Based on AIC CTU (FEVER 8 Winner) and HerO 2 (AVeriTeC 2025 Runner-up).

Key Features:
- Question generation from claims
- Document-level evidence retrieval (~60K chars context)
- LLM-based verdict with confidence scoring
- Per-claim breakdown with evidence quotes

References:
- AIC CTU: https://arxiv.org/html/2508.04390
- HerO 2: https://arxiv.org/html/2507.11004
- AVeriTeC Dataset: Real-world claim verification
"""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from .claim_extraction import ExtractedClaim
from .config import agent_settings

logger = logging.getLogger(__name__)


# =============================================================================
# Source Credibility Configuration
# =============================================================================

# High credibility sources - major wire services and reputable outlets
HIGH_CREDIBILITY_SOURCES: dict[str, float] = {
    # Wire services (highest credibility)
    "reuters.com": 1.5,
    "apnews.com": 1.5,
    "afp.com": 1.5,
    # Major international broadcasters
    "bbc.com": 1.4,
    "bbc.co.uk": 1.4,
    "aljazeera.com": 1.3,
    "france24.com": 1.3,
    "dw.com": 1.3,
    # Quality newspapers
    "theguardian.com": 1.3,
    "nytimes.com": 1.3,
    "washingtonpost.com": 1.3,
    "economist.com": 1.3,
    # Government/official sources
    ".gov": 1.4,
    ".mil": 1.3,
    ".int": 1.3,
}

# Low credibility patterns - tabloids, unknown, or unreliable sources
LOW_CREDIBILITY_PATTERNS: dict[str, float] = {
    # Tabloid patterns
    "tabloid": 0.5,
    "daily-mail": 0.6,
    "thesun.": 0.5,
    "mirror.co.uk": 0.6,
    # Content farms / aggregators
    "buzzfeed": 0.7,
    "huffpost": 0.7,
    # Default for unknown sources
    "unknown": 0.7,
}


def get_source_credibility(url: str, source_name: str = "") -> float:
    """
    Get credibility score for a source.

    Args:
        url: Source URL
        source_name: Source name (optional)

    Returns:
        Credibility multiplier (0.5 - 1.5)
    """
    check_string = f"{url} {source_name}".lower()

    # Check high credibility sources first
    for pattern, score in HIGH_CREDIBILITY_SOURCES.items():
        if pattern in check_string:
            return score

    # Check low credibility patterns
    for pattern, score in LOW_CREDIBILITY_PATTERNS.items():
        if pattern in check_string:
            return score

    # Default credibility for unknown but legitimate-looking sources
    if url and "." in url:
        return 1.0

    return 0.7  # Unknown source


# =============================================================================
# Data Models
# =============================================================================


VerdictType = Literal["SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"]


class EvidenceSource(BaseModel):
    """Evidence source used for verification."""

    url: str = Field(default="")
    title: str = Field(default="")
    snippet: str = Field(default="")
    source_name: str = Field(default="unknown")
    relevance_score: float = Field(default=0.0)
    credibility_score: float = Field(default=1.0, description="Source credibility multiplier")


class ClaimVerdict(BaseModel):
    """Verification verdict for a single claim."""

    claim_id: str = Field(description="ID of the verified claim")
    claim_text: str = Field(description="Original claim text")
    verdict: VerdictType = Field(description="Verification verdict")
    confidence: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Confidence level (1-5 Likert scale)",
    )
    evidence_quotes: list[str] = Field(
        default_factory=list,
        description="Key quotes supporting the verdict",
    )
    reasoning: str = Field(
        default="",
        description="Explanation of the verdict",
    )
    questions_asked: list[str] = Field(
        default_factory=list,
        description="Questions generated to verify the claim",
    )
    sources_used: list[EvidenceSource] = Field(
        default_factory=list,
        description="Sources used for verification",
    )


class VerificationResult(BaseModel):
    """Result of verifying multiple claims."""

    verdicts: list[ClaimVerdict] = Field(default_factory=list)
    supported_count: int = Field(default=0)
    refuted_count: int = Field(default=0)
    nei_count: int = Field(default=0)
    overall_reliability: float = Field(
        default=0.0,
        description="Proportion of supported claims",
    )


# =============================================================================
# Prompts
# =============================================================================

QUESTION_GENERATION_PROMPT = """Generate 2-4 specific questions that would help verify the following claim.

CLAIM: {claim}

Requirements:
1. Questions should be answerable from news articles or official sources
2. Focus on verifiable facts (who, what, when, where, how many)
3. Avoid yes/no questions - prefer specific factual questions

Output format:
Q1: [question]
Q2: [question]
..."""

VERIFICATION_PROMPT = """You are a professional fact-checker. Verify the following claim based STRICTLY on the evidence provided.

CLAIM TO VERIFY:
{claim}

EVIDENCE DOCUMENTS:
{evidence}

VERIFICATION QUESTIONS:
{questions}

## CRITICAL GROUNDING RULES (MUST FOLLOW)

1. **ONLY USE PROVIDED EVIDENCE**: You MUST only cite information that explicitly appears in the evidence documents above. Do NOT use any external knowledge or make assumptions.

2. **EXPLICIT SOURCE ATTRIBUTION**: When citing information, ALWAYS specify the exact source by name:
   - CORRECT: "According to Reuters, 50 people were injured..."
   - CORRECT: "The BBC reports that the attack occurred at 3pm..."
   - WRONG: "According to reports..." (too vague)
   - WRONG: "Sources say..." (unspecified)
   - WRONG: "It is reported that..." (no specific source)

3. **NOT_ENOUGH_INFO BY DEFAULT**: If the evidence documents do NOT contain information to verify the claim, you MUST return NOT_ENOUGH_INFO. Do NOT guess or infer facts that are not explicitly stated.

4. **NO HALLUCINATION**: If a specific detail (number, name, date, location) is not present in the evidence, do NOT include it. Only report what you can directly quote from the evidence.

## Instructions

1. Read all evidence documents carefully
2. For each question, search for relevant information ONLY in the provided evidence
3. If information is found, note the SPECIFIC SOURCE NAME
4. If information is NOT found in the evidence, mark as NOT_ENOUGH_INFO
5. Provide EXACT QUOTES from the evidence documents (with source attribution)

## Verdict Criteria

- **SUPPORTED**: Multiple sources IN THE PROVIDED EVIDENCE confirm the claim with consistent information
- **REFUTED**: Evidence IN THE PROVIDED DOCUMENTS directly contradicts the claim
- **NOT_ENOUGH_INFO**:
  - Evidence does not address the claim
  - Evidence is insufficient to verify
  - Evidence is conflicting
  - You cannot find the information in the provided documents

## Output Format

VERDICT: SUPPORTED | REFUTED | NOT_ENOUGH_INFO
CONFIDENCE: 1-5 (1=very uncertain, 5=very certain)
EVIDENCE_QUOTES:
- "[Source Name]: exact quote from the evidence"
- "[Source Name]: another quote with source attribution"
REASONING: [Brief explanation citing ONLY information from the provided evidence. Include source names.]

Provide your analysis:"""


# =============================================================================
# QA Verifier
# =============================================================================


class QAVerifier:
    """
    QA-Based Claim Verifier using LLM.

    Pipeline (based on AIC CTU / HerO 2):
    1. Generate verification questions from claim
    2. Gather evidence documents
    3. LLM determines verdict based on Q&A analysis
    """

    def __init__(
        self,
        model: str | None = None,
        temperature: float = 0.1,
        max_evidence_chars: int = 60000,  # ~60K chars per AIC CTU
        llm_timeout: float = 60.0,
        max_concurrent_verifications: int = 3,
    ):
        self.model = model or agent_settings.llm_model
        self.temperature = temperature
        self.max_evidence_chars = max_evidence_chars
        self.llm_timeout = llm_timeout
        self.max_concurrent = max_concurrent_verifications

        # Semaphore for rate limiting concurrent LLM calls
        self._verification_semaphore = asyncio.Semaphore(max_concurrent_verifications)

        self.llm = ChatOpenAI(
            model=self.model,
            temperature=self.temperature,
            api_key=agent_settings.openai_api_key,
        )

    async def verify_claim(
        self,
        claim: ExtractedClaim | str,
        evidence_docs: list[dict],
    ) -> ClaimVerdict:
        """
        Verify a single claim against evidence.

        Args:
            claim: Claim to verify (ExtractedClaim or string)
            evidence_docs: List of evidence documents with title, content, url

        Returns:
            ClaimVerdict with verdict, confidence, and reasoning
        """
        claim_text = claim.text if isinstance(claim, ExtractedClaim) else claim
        claim_id = claim.id if isinstance(claim, ExtractedClaim) else "claim_001"

        logger.info(
            "Verifying claim",
            extra={"claim_id": claim_id, "evidence_count": len(evidence_docs)},
        )

        # Step 1: Generate verification questions
        questions = await self._generate_questions(claim_text)

        # Step 2: Prepare evidence context
        evidence_context = self._prepare_evidence_context(evidence_docs)
        sources = self._extract_sources(evidence_docs)

        # Step 3: Get LLM verdict
        verdict_data = await self._get_verdict(
            claim_text, evidence_context, questions
        )

        # Step 4: Adjust confidence based on source credibility
        original_confidence = verdict_data.get("confidence", 3)
        adjusted_confidence = self._adjust_confidence_by_credibility(
            original_confidence, sources
        )

        # Step 5: Enforce minimum 2 unique sources for SUPPORTED verdict
        final_verdict = verdict_data.get("verdict", "NOT_ENOUGH_INFO")
        if final_verdict == "SUPPORTED":
            # Count unique high-credibility sources
            unique_sources = set()
            for source in sources:
                if source.credibility_score >= 1.0:  # Only count standard+ sources
                    unique_sources.add(source.source_name)

            if len(unique_sources) < 2:
                logger.info(
                    f"Downgrading SUPPORTED to NOT_ENOUGH_INFO: "
                    f"only {len(unique_sources)} unique source(s) found, need 2+"
                )
                final_verdict = "NOT_ENOUGH_INFO"
                adjusted_confidence = min(adjusted_confidence, 2)

        verdict = ClaimVerdict(
            claim_id=claim_id,
            claim_text=claim_text,
            verdict=final_verdict,
            confidence=adjusted_confidence,
            evidence_quotes=verdict_data.get("evidence_quotes", []),
            reasoning=verdict_data.get("reasoning", ""),
            questions_asked=questions,
            sources_used=sources,
        )

        logger.info(
            "Claim verified",
            extra={
                "claim_id": claim_id,
                "verdict": verdict.verdict,
                "confidence": verdict.confidence,
            },
        )

        return verdict

    async def verify_claims(
        self,
        claims: list[ExtractedClaim],
        evidence_docs: list[dict],
    ) -> VerificationResult:
        """
        Verify multiple claims against evidence.

        Args:
            claims: List of claims to verify
            evidence_docs: Evidence documents

        Returns:
            VerificationResult with all verdicts and statistics
        """
        if not claims:
            return VerificationResult()

        logger.info(
            "Verifying multiple claims",
            extra={"claim_count": len(claims), "max_concurrent": self.max_concurrent},
        )

        # Helper function for rate-limited verification
        async def verify_with_semaphore(claim: ExtractedClaim) -> ClaimVerdict:
            async with self._verification_semaphore:
                try:
                    return await self.verify_claim(claim, evidence_docs)
                except Exception as e:
                    logger.error(f"Failed to verify claim {claim.id}: {e}")
                    return ClaimVerdict(
                        claim_id=claim.id,
                        claim_text=claim.text,
                        verdict="NOT_ENOUGH_INFO",
                        confidence=1,
                        reasoning=f"Verification failed: {e}",
                    )

        # Verify claims in parallel with rate limiting
        verdicts = await asyncio.gather(
            *[verify_with_semaphore(claim) for claim in claims]
        )

        # Calculate statistics
        supported = sum(1 for v in verdicts if v.verdict == "SUPPORTED")
        refuted = sum(1 for v in verdicts if v.verdict == "REFUTED")
        nei = sum(1 for v in verdicts if v.verdict == "NOT_ENOUGH_INFO")

        reliability = supported / len(verdicts) if verdicts else 0.0

        result = VerificationResult(
            verdicts=verdicts,
            supported_count=supported,
            refuted_count=refuted,
            nei_count=nei,
            overall_reliability=reliability,
        )

        logger.info(
            "Verification complete",
            extra={
                "supported": supported,
                "refuted": refuted,
                "nei": nei,
                "reliability": f"{reliability:.2%}",
            },
        )

        return result

    async def _generate_questions(self, claim: str) -> list[str]:
        """Generate verification questions for a claim."""
        try:
            response = await asyncio.wait_for(
                self.llm.ainvoke([
                    SystemMessage(content="You are a fact-checker generating verification questions."),
                    HumanMessage(content=QUESTION_GENERATION_PROMPT.format(claim=claim)),
                ]),
                timeout=self.llm_timeout,
            )

            questions = []
            for line in response.content.split("\n"):
                line = line.strip()
                if line.startswith("Q") and ":" in line:
                    question = line.split(":", 1)[1].strip()
                    if question:
                        questions.append(question)

            return questions[:4] if questions else [f"Is the following claim true: {claim}?"]

        except asyncio.TimeoutError:
            logger.warning(f"Question generation timed out after {self.llm_timeout}s")
            return [f"Is the following claim true: {claim}?"]
        except Exception as e:
            logger.warning(f"Question generation failed: {e}")
            return [f"Is the following claim true: {claim}?"]

    def _prepare_evidence_context(self, evidence_docs: list[dict]) -> str:
        """Prepare evidence context within token limit, with credibility labels."""
        context_parts = []
        total_chars = 0

        for doc in evidence_docs:
            title = doc.get("title", "Untitled")
            content = doc.get("content", doc.get("snippet", ""))
            source = doc.get("source_name", doc.get("url", "unknown"))
            url = doc.get("url", "")

            # Get credibility and label
            credibility = get_source_credibility(url, source)
            if credibility >= 1.3:
                cred_label = "HIGH CREDIBILITY"
            elif credibility >= 1.0:
                cred_label = "STANDARD"
            else:
                cred_label = "LOW CREDIBILITY"

            doc_text = f"[Source: {source}] [{cred_label}]\nTitle: {title}\n{content}\n\n"

            if total_chars + len(doc_text) > self.max_evidence_chars:
                # Truncate this document
                remaining = self.max_evidence_chars - total_chars - 100
                if remaining > 200:
                    doc_text = doc_text[:remaining] + "..."
                    context_parts.append(doc_text)
                break

            context_parts.append(doc_text)
            total_chars += len(doc_text)

        return "".join(context_parts) or "No evidence available."

    def _extract_sources(self, evidence_docs: list[dict]) -> list[EvidenceSource]:
        """Extract source information from evidence documents with credibility scores."""
        sources = []
        seen_urls = set()

        for doc in evidence_docs[:20]:  # Limit to 20 sources
            url = doc.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)

            source_name = doc.get("source_name", "unknown")
            credibility = get_source_credibility(url, source_name)

            sources.append(EvidenceSource(
                url=url,
                title=doc.get("title", ""),
                snippet=doc.get("content", doc.get("snippet", ""))[:200],
                source_name=source_name,
                credibility_score=credibility,
            ))

            logger.debug(
                f"Source credibility: {source_name} ({url[:50]}...) -> {credibility}"
            )

        return sources

    async def _get_verdict(
        self,
        claim: str,
        evidence: str,
        questions: list[str],
    ) -> dict:
        """Get LLM verdict for claim."""
        questions_text = "\n".join([f"- {q}" for q in questions])

        try:
            response = await asyncio.wait_for(
                self.llm.ainvoke([
                    SystemMessage(content=(
                        "You are a professional fact-checker. You MUST only use information "
                        "from the provided evidence documents. Never use external knowledge. "
                        "Always cite sources explicitly by name. If evidence is insufficient, "
                        "return NOT_ENOUGH_INFO."
                    )),
                    HumanMessage(content=VERIFICATION_PROMPT.format(
                        claim=claim,
                        evidence=evidence,
                        questions=questions_text,
                    )),
                ]),
                timeout=self.llm_timeout,
            )

            return self._parse_verdict(response.content)

        except asyncio.TimeoutError:
            logger.error(f"Verdict generation timed out after {self.llm_timeout}s")
            return {
                "verdict": "NOT_ENOUGH_INFO",
                "confidence": 1,
                "reasoning": f"Verification timed out after {self.llm_timeout}s",
            }
        except Exception as e:
            logger.error(f"Verdict generation failed: {e}")
            return {
                "verdict": "NOT_ENOUGH_INFO",
                "confidence": 1,
                "reasoning": f"Verification failed: {e}",
            }

    def _parse_verdict(self, content: str) -> dict:
        """Parse LLM verdict response."""
        result = {
            "verdict": "NOT_ENOUGH_INFO",
            "confidence": 3,
            "evidence_quotes": [],
            "reasoning": "",
        }

        lines = content.split("\n")
        in_quotes = False
        quotes = []

        for line in lines:
            line = line.strip()

            if line.startswith("VERDICT:"):
                verdict_text = line[8:].strip().upper()
                if verdict_text in ("SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"):
                    result["verdict"] = verdict_text

            elif line.startswith("CONFIDENCE:"):
                try:
                    conf_text = line[11:].strip()
                    # Handle various formats: "4", "4/5", "80%", "4 out of 5"
                    if "%" in conf_text:
                        # Convert percentage to 1-5 scale
                        pct = int(conf_text.replace("%", "").split()[0])
                        conf = max(1, min(5, round(pct / 20)))
                    elif "/" in conf_text:
                        # Handle "4/5" format
                        numerator = int(conf_text.split("/")[0].strip())
                        conf = max(1, min(5, numerator))
                    else:
                        # Handle "4" or "4 out of 5" format
                        conf = int(conf_text.split()[0])
                    result["confidence"] = max(1, min(5, conf))
                except (ValueError, IndexError):
                    # Keep default confidence (3)
                    logger.debug(f"Could not parse confidence from: {line}")

            elif line.startswith("EVIDENCE_QUOTES:"):
                in_quotes = True

            elif line.startswith("REASONING:"):
                in_quotes = False
                result["reasoning"] = line[10:].strip()

            elif in_quotes and line.startswith("-"):
                quote = line.lstrip("- ").strip().strip('"\'')
                if quote:
                    quotes.append(quote)

            elif not in_quotes and result["reasoning"] and line:
                # Continue reasoning on next line
                result["reasoning"] += " " + line

        result["evidence_quotes"] = quotes[:5]  # Max 5 quotes
        return result

    def _adjust_confidence_by_credibility(
        self,
        confidence: int,
        sources: list[EvidenceSource],
    ) -> int:
        """
        Adjust confidence based on source credibility.

        Rules:
        - 2+ high credibility sources confirm -> confidence +1 (max 5)
        - Only low credibility sources -> confidence -1 (min 1)
        - High and low credibility conflict -> favor high credibility

        Args:
            confidence: Original LLM confidence (1-5)
            sources: List of evidence sources with credibility scores

        Returns:
            Adjusted confidence (1-5)
        """
        if not sources:
            return confidence

        high_cred_count = sum(1 for s in sources if s.credibility_score >= 1.3)
        low_cred_count = sum(1 for s in sources if s.credibility_score < 1.0)
        total_count = len(sources)

        # All sources are high credibility
        if high_cred_count >= 2:
            adjusted = min(5, confidence + 1)
            logger.debug(
                f"Confidence boost: {confidence} -> {adjusted} "
                f"({high_cred_count} high credibility sources)"
            )
            return adjusted

        # Only low credibility sources
        if low_cred_count == total_count and total_count > 0:
            adjusted = max(1, confidence - 1)
            logger.debug(
                f"Confidence penalty: {confidence} -> {adjusted} "
                f"(only low credibility sources)"
            )
            return adjusted

        return confidence


# =============================================================================
# Convenience Functions
# =============================================================================


async def verify_claim(
    claim: str,
    evidence_docs: list[dict],
) -> ClaimVerdict:
    """
    Convenience function to verify a single claim.

    Args:
        claim: Claim text to verify
        evidence_docs: List of evidence documents

    Returns:
        ClaimVerdict with verdict and reasoning
    """
    verifier = QAVerifier()
    return await verifier.verify_claim(claim, evidence_docs)


async def verify_claims_batch(
    claims: list[ExtractedClaim],
    evidence_docs: list[dict],
) -> VerificationResult:
    """
    Verify multiple claims in batch.

    Args:
        claims: List of claims to verify
        evidence_docs: Evidence documents

    Returns:
        VerificationResult with all verdicts
    """
    verifier = QAVerifier()
    return await verifier.verify_claims(claims, evidence_docs)
