"""
LLM-based News Classifier using Deepinfra

Replaces pattern-based filtering (patterns.py, checkworthiness.py, specificity.py)
with a single LLM call that handles:
1. IS_NEWS: Is this a real breaking news event?
2. CATEGORY: war|conflict|politics|security|military|terrorism|diplomacy|protest|other
3. IS_SIGNIFICANT: Is this internationally significant?
4. TEMPORAL_CATEGORY: Temporal classification (breaking, developing, retrospective, predictive, timeless)

Cost: ~$3-5/month for ~2000 articles/day using Llama 3.1 8B

Phase 6: Temporal Classification Enhancement
- Added TemporalCategory enum for 5-class temporal classification
- Enhanced prompt with current date context and linguistic markers
- Auto-reject RETROSPECTIVE and PREDICTIVE articles
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import httpx

from .config import agent_settings

logger = logging.getLogger(__name__)


class NewsCategory(str, Enum):
    """International affairs categories"""
    WAR = "war"
    CONFLICT = "conflict"
    POLITICS = "politics"
    SECURITY = "security"
    MILITARY = "military"
    TERRORISM = "terrorism"
    DIPLOMACY = "diplomacy"
    PROTEST = "protest"
    OTHER = "other"


class TemporalCategory(str, Enum):
    """
    Temporal classification categories based on academic research.

    References:
    - TCELongBench (2024): 88,821 QA pairs for temporal complex events
    - TimeBank (TIMEX3): English news temporal annotation
    """
    BREAKING = "breaking"          # 24시간 이내 실시간 이벤트
    DEVELOPING = "developing"      # 진행 중 이벤트 (1-7일)
    RETROSPECTIVE = "retrospective"  # 회고/분석/리뷰 (NOT publishable)
    PREDICTIVE = "predictive"      # 미래 예측/추측 (NOT publishable)
    TIMELESS = "timeless"          # 시간 무관 (백과사전적)


# Temporal categories that should NOT be published
NON_PUBLISHABLE_TEMPORAL = {TemporalCategory.RETROSPECTIVE, TemporalCategory.PREDICTIVE}


@dataclass
class ClassificationResult:
    """Result from LLM classification"""
    title: str
    is_news: bool              # True if this is a real breaking news event
    category: NewsCategory     # Classified category
    is_significant: bool       # True if internationally significant
    confidence: float          # 0.0-1.0 confidence score
    reason: str               # Brief explanation
    raw_response: dict | None = None  # Raw LLM response for debugging
    # Phase 6: Temporal classification fields
    temporal_category: TemporalCategory = TemporalCategory.BREAKING
    temporal_markers_found: list[str] = field(default_factory=list)


@dataclass
class BatchClassificationResult:
    """Result from batch classification"""
    results: list[ClassificationResult]
    total_articles: int
    passed_count: int
    rejected_count: int
    processing_time_seconds: float
    llm_tokens_used: int | None = None


# Classification prompt template with temporal classification
# Phase 6: Enhanced with current date context and temporal linguistic markers
CLASSIFICATION_PROMPT = """You are a breaking international news classifier for a real-time geopolitical events map.
Today's date: {current_date}

For each article, determine:

1. TEMPORAL_CATEGORY (Critical for filtering):

   BREAKING (Publish: YES)
   - Events happening within the last 24 hours
   - Markers: "just", "breaking", "happening now", "moments ago", present tense
   - Example: "Russia launches new offensive in Ukraine border region"

   DEVELOPING (Publish: YES)
   - Ongoing events with new updates (1-7 days)
   - Markers: "latest update", "developing story", "as situation unfolds", "Day N of"
   - Example: "Day 5 of peace talks: New proposals emerge"

   RETROSPECTIVE (Publish: NO)
   - Analysis, reviews, historical comparisons, anniversaries
   - Markers: "X years later", "looking back", "analysis", "what 20XX taught us", "in hindsight", "lessons learned"
   - Example: "Three years into the conflict: A comprehensive analysis"

   PREDICTIVE (Publish: NO)
   - Future speculation, forecasts, predictions
   - Markers: "could", "may", "will likely", "expected to", "experts predict", "forecast", "outlook"
   - Example: "What the 2027 election could mean for foreign policy"

   TIMELESS (Publish: EVALUATE)
   - Encyclopedic, educational content without news value
   - Example: "How international sanctions work: An explainer"

2. IS_NEWS: Is this a REAL breaking news event?
   - TRUE: Actual events (attacks, elections, protests, diplomatic meetings, military actions)
   - FALSE: Entertainment, opinion pieces, retrospectives, predictions, lifestyle

3. CATEGORY (if IS_NEWS is true):
   - war: Active warfare, invasions, airstrikes, military operations
   - conflict: Armed clashes, border tensions, ceasefires, hostilities
   - politics: Elections, government changes, sanctions, legislation
   - security: Cyber attacks, nuclear issues, espionage, threats
   - military: Troop deployments, defense announcements, weapons
   - terrorism: Terror attacks, extremist activities, hostage situations
   - diplomacy: Treaties, negotiations, summits, international agreements
   - protest: Demonstrations, riots, civil unrest, strikes
   - other: Does not fit above categories

4. IS_SIGNIFICANT: Is this event internationally significant?
   - TRUE: Major world events, affects multiple countries, high casualties/impact
   - FALSE: Local incidents, minor events, limited international relevance

CRITICAL FILTERS:
- If article mentions years like "2024", "2023" extensively → likely RETROSPECTIVE
- If article title contains "analysis", "review", "lessons", "in hindsight" → RETROSPECTIVE
- If article uses future tense ("could", "may", "will") throughout → PREDICTIVE
- Anniversary articles ("X years since...", "marking X years") → RETROSPECTIVE
- Year-end reviews ("2024 in review", "year of...") → RETROSPECTIVE

Respond with a JSON array. Each object must have exactly these fields:
{{"index": <number>, "temporal_category": "<breaking|developing|retrospective|predictive|timeless>", "is_news": <bool>, "category": "<string>", "is_significant": <bool>, "temporal_markers_found": ["marker1", "marker2"], "reason": "<brief explanation>"}}

IMPORTANT:
- temporal_category is REQUIRED for all articles
- RETROSPECTIVE and PREDICTIVE articles should have is_news=false
- Be strict about filtering non-news content
- Respond ONLY with valid JSON array, no other text

Articles to classify:
{articles}"""


class LLMClassifier:
    """
    LLM-based news classifier using Deepinfra API.

    Replaces pattern-based filtering with a single LLM call per batch.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        batch_size: int | None = None,
        timeout: float | None = None,
    ):
        """
        Initialize LLM classifier.

        Args:
            api_key: Deepinfra API key (defaults to config)
            base_url: API base URL (defaults to config)
            model: Model to use (defaults to config)
            batch_size: Articles per batch (defaults to config)
            timeout: Request timeout in seconds (defaults to config)
        """
        self.api_key = api_key or agent_settings.deepinfra_api_key
        self.base_url = base_url or agent_settings.deepinfra_base_url
        self.model = model or agent_settings.llm_classifier_model
        self.batch_size = batch_size or agent_settings.llm_classifier_batch_size
        self.timeout = timeout or agent_settings.llm_classifier_timeout

        # Track usage
        self._total_requests = 0
        self._total_tokens = 0
        self._last_request_time: datetime | None = None

    @property
    def is_enabled(self) -> bool:
        """Check if LLM classifier is properly configured and enabled."""
        return bool(self.api_key) and agent_settings.llm_classifier_enabled

    async def classify_batch(
        self,
        articles: list[dict],
    ) -> BatchClassificationResult:
        """
        Classify a batch of articles using LLM.

        Args:
            articles: List of article dicts with 'title' and optionally 'content'

        Returns:
            BatchClassificationResult with classification results
        """
        start_time = datetime.utcnow()

        if not articles:
            return BatchClassificationResult(
                results=[],
                total_articles=0,
                passed_count=0,
                rejected_count=0,
                processing_time_seconds=0.0,
            )

        # Process in batches
        all_results: list[ClassificationResult] = []
        total_tokens = 0

        for i in range(0, len(articles), self.batch_size):
            batch = articles[i:i + self.batch_size]

            try:
                batch_results, tokens = await self._classify_single_batch(batch)
                all_results.extend(batch_results)
                total_tokens += tokens or 0

            except Exception as e:
                logger.error(f"[LLM-CLASSIFIER] Batch classification error: {e}")
                # On error, use fallback (reject all in batch)
                if agent_settings.llm_classifier_fallback_enabled:
                    fallback_results = self._fallback_classify(batch)
                    all_results.extend(fallback_results)
                else:
                    raise

        # Calculate stats
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        passed_count = sum(1 for r in all_results if r.is_news and r.is_significant)
        rejected_count = len(all_results) - passed_count

        logger.info(
            f"[LLM-CLASSIFIER] Processed {len(articles)} articles in {processing_time:.2f}s | "
            f"Passed: {passed_count}, Rejected: {rejected_count}"
        )

        return BatchClassificationResult(
            results=all_results,
            total_articles=len(articles),
            passed_count=passed_count,
            rejected_count=rejected_count,
            processing_time_seconds=processing_time,
            llm_tokens_used=total_tokens if total_tokens > 0 else None,
        )

    async def _classify_single_batch(
        self,
        articles: list[dict],
    ) -> tuple[list[ClassificationResult], int | None]:
        """
        Classify a single batch of articles.

        Returns:
            Tuple of (results, tokens_used)
        """
        if not self.api_key:
            logger.warning("[LLM-CLASSIFIER] No API key configured, using fallback")
            return self._fallback_classify(articles), None

        # Format articles for prompt
        article_lines = []
        for i, article in enumerate(articles):
            title = article.get("title", "")[:200]  # Limit title length
            article_lines.append(f"{i}. {title}")

        articles_text = "\n".join(article_lines)

        # Phase 6: Include current date for temporal context
        current_date = datetime.utcnow().strftime("%Y-%m-%d")
        prompt = CLASSIFICATION_PROMPT.format(
            current_date=current_date,
            articles=articles_text
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.1,  # Low temperature for consistent results
                        "max_tokens": 2000,
                    },
                )

                if response.status_code != 200:
                    logger.error(
                        f"[LLM-CLASSIFIER] API error {response.status_code}: {response.text[:200]}"
                    )
                    return self._fallback_classify(articles), None

                data = response.json()
                self._total_requests += 1
                self._last_request_time = datetime.utcnow()

                # Extract token usage
                tokens_used = data.get("usage", {}).get("total_tokens", 0)
                self._total_tokens += tokens_used

                # Parse response
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                results = self._parse_llm_response(content, articles)

                return results, tokens_used

        except httpx.TimeoutException:
            logger.warning("[LLM-CLASSIFIER] Request timeout, using fallback")
            return self._fallback_classify(articles), None

        except Exception as e:
            logger.error(f"[LLM-CLASSIFIER] Request error: {e}")
            return self._fallback_classify(articles), None

    def _parse_llm_response(
        self,
        content: str,
        articles: list[dict],
    ) -> list[ClassificationResult]:
        """
        Parse LLM response JSON into ClassificationResult objects.
        """
        results: list[ClassificationResult] = []

        try:
            # Clean up response (sometimes LLM adds markdown)
            content = content.strip()
            if content.startswith("```"):
                # Remove markdown code blocks
                lines = content.split("\n")
                content = "\n".join(
                    line for line in lines
                    if not line.startswith("```")
                )

            # Parse JSON array
            parsed = json.loads(content)

            if not isinstance(parsed, list):
                logger.warning("[LLM-CLASSIFIER] Response is not a JSON array")
                return self._fallback_classify(articles)

            # Map results by index
            result_map = {item.get("index", i): item for i, item in enumerate(parsed)}

            for i, article in enumerate(articles):
                title = article.get("title", "")
                item = result_map.get(i, {})

                # Parse category
                category_str = item.get("category", "other").lower()
                try:
                    category = NewsCategory(category_str)
                except ValueError:
                    category = NewsCategory.OTHER

                # Phase 6: Parse temporal category
                temporal_str = item.get("temporal_category", "breaking").lower()
                try:
                    temporal_category = TemporalCategory(temporal_str)
                except ValueError:
                    temporal_category = TemporalCategory.BREAKING

                # Parse temporal markers found
                temporal_markers = item.get("temporal_markers_found", [])
                if not isinstance(temporal_markers, list):
                    temporal_markers = []

                # Phase 6: Auto-reject RETROSPECTIVE and PREDICTIVE
                is_news = bool(item.get("is_news", False))
                is_significant = bool(item.get("is_significant", False))

                if temporal_category in NON_PUBLISHABLE_TEMPORAL:
                    is_news = False
                    is_significant = False
                    logger.info(
                        f"[LLM-CLASSIFIER] Temporal filter REJECT ({temporal_category.value}): "
                        f"{title[:60]}... | markers: {temporal_markers}"
                    )

                results.append(ClassificationResult(
                    title=title,
                    is_news=is_news,
                    category=category,
                    is_significant=is_significant,
                    confidence=0.85 if item else 0.5,  # Lower confidence if no match
                    reason=item.get("reason", "No classification returned"),
                    raw_response=item,
                    temporal_category=temporal_category,
                    temporal_markers_found=temporal_markers,
                ))

        except json.JSONDecodeError as e:
            logger.error(f"[LLM-CLASSIFIER] JSON parse error: {e}")
            logger.debug(f"[LLM-CLASSIFIER] Raw content: {content[:500]}")
            return self._fallback_classify(articles)

        return results

    def _fallback_classify(
        self,
        articles: list[dict],
    ) -> list[ClassificationResult]:
        """
        Fallback classification when LLM is unavailable.

        Uses simple keyword matching (conservative - passes most articles).
        Phase 6: Added temporal classification with keyword-based detection.
        """
        results: list[ClassificationResult] = []

        # Simple keyword sets for fallback
        news_keywords = {
            "war", "attack", "killed", "bombing", "military", "troops",
            "election", "president", "government", "protest", "sanctions",
            "nuclear", "terrorist", "hostage", "ceasefire", "summit",
        }

        non_news_keywords = {
            "movie", "film", "celebrity", "actor", "actress", "sports",
            "recipe", "fashion", "lifestyle", "review", "opinion",
            "how to", "tips", "ranked", "best", "top 10",
        }

        # Phase 6: Temporal markers for fallback classification
        retrospective_keywords = {
            "years later", "looking back", "anniversary", "in retrospect",
            "lessons learned", "what we learned", "commemorat", "years since",
            "in hindsight", "year in review", "in review", "years ago",
        }

        predictive_keywords = {
            "could mean", "may lead", "will likely", "expected to",
            "experts predict", "forecast", "outlook", "upcoming",
            "analysts say", "projections",
        }

        breaking_keywords = {
            "breaking", "just in", "happening now", "developing",
            "live update", "unfolding",
        }

        for article in articles:
            title = article.get("title", "").lower()
            temporal_markers_found = []

            # Phase 6: Detect temporal category
            temporal_category = TemporalCategory.BREAKING  # Default

            # Check retrospective
            retro_matches = [kw for kw in retrospective_keywords if kw in title]
            if retro_matches:
                temporal_category = TemporalCategory.RETROSPECTIVE
                temporal_markers_found = retro_matches[:3]

            # Check predictive (only if not already retrospective)
            elif any(kw in title for kw in predictive_keywords):
                pred_matches = [kw for kw in predictive_keywords if kw in title]
                temporal_category = TemporalCategory.PREDICTIVE
                temporal_markers_found = pred_matches[:3]

            # Check breaking
            elif any(kw in title for kw in breaking_keywords):
                break_matches = [kw for kw in breaking_keywords if kw in title]
                temporal_category = TemporalCategory.BREAKING
                temporal_markers_found = break_matches[:3]

            # Check for non-news indicators
            is_non_news = any(kw in title for kw in non_news_keywords)

            # Check for news indicators
            has_news_keywords = any(kw in title for kw in news_keywords)

            # Phase 6: Auto-reject retrospective/predictive
            if temporal_category in NON_PUBLISHABLE_TEMPORAL:
                results.append(ClassificationResult(
                    title=article.get("title", ""),
                    is_news=False,
                    category=NewsCategory.OTHER,
                    is_significant=False,
                    confidence=0.6,
                    reason=f"Fallback: {temporal_category.value} detected",
                    temporal_category=temporal_category,
                    temporal_markers_found=temporal_markers_found,
                ))
                logger.info(
                    f"[LLM-CLASSIFIER] Fallback temporal REJECT ({temporal_category.value}): "
                    f"{article.get('title', '')[:60]}..."
                )
            elif is_non_news:
                results.append(ClassificationResult(
                    title=article.get("title", ""),
                    is_news=False,
                    category=NewsCategory.OTHER,
                    is_significant=False,
                    confidence=0.6,
                    reason="Fallback: Non-news keywords detected",
                    temporal_category=temporal_category,
                    temporal_markers_found=temporal_markers_found,
                ))
            elif has_news_keywords:
                # Guess category from keywords
                category = NewsCategory.OTHER
                if any(kw in title for kw in ["war", "attack", "bombing", "airstrike"]):
                    category = NewsCategory.WAR
                elif any(kw in title for kw in ["military", "troops", "army"]):
                    category = NewsCategory.MILITARY
                elif any(kw in title for kw in ["election", "president", "government"]):
                    category = NewsCategory.POLITICS
                elif any(kw in title for kw in ["protest", "demonstration", "riot"]):
                    category = NewsCategory.PROTEST

                results.append(ClassificationResult(
                    title=article.get("title", ""),
                    is_news=True,
                    category=category,
                    is_significant=True,  # Conservative - assume significant
                    confidence=0.5,
                    reason="Fallback: News keywords detected",
                    temporal_category=temporal_category,
                    temporal_markers_found=temporal_markers_found,
                ))
            else:
                # Unknown - pass through (conservative)
                # Preserve temporal_category if it was set by breaking_keywords detection
                final_temporal = temporal_category if temporal_markers_found else TemporalCategory.TIMELESS
                results.append(ClassificationResult(
                    title=article.get("title", ""),
                    is_news=True,
                    category=NewsCategory.OTHER,
                    is_significant=True,
                    confidence=0.3,
                    reason="Fallback: Unable to classify",
                    temporal_category=final_temporal,
                    temporal_markers_found=temporal_markers_found,
                ))

        return results

    def get_usage_stats(self) -> dict:
        """Get usage statistics."""
        return {
            "total_requests": self._total_requests,
            "total_tokens": self._total_tokens,
            "last_request_time": self._last_request_time.isoformat() if self._last_request_time else None,
            "model": self.model,
            "is_enabled": self.is_enabled,
        }


# Global classifier instance
_global_classifier: LLMClassifier | None = None


def get_llm_classifier() -> LLMClassifier:
    """Get or create global LLM classifier instance."""
    global _global_classifier
    if _global_classifier is None:
        _global_classifier = LLMClassifier()
    return _global_classifier


async def classify_articles(
    articles: list[dict],
) -> BatchClassificationResult:
    """
    Convenience function to classify articles using global classifier.

    Args:
        articles: List of article dicts with 'title' key

    Returns:
        BatchClassificationResult
    """
    classifier = get_llm_classifier()
    return await classifier.classify_batch(articles)


def filter_by_classification(
    results: list[ClassificationResult],
    require_significant: bool = True,
    filter_temporal: bool = True,
) -> list[ClassificationResult]:
    """
    Filter classification results to only include publishable articles.

    Args:
        results: Classification results
        require_significant: If True, only include significant news
        filter_temporal: If True, reject RETROSPECTIVE and PREDICTIVE (Phase 6)

    Returns:
        Filtered list of results that passed classification
    """
    filtered = []
    for result in results:
        # Phase 6: Filter by temporal category
        if filter_temporal and result.temporal_category in NON_PUBLISHABLE_TEMPORAL:
            logger.debug(
                f"[LLM-FILTER] Rejected (temporal={result.temporal_category.value}): "
                f"{result.title[:50]}..."
            )
            continue

        if not result.is_news:
            logger.debug(f"[LLM-FILTER] Rejected (not news): {result.title[:50]}...")
            continue

        if require_significant and not result.is_significant:
            logger.debug(f"[LLM-FILTER] Rejected (not significant): {result.title[:50]}...")
            continue

        if result.category == NewsCategory.OTHER:
            logger.debug(f"[LLM-FILTER] Rejected (other category): {result.title[:50]}...")
            continue

        filtered.append(result)

    return filtered
