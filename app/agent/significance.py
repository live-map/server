"""
Significance scoring module for news events.

Provides:
1. Deterministic scoring based on keywords, sources, engagement
2. LLM-based classification with structured output
3. Configurable thresholds
4. Detailed logging for debugging
5. Word boundary matching to reduce false positives

This replaces the vague "significant events" criteria with
measurable, tunable parameters.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# =============================================================================
# Keyword Matching Utilities
# =============================================================================

# Context words that indicate non-event usage (defense, prevention, etc.)
NEGATION_CONTEXT_WORDS = frozenset({
    "defense", "defence", "prevention", "prevention of",
    "anti-", "counter-", "against", "prevent", "preventing",
    "avoided", "averted", "stopped", "intercepted",
    "simulation", "exercise", "drill", "training",
    "history", "historical", "anniversary", "memorial",
    "movie", "film", "game", "video game", "book",
})


def match_keyword_with_boundary(keyword: str, text: str) -> bool:
    """
    Match keyword with word boundaries to avoid false positives.

    Args:
        keyword: Keyword to match
        text: Text to search in (should be lowercase)

    Returns:
        True if keyword matches with word boundaries

    Examples:
        - "airstrike" matches "airstrike on city" -> True
        - "airstrike" matches "airstrike defense" -> False (negation context)
        - "war" matches "the war began" -> True
        - "war" matches "warning issued" -> False (no word boundary)
    """
    # Escape special regex characters in keyword
    escaped_kw = re.escape(keyword.strip())

    # Build pattern with word boundaries
    # \b matches word boundary (between \w and \W)
    pattern = rf'\b{escaped_kw}\b'

    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return False

    # Check for negation context in surrounding words (±5 words)
    start_pos = max(0, match.start() - 50)
    end_pos = min(len(text), match.end() + 50)
    context = text[start_pos:end_pos].lower()

    for neg_word in NEGATION_CONTEXT_WORDS:
        if neg_word in context:
            logger.debug(
                f"Keyword '{keyword}' matched but negated by context word '{neg_word}'"
            )
            return False

    return True


def match_any_keyword(keywords: set[str], text: str) -> list[str]:
    """
    Match any keywords from a set with word boundary checking.

    Args:
        keywords: Set of keywords to match
        text: Text to search in

    Returns:
        List of matched keywords
    """
    text_lower = text.lower()
    matched = []

    for kw in keywords:
        if match_keyword_with_boundary(kw, text_lower):
            matched.append(kw)

    return matched


class SignificanceLevel(str, Enum):
    """Event significance levels."""
    CRITICAL = "critical"  # 80-100: Major breaking news
    HIGH = "high"          # 60-79: Important news
    MEDIUM = "medium"      # 40-59: Notable news
    LOW = "low"            # 20-39: Minor news
    NOISE = "noise"        # 0-19: Likely irrelevant


@dataclass
class SignificanceConfig:
    """Configuration for significance scoring."""

    # Thresholds
    min_publish_score: int = 40  # Minimum score to consider for publishing
    min_investigate_score: int = 60  # Minimum score to trigger investigation

    # Keyword weights (v2: 더 구체적인 키워드)
    critical_keywords: set[str] = field(default_factory=lambda: {
        # Active conflict (most specific)
        "airstrike", "airstrikes", "air strike",
        "missile strike", "missile attack", "missile hits",
        "ground invasion", "troops deployed", "troops invade",
        "bombing raid", "carpet bombing",
        "ceasefire broken", "ceasefire violated",
        "declaration of war",
        # Mass casualties
        "massacre", "mass shooting", "mass killing",
        "terrorist attack", "suicide bombing", "car bomb",
        "civilian casualties", "death toll rises",
        # Major incidents
        "nuclear strike", "chemical weapon", "biological weapon",
        # Specific conflicts
        "ukraine war", "gaza conflict", "israel hamas", "russia ukraine",
    })

    high_keywords: set[str] = field(default_factory=lambda: {
        # Military operations
        "military operation", "military offensive",
        "armed conflict", "armed clash",
        "artillery strike", "artillery shelling", "shelling",
        "drone strike", "air raid", "naval blockade",
        # Casualties
        "casualties reported", "killed in attack", "death toll",
        "wounded in", "injured in attack",
        # Major protests
        "mass protest", "violent protest", "violent riot",
        "martial law", "state of emergency declared",
        # Terrorism
        "claimed responsibility", "terror alert", "hostage situation",
        "explosion kills", "bomb explodes",
    })

    medium_keywords: set[str] = field(default_factory=lambda: {
        # Military movements
        "military exercise", "military drill",
        "troops", "soldiers deployed", "warship",
        "fighter jet", "military convoy",
        # Protests (general)
        "protest", "demonstration", "riot",
        "riot police", "tear gas",
        # General conflict
        "explosion", "shooting", "attack on",
        "clashes", "confrontation",
        # Single-word catches (for broader matching)
        "war ", " war", "warfare",  # space to avoid "warning", "ward"
        "military",
        "invasion",
        "strike",
        "bomb",
    })

    # Words that reduce significance (false positives)
    noise_keywords: set[str] = field(default_factory=lambda: {
        # Animal attacks
        "animal attack", "dog attack", "shark attack", "bear attack",
        "dingo attack", "snake attack", "bee attack",
        # Medical/health
        "heart attack", "panic attack", "asthma attack",
        # Cyber/digital
        "cyber attack", "ddos attack", "ransomware attack",
        # Entertainment
        "movie", "film", "game", "video game", "sport",
        "weather", "forecast",
        # Politics (not actual events)
        "bill introduced", "proposed legislation", "bill passed",
        "denaturalize", "immigration bill",
        # Accidents (not conflicts)
        "car crash", "train crash", "plane crash",
        "factory explosion", "industrial accident",
    })

    # Source credibility multipliers
    high_credibility_sources: set[str] = field(default_factory=lambda: {
        "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk",
        "aljazeera.com", "france24.com", "dw.com",
        "theguardian.com", "nytimes.com", "washingtonpost.com",
    })


class SignificanceScore(BaseModel):
    """Detailed significance score with breakdown."""
    total_score: int
    level: SignificanceLevel
    keyword_score: int
    source_score: int
    engagement_score: int
    recency_score: int
    noise_penalty: int
    matched_keywords: list[str]
    reasoning: str


def calculate_significance(
    title: str,
    content: str = "",
    source_domain: str = "",
    engagement: dict | None = None,
    language: str = "en",
    config: SignificanceConfig | None = None,
) -> SignificanceScore:
    """
    Calculate deterministic significance score for an event.

    Args:
        title: Event title
        content: Event content (optional)
        source_domain: Source domain (e.g., reuters.com)
        engagement: Engagement metrics (likes, retweets, etc.)
        language: Article language code
        config: Scoring configuration

    Returns:
        SignificanceScore with breakdown
    """
    config = config or SignificanceConfig()
    text = f"{title} {content}".lower()
    matched_keywords = []
    reasons = []

    # 1. Keyword scoring (0-60 points) with word boundary matching
    keyword_score = 0

    # Check for noise keywords first (reduce false positives)
    # Noise keywords use simple substring match (they're meant to be broad)
    noise_penalty = 0
    for noise in config.noise_keywords:
        if noise in text:
            noise_penalty += 15
            reasons.append(f"Noise: '{noise}'")

    # Critical keywords (+30 each, max 60) with word boundary matching
    critical_matches = match_any_keyword(config.critical_keywords, text)
    for kw in critical_matches:
        keyword_score += 30
        matched_keywords.append(f"[CRITICAL] {kw}")
    keyword_score = min(keyword_score, 60)

    # High keywords (+15 each, max 45) with word boundary matching
    if keyword_score < 60:
        high_matches = match_any_keyword(config.high_keywords, text)
        for kw in high_matches:
            keyword_score += 15
            matched_keywords.append(f"[HIGH] {kw}")
        keyword_score = min(keyword_score, 60)

    # Medium keywords (+8 each, max 30) with word boundary matching
    if keyword_score < 30:
        medium_matches = match_any_keyword(config.medium_keywords, text)
        for kw in medium_matches:
            keyword_score += 8
            matched_keywords.append(f"[MEDIUM] {kw}")
        keyword_score = min(keyword_score, 30)

    # 2. Source credibility (0-25 points) - increased importance
    source_score = 0
    if source_domain:
        domain = source_domain.lower()
        if any(high in domain for high in config.high_credibility_sources):
            source_score = 25  # High credibility sources get big bonus
            reasons.append(f"Trusted source: {domain}")
        elif any(ext in domain for ext in [".gov", ".mil", ".int"]):
            source_score = 20  # Government/military sources
            reasons.append(f"Official source: {domain}")
        elif "." in domain:
            source_score = 10

    # 3. Engagement score (0-10 points)
    engagement_score = 0
    if engagement:
        total_engagement = sum(engagement.values()) if isinstance(engagement, dict) else 0
        if total_engagement > 10000:
            engagement_score = 10
        elif total_engagement > 1000:
            engagement_score = 5
        elif total_engagement > 100:
            engagement_score = 2

    # 4. Recency score (0-10 points) - placeholder
    recency_score = 5

    # 5. Language bonus (English articles more reliably processed)
    language_bonus = 5 if language and language.lower() in ["en", "english"] else 0

    # 6. GDELT fulltext match bonus
    # If GDELT matched but we didn't find keywords in title,
    # still give some base score since GDELT found it relevant
    gdelt_base_score = 0
    if keyword_score == 0 and source_score >= 20:
        # No keywords in title, but trusted source + GDELT matched
        gdelt_base_score = 15
        reasons.append("GDELT fulltext match + trusted source")

    # Calculate total
    total_score = (
        keyword_score
        + source_score
        + engagement_score
        + recency_score
        + language_bonus
        + gdelt_base_score
        - noise_penalty
    )
    total_score = max(0, min(100, total_score))

    # Determine level
    if total_score >= 80:
        level = SignificanceLevel.CRITICAL
    elif total_score >= 60:
        level = SignificanceLevel.HIGH
    elif total_score >= 40:
        level = SignificanceLevel.MEDIUM
    elif total_score >= 20:
        level = SignificanceLevel.LOW
    else:
        level = SignificanceLevel.NOISE

    # Build reasoning
    if not matched_keywords:
        reasons.append("No significant keywords matched")
    else:
        reasons.append(f"Keywords: {', '.join(matched_keywords[:5])}")

    reasoning = "; ".join(reasons) if reasons else "Standard scoring"

    return SignificanceScore(
        total_score=total_score,
        level=level,
        keyword_score=keyword_score,
        source_score=source_score,
        engagement_score=engagement_score,
        recency_score=recency_score,
        noise_penalty=noise_penalty,
        matched_keywords=matched_keywords,
        reasoning=reasoning,
    )


def filter_significant_events(
    events: list[dict],
    min_score: int = 40,
    config: SignificanceConfig | None = None,
) -> list[tuple[dict, SignificanceScore]]:
    """
    Filter events by significance score.

    Args:
        events: List of event dicts with 'title', 'content', 'source_name'
        min_score: Minimum score to include
        config: Scoring configuration

    Returns:
        List of (event, score) tuples for events meeting threshold
    """
    config = config or SignificanceConfig()
    results = []

    for event in events:
        title = event.get("title", "")
        content = event.get("content", "")
        source = event.get("source_name", event.get("source", ""))
        engagement = event.get("engagement", {})

        score = calculate_significance(
            title=title,
            content=content,
            source_domain=source,
            engagement=engagement,
            config=config,
        )

        # Log all scoring decisions
        logger.debug(
            f"Significance: {score.total_score} [{score.level.value}] - {title[:60]}... "
            f"(kw={score.keyword_score}, src={score.source_score}, "
            f"eng={score.engagement_score}, noise=-{score.noise_penalty})"
        )

        if score.total_score >= min_score:
            results.append((event, score))

    # Sort by score descending
    results.sort(key=lambda x: -x[1].total_score)

    logger.info(
        f"Filtered {len(results)}/{len(events)} events "
        f"(threshold={min_score})"
    )

    return results


# LLM-based classification with structured output
LLM_CLASSIFICATION_PROMPT = """You are a breaking news analyst for international conflicts and security events.

Analyze each event and rate its significance for a news monitoring service focused on:
- Armed conflicts and wars
- Military operations
- Terrorist attacks
- Mass protests and civil unrest
- Major security incidents

For each event, provide:
1. SCORE: 0-100 (not just significant/not - use the full range)
   - 80-100: Critical breaking news (war, major attack, mass casualties)
   - 60-79: Important news (military operations, major protests)
   - 40-59: Notable news (security incidents, regional conflicts)
   - 20-39: Minor news (small protests, minor incidents)
   - 0-19: Not relevant (local crime, animal attacks, political bills, weather)

2. CATEGORY: war | protest | terrorism | military | violence | other
3. REASONING: Brief explanation of the score

IMPORTANT:
- Local crime (robbery, assault) = 0-19
- Animal attacks = 0-19
- Political bills mentioning "terrorist" = 0-19
- Actual military operations = 60+
- Mass casualties = 80+

Events to analyze:
{events}

Respond in this exact format for each event:
EVENT_INDEX: [0-based index]
SCORE: [0-100]
CATEGORY: [category]
REASONING: [brief explanation]
---
"""


async def classify_with_llm(
    events: list[dict],
    llm,
    min_score: int = 40,
) -> list[tuple[dict, int, str, str]]:
    """
    Classify events using LLM with structured scoring.

    Args:
        events: List of event dicts
        llm: LangChain LLM instance
        min_score: Minimum score to include

    Returns:
        List of (event, score, category, reasoning) tuples
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    if not events or not llm:
        return []

    # Format events for prompt
    events_text = "\n".join([
        f"[{i}] [{e.get('source_name', 'unknown')}] {e.get('title', '')}"
        for i, e in enumerate(events[:30])
    ])

    prompt = LLM_CLASSIFICATION_PROMPT.format(events=events_text)

    try:
        response = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content="Analyze these events and provide scores."),
        ])

        # Log full response for debugging
        logger.debug(f"LLM classification response:\n{response.content}")

        return _parse_llm_response(response.content, events, min_score)

    except Exception as e:
        logger.error(f"LLM classification error: {e}")
        return []


def _parse_llm_response(
    response: str,
    events: list[dict],
    min_score: int,
) -> list[tuple[dict, int, str, str]]:
    """Parse structured LLM response."""
    results = []
    current = {}

    for line in response.strip().split("\n"):
        line = line.strip()

        if line.startswith("EVENT_INDEX:"):
            if current and current.get("score", 0) >= min_score:
                idx = current.get("index")
                if idx is not None and 0 <= idx < len(events):
                    results.append((
                        events[idx],
                        current.get("score", 0),
                        current.get("category", "other"),
                        current.get("reasoning", ""),
                    ))
            try:
                current = {"index": int(line.split(":")[1].strip())}
            except (ValueError, IndexError):
                current = {}

        elif line.startswith("SCORE:"):
            try:
                current["score"] = int(line.split(":")[1].strip())
            except (ValueError, IndexError):
                pass

        elif line.startswith("CATEGORY:"):
            current["category"] = line.split(":")[1].strip().lower()

        elif line.startswith("REASONING:"):
            current["reasoning"] = line.split(":", 1)[1].strip()

        elif line == "---":
            if current and current.get("score", 0) >= min_score:
                idx = current.get("index")
                if idx is not None and 0 <= idx < len(events):
                    results.append((
                        events[idx],
                        current.get("score", 0),
                        current.get("category", "other"),
                        current.get("reasoning", ""),
                    ))
            current = {}

    # Handle last entry
    if current and current.get("score", 0) >= min_score:
        idx = current.get("index")
        if idx is not None and 0 <= idx < len(events):
            results.append((
                events[idx],
                current.get("score", 0),
                current.get("category", "other"),
                current.get("reasoning", ""),
            ))

    return results
