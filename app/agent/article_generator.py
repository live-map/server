"""
AP Style Article Generator

Generates professional news articles following AP Stylebook guidelines.
Includes proper attribution, hedging language, and AI disclosure.

Key Features:
- Inverted pyramid structure (Lead → Nut Graph → Body)
- Proper hedging for unverified claims ("reportedly", "according to")
- Source attribution
- Per-claim verification breakdown
- AI-generated disclosure

References:
- AP Stylebook AI Guidelines (2024-2026)
- California AI Transparency Act (Effective Jan 2026)
- Reuters AI Principles
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from .claim_extraction import ExtractedClaim
from .config import agent_settings
from .qa_verifier import ClaimVerdict, VerificationResult

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================


class ArticleMetadata(BaseModel):
    """Article metadata for transparency."""

    word_count: int = Field(default=0)
    source_count: int = Field(default=0)
    claims_verified: int = Field(default=0)
    claims_refuted: int = Field(default=0)
    claims_unverifiable: int = Field(default=0)
    verification_score: float = Field(default=0.0)
    ai_generated: bool = Field(default=True)
    human_reviewed: bool = Field(default=False)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class GeneratedArticle(BaseModel):
    """Generated news article with metadata."""

    headline: str = Field(default="")
    lead: str = Field(default="", description="Opening paragraph (WHO, WHAT, WHEN)")
    nut_graph: str = Field(default="", description="Why this matters")
    body: str = Field(default="", description="Main article body")
    claim_breakdown: str = Field(default="", description="Per-claim verification status")
    sources_section: str = Field(default="", description="Source attribution")
    full_text: str = Field(default="", description="Complete formatted article")
    metadata: ArticleMetadata = Field(default_factory=ArticleMetadata)


# =============================================================================
# Prompts
# =============================================================================

ARTICLE_GENERATION_PROMPT = """You are a professional news writer following AP Stylebook guidelines.

Write a news article based on the verified information below.

## EVENT SUMMARY
{event_summary}

## VERIFIED CLAIMS (confidence high)
{verified_claims}

## REFUTED CLAIMS (do not include as fact)
{refuted_claims}

## UNVERIFIED CLAIMS (use hedging language)
{unverified_claims}

## SOURCES
{sources}

## AP STYLE REQUIREMENTS

1. **Lead Paragraph** (25-40 words):
   - Start with WHO and WHAT
   - Include WHEN and WHERE
   - Most important information first

2. **Nut Graph** (2nd paragraph):
   - Explain why this matters
   - Provide context

3. **Body**:
   - Use inverted pyramid (most to least important)
   - Attribution: "said", "according to", "stated"
   - Short paragraphs (1-3 sentences each)

4. **Hedging Language** (for unverified claims):
   - "reportedly"
   - "according to unconfirmed reports"
   - "allegedly"
   - "sources say"

5. **DO NOT**:
   - Include refuted claims as facts
   - Make unsupported assertions
   - Use sensational language
   - Editorialize

## OUTPUT FORMAT

HEADLINE: [Concise, factual headline]

LEAD:
[Opening paragraph - WHO, WHAT, WHEN, WHERE]

NUT_GRAPH:
[Why this matters, context]

BODY:
[Rest of the article with proper attribution]

Write the article:"""


# =============================================================================
# Article Generator
# =============================================================================


class ArticleGenerator:
    """
    Generates AP Style news articles from verified claims.

    Structure:
    1. Headline - Factual, concise
    2. Lead - WHO, WHAT, WHEN, WHERE (25-40 words)
    3. Nut Graph - Why this matters
    4. Body - Inverted pyramid, attributed
    5. Claim Breakdown - Verification status
    6. Sources - Attribution
    """

    def __init__(
        self,
        model: str | None = None,
        temperature: float = 0.3,
    ):
        self.model = model or agent_settings.llm_model
        self.llm = ChatOpenAI(
            model=self.model,
            temperature=temperature,
            api_key=agent_settings.openai_api_key,
        )

    async def generate(
        self,
        event_summary: str,
        verification_result: VerificationResult,
        sources: list[str] | None = None,
    ) -> GeneratedArticle:
        """
        Generate a news article from verification results.

        Args:
            event_summary: Brief summary of the event
            verification_result: Result from claim verification
            sources: List of source URLs/names

        Returns:
            GeneratedArticle with full text and metadata
        """
        logger.info("Generating article", extra={"event": event_summary[:50]})

        # Categorize verdicts
        verified = [v for v in verification_result.verdicts if v.verdict == "SUPPORTED"]
        refuted = [v for v in verification_result.verdicts if v.verdict == "REFUTED"]
        unverified = [v for v in verification_result.verdicts if v.verdict == "NOT_ENOUGH_INFO"]

        # Format for prompt
        verified_text = self._format_claims(verified, "verified")
        refuted_text = self._format_claims(refuted, "refuted")
        unverified_text = self._format_claims(unverified, "unverified")
        sources_text = "\n".join([f"- {s}" for s in (sources or [])[:20]])

        # Generate article
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="You are a professional AP-style news writer."),
                HumanMessage(content=ARTICLE_GENERATION_PROMPT.format(
                    event_summary=event_summary,
                    verified_claims=verified_text or "None",
                    refuted_claims=refuted_text or "None",
                    unverified_claims=unverified_text or "None",
                    sources=sources_text or "No sources available",
                )),
            ])

            article = self._parse_article(response.content)

        except Exception as e:
            logger.error(f"Article generation failed: {e}")
            article = GeneratedArticle(
                headline="Article Generation Failed",
                body=f"Unable to generate article: {e}",
            )

        # Add claim breakdown
        article.claim_breakdown = self._generate_claim_breakdown(
            verified, refuted, unverified
        )

        # Add sources section
        article.sources_section = self._generate_sources_section(
            verification_result.verdicts
        )

        # Generate full text
        article.full_text = self._format_full_article(article)

        # Calculate metadata
        article.metadata = self._calculate_metadata(
            article, verification_result, sources or []
        )

        logger.info(
            "Article generated",
            extra={
                "word_count": article.metadata.word_count,
                "claims_verified": article.metadata.claims_verified,
            },
        )

        return article

    def _format_claims(
        self,
        verdicts: list[ClaimVerdict],
        category: str,
    ) -> str:
        """Format claims for the prompt."""
        if not verdicts:
            return ""

        lines = []
        for v in verdicts:
            conf_label = self._confidence_label(v.confidence)
            lines.append(f"- {v.claim_text} (confidence: {conf_label})")

        return "\n".join(lines)

    def _confidence_label(self, confidence: int) -> str:
        """Convert confidence score to label."""
        if confidence >= 4:
            return "high"
        elif confidence >= 3:
            return "medium"
        else:
            return "low"

    def _parse_article(self, content: str) -> GeneratedArticle:
        """Parse LLM response into article structure."""
        article = GeneratedArticle()

        sections = {
            "HEADLINE:": "headline",
            "LEAD:": "lead",
            "NUT_GRAPH:": "nut_graph",
            "BODY:": "body",
        }

        current_section = None
        current_content: list[str] = []

        for line in content.split("\n"):
            # Check for section headers
            for header, attr in sections.items():
                if line.strip().startswith(header):
                    # Save previous section
                    if current_section:
                        setattr(article, current_section, "\n".join(current_content).strip())
                    current_section = attr
                    # Get content after header on same line
                    remaining = line.strip()[len(header):].strip()
                    current_content = [remaining] if remaining else []
                    break
            else:
                # Not a header, add to current section
                if current_section:
                    current_content.append(line)

        # Save last section
        if current_section:
            setattr(article, current_section, "\n".join(current_content).strip())

        return article

    def _generate_claim_breakdown(
        self,
        verified: list[ClaimVerdict],
        refuted: list[ClaimVerdict],
        unverified: list[ClaimVerdict],
    ) -> str:
        """Generate per-claim verification breakdown."""
        lines = ["", "=" * 60, "VERIFICATION BREAKDOWN", "=" * 60]

        if verified:
            lines.append(f"\n[VERIFIED] ({len(verified)} claims)")
            for v in verified:
                conf_pct = v.confidence * 20
                lines.append(f"  + {v.claim_text}")
                lines.append(f"    Confidence: {conf_pct}%")
                if v.evidence_quotes:
                    lines.append(f"    Evidence: \"{v.evidence_quotes[0][:100]}...\"")

        if refuted:
            lines.append(f"\n[REFUTED] ({len(refuted)} claims)")
            for v in refuted:
                lines.append(f"  - {v.claim_text}")
                lines.append(f"    Reason: {v.reasoning[:100]}...")

        if unverified:
            lines.append(f"\n[UNVERIFIED] ({len(unverified)} claims)")
            for v in unverified:
                lines.append(f"  ? {v.claim_text}")
                lines.append(f"    Reason: Insufficient evidence")

        return "\n".join(lines)

    def _generate_sources_section(
        self,
        verdicts: list[ClaimVerdict],
    ) -> str:
        """Generate sources attribution section."""
        all_sources = set()

        for v in verdicts:
            for s in v.sources_used:
                if s.source_name:
                    all_sources.add(s.source_name)
                elif s.url:
                    # Extract domain from URL
                    try:
                        from urllib.parse import urlparse
                        domain = urlparse(s.url).netloc.replace("www.", "")
                        all_sources.add(domain)
                    except Exception:
                        all_sources.add(s.url[:50])

        if not all_sources:
            return "Sources: Not available"

        sources_list = sorted(all_sources)[:15]
        return "Sources: " + ", ".join(sources_list)

    def _format_full_article(self, article: GeneratedArticle) -> str:
        """Format complete article with all sections."""
        lines = [
            "=" * 70,
            article.headline.upper() if article.headline else "BREAKING NEWS",
            "=" * 70,
            "",
            article.lead,
            "",
            article.nut_graph,
            "",
            article.body,
            "",
            article.claim_breakdown,
            "",
            "-" * 70,
            article.sources_section,
            "-" * 70,
            "",
            "DISCLOSURE: This article was generated with AI assistance.",
            "Verification performed using automated fact-checking system.",
            f"Generated at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            "=" * 70,
        ]

        return "\n".join(lines)

    def _calculate_metadata(
        self,
        article: GeneratedArticle,
        verification_result: VerificationResult,
        sources: list[str],
    ) -> ArticleMetadata:
        """Calculate article metadata."""
        full_text = f"{article.lead} {article.nut_graph} {article.body}"
        word_count = len(full_text.split())

        return ArticleMetadata(
            word_count=word_count,
            source_count=len(sources),
            claims_verified=verification_result.supported_count,
            claims_refuted=verification_result.refuted_count,
            claims_unverifiable=verification_result.nei_count,
            verification_score=verification_result.overall_reliability,
            ai_generated=True,
            human_reviewed=False,
            generated_at=datetime.utcnow(),
        )


# =============================================================================
# Convenience Functions
# =============================================================================


async def generate_article(
    event_summary: str,
    verification_result: VerificationResult,
    sources: list[str] | None = None,
) -> GeneratedArticle:
    """
    Convenience function to generate an article.

    Args:
        event_summary: Brief event summary
        verification_result: Verification results
        sources: List of sources

    Returns:
        GeneratedArticle
    """
    generator = ArticleGenerator()
    return await generator.generate(event_summary, verification_result, sources)


def format_article_for_display(article: GeneratedArticle) -> str:
    """Format article for terminal/console display."""
    return article.full_text
