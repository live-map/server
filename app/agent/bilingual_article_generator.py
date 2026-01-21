"""
Bilingual Article Generator (English + Korean)

Generates professional news articles in both English and Korean
following AP Stylebook guidelines and Korean journalistic conventions.

Key Features:
- Single LLM call for both languages (consistency)
- AP Style for English
- 합니다체 (formal style) for Korean
- Proper Korean terminology and formatting
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from .config import agent_settings
from .qa_verifier import ClaimVerdict, VerificationResult

logger = logging.getLogger(__name__)


class BilingualArticle(BaseModel):
    """Bilingual article output."""

    # English
    headline_en: str = ""
    lead_en: str = ""
    nut_graph_en: str = ""
    body_en: str = ""
    full_text_en: str = ""

    # Korean
    headline_ko: str = ""
    lead_ko: str = ""
    nut_graph_ko: str = ""
    body_ko: str = ""
    full_text_ko: str = ""

    # Metadata
    word_count_en: int = 0
    word_count_ko: int = 0
    claims_verified: int = 0
    claims_refuted: int = 0
    claims_unverifiable: int = 0
    verification_score: float = 0.0
    source_count: int = 0
    generated_at: datetime = Field(default_factory=datetime.utcnow)


BILINGUAL_ARTICLE_PROMPT = """You are a professional news writer. Generate a news article in BOTH English AND Korean.

## EVENT SUMMARY
{event_summary}

## VERIFIED CLAIMS (use as facts)
{verified_claims}

## REFUTED CLAIMS (do NOT include as facts)
{refuted_claims}

## UNVERIFIED CLAIMS (use hedging language)
{unverified_claims}

## SOURCES
{sources}

---

## ENGLISH ARTICLE (AP Style)

1. **Lead Paragraph** (25-40 words):
   - WHO, WHAT, WHEN, WHERE
   - Most important information first

2. **Nut Graph** (2nd paragraph):
   - Why this matters, context

3. **Body**:
   - Inverted pyramid structure
   - Attribution: "said", "according to"
   - Short paragraphs (1-3 sentences)

4. **Hedging** (for unverified):
   - "reportedly", "according to unconfirmed reports"

---

## KOREAN ARTICLE (합니다체)

1. **리드 문단** (25-40 단어):
   - 누가, 무엇을, 언제, 어디서
   - 가장 중요한 정보 먼저

2. **넛 그래프** (2번째 문단):
   - 왜 중요한지, 맥락 설명

3. **본문**:
   - 역피라미드 구조
   - 인용: "~라고 말했다", "~에 따르면"
   - 짧은 문단 (1-3문장)

4. **한국어 스타일**:
   - 합니다체 사용 (공식 문어체)
   - 표준 지명: 우크라이나, 이스라엘, 가자 지구
   - 숫자 형식: 3,500명, 100억 원
   - 인용: "~라고 전했다", "~에 따르면"

---

## OUTPUT FORMAT (follow exactly)

=== ENGLISH ===
HEADLINE_EN: [Factual, concise headline]

LEAD_EN:
[Opening paragraph - WHO, WHAT, WHEN, WHERE]

NUT_GRAPH_EN:
[Why this matters, context]

BODY_EN:
[Rest of the article]

=== KOREAN ===
HEADLINE_KO: [사실 기반 헤드라인]

LEAD_KO:
[리드 문단 - 누가, 무엇을, 언제, 어디서]

NUT_GRAPH_KO:
[왜 중요한지, 맥락]

BODY_KO:
[본문 나머지]

Write the bilingual article:"""


class BilingualArticleGenerator:
    """
    Generates bilingual news articles (English + Korean).

    Uses single LLM call for consistency between languages.
    """

    def __init__(
        self,
        model: str | None = None,
        temperature: float = 0.3,
        llm_timeout: float = 90.0,  # Longer timeout for bilingual
    ):
        self.model = model or agent_settings.llm_model
        self.llm_timeout = llm_timeout
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
    ) -> BilingualArticle:
        """
        Generate bilingual article from verification results.

        Args:
            event_summary: Brief summary of the event
            verification_result: Result from claim verification
            sources: List of source URLs/names

        Returns:
            BilingualArticle with EN and KO content
        """
        logger.info("Generating bilingual article", extra={"event": event_summary[:50]})

        # Categorize verdicts
        verified = [v for v in verification_result.verdicts if v.verdict == "SUPPORTED"]
        refuted = [v for v in verification_result.verdicts if v.verdict == "REFUTED"]
        unverified = [v for v in verification_result.verdicts if v.verdict == "NOT_ENOUGH_INFO"]

        # Format for prompt
        verified_text = self._format_claims(verified) or "None"
        refuted_text = self._format_claims(refuted) or "None"
        unverified_text = self._format_claims(unverified) or "None"
        sources_text = "\n".join([f"- {s}" for s in (sources or [])[:15]]) or "No sources available"

        try:
            response = await asyncio.wait_for(
                self.llm.ainvoke([
                    SystemMessage(content="You are a professional bilingual news writer (English/Korean)."),
                    HumanMessage(content=BILINGUAL_ARTICLE_PROMPT.format(
                        event_summary=event_summary,
                        verified_claims=verified_text,
                        refuted_claims=refuted_text,
                        unverified_claims=unverified_text,
                        sources=sources_text,
                    )),
                ]),
                timeout=self.llm_timeout,
            )

            article = self._parse_bilingual_response(response.content)

        except asyncio.TimeoutError:
            logger.error(f"Bilingual generation timed out after {self.llm_timeout}s")
            article = BilingualArticle(
                headline_en="Article Generation Timeout",
                body_en=f"Unable to generate article: LLM timed out after {self.llm_timeout}s",
                headline_ko="기사 생성 시간 초과",
                body_ko=f"기사를 생성할 수 없습니다: LLM 시간 초과 ({self.llm_timeout}초)",
            )
        except Exception as e:
            logger.error(f"Bilingual generation failed: {e}")
            article = BilingualArticle(
                headline_en="Article Generation Failed",
                body_en=f"Unable to generate article: {e}",
                headline_ko="기사 생성 실패",
                body_ko=f"기사를 생성할 수 없습니다: {e}",
            )

        # Generate full text for both languages
        article.full_text_en = self._format_full_article_en(article)
        article.full_text_ko = self._format_full_article_ko(article)

        # Calculate metadata
        article.word_count_en = len(f"{article.lead_en} {article.nut_graph_en} {article.body_en}".split())
        article.word_count_ko = len(f"{article.lead_ko} {article.nut_graph_ko} {article.body_ko}".split())
        article.claims_verified = verification_result.supported_count
        article.claims_refuted = verification_result.refuted_count
        article.claims_unverifiable = verification_result.nei_count
        article.verification_score = verification_result.overall_reliability
        article.source_count = len(sources) if sources else 0

        logger.info(
            "Bilingual article generated",
            extra={
                "word_count_en": article.word_count_en,
                "word_count_ko": article.word_count_ko,
            },
        )

        return article

    def _format_claims(self, verdicts: list[ClaimVerdict]) -> str:
        """Format claims for the prompt."""
        if not verdicts:
            return ""

        lines = []
        for v in verdicts:
            conf_label = "high" if v.confidence >= 4 else "medium" if v.confidence >= 3 else "low"
            lines.append(f"- {v.claim_text} (confidence: {conf_label})")

        return "\n".join(lines)

    def _parse_bilingual_response(self, content: str) -> BilingualArticle:
        """Parse LLM response into bilingual article structure."""
        article = BilingualArticle()

        # Section patterns
        en_patterns = {
            "headline_en": ["HEADLINE_EN:", "**HEADLINE_EN:**"],
            "lead_en": ["LEAD_EN:", "**LEAD_EN:**"],
            "nut_graph_en": ["NUT_GRAPH_EN:", "**NUT_GRAPH_EN:**"],
            "body_en": ["BODY_EN:", "**BODY_EN:**"],
        }
        ko_patterns = {
            "headline_ko": ["HEADLINE_KO:", "**HEADLINE_KO:**"],
            "lead_ko": ["LEAD_KO:", "**LEAD_KO:**"],
            "nut_graph_ko": ["NUT_GRAPH_KO:", "**NUT_GRAPH_KO:**"],
            "body_ko": ["BODY_KO:", "**BODY_KO:**"],
        }

        all_patterns = {**en_patterns, **ko_patterns}

        current_section = None
        current_content: list[str] = []

        for line in content.split("\n"):
            line_stripped = line.strip()
            line_upper = line_stripped.upper()

            # Skip language markers
            if line_upper in ["=== ENGLISH ===", "=== KOREAN ==="]:
                continue

            found_section = False

            # Check for section headers
            for attr, patterns in all_patterns.items():
                for pattern in patterns:
                    if line_upper.startswith(pattern.upper()):
                        # Save previous section
                        if current_section:
                            setattr(article, current_section, "\n".join(current_content).strip())

                        current_section = attr
                        # Get content after header
                        remaining = line_stripped[len(pattern):].strip()
                        remaining = remaining.strip("*").strip()
                        current_content = [remaining] if remaining else []
                        found_section = True
                        break
                if found_section:
                    break

            if not found_section and current_section:
                current_content.append(line)

        # Save last section
        if current_section:
            setattr(article, current_section, "\n".join(current_content).strip())

        # Log parsing results
        logger.info(
            "Bilingual article parsed",
            extra={
                "has_headline_en": bool(article.headline_en),
                "has_headline_ko": bool(article.headline_ko),
                "has_lead_en": bool(article.lead_en),
                "has_lead_ko": bool(article.lead_ko),
            }
        )

        return article

    def _format_full_article_en(self, article: BilingualArticle) -> str:
        """Format complete English article."""
        lines = [
            "=" * 70,
            article.headline_en.upper() if article.headline_en else "BREAKING NEWS",
            "=" * 70,
            "",
            article.lead_en,
            "",
            article.nut_graph_en,
            "",
            article.body_en,
            "",
            "-" * 70,
            "DISCLOSURE: This article was generated with AI assistance.",
            f"Generated at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            "=" * 70,
        ]
        return "\n".join(lines)

    def _format_full_article_ko(self, article: BilingualArticle) -> str:
        """Format complete Korean article."""
        lines = [
            "=" * 70,
            article.headline_ko if article.headline_ko else "속보",
            "=" * 70,
            "",
            article.lead_ko,
            "",
            article.nut_graph_ko,
            "",
            article.body_ko,
            "",
            "-" * 70,
            "알림: 이 기사는 AI 지원을 통해 생성되었습니다.",
            f"생성 시각: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            "=" * 70,
        ]
        return "\n".join(lines)

    def to_dict(self, article: BilingualArticle) -> dict[str, Any]:
        """Convert article to dictionary for storage."""
        return {
            "en": {
                "headline": article.headline_en,
                "lead": article.lead_en,
                "nut_graph": article.nut_graph_en,
                "body": article.body_en,
                "full_text": article.full_text_en,
            },
            "ko": {
                "headline": article.headline_ko,
                "lead": article.lead_ko,
                "nut_graph": article.nut_graph_ko,
                "body": article.body_ko,
                "full_text": article.full_text_ko,
            },
            "metadata": {
                "word_count_en": article.word_count_en,
                "word_count_ko": article.word_count_ko,
                "claims_verified": article.claims_verified,
                "claims_refuted": article.claims_refuted,
                "claims_unverifiable": article.claims_unverifiable,
                "verification_score": article.verification_score,
                "source_count": article.source_count,
                "generated_at": article.generated_at.isoformat(),
            },
        }


async def generate_bilingual_article(
    event_summary: str,
    verification_result: VerificationResult,
    sources: list[str] | None = None,
) -> BilingualArticle:
    """Convenience function to generate bilingual article."""
    generator = BilingualArticleGenerator()
    return await generator.generate(event_summary, verification_result, sources)
