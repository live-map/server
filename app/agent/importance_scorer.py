"""
Importance Scorer based on GDELT Goldstein Scale and ACLED methodology.

This module provides a multi-dimensional importance scoring system for news events,
combining:
1. Event Type Score (Goldstein Scale) - Conflict intensity
2. Actor Significance - G7, UN, NATO, major powers
3. Geographic Scope - Local vs. International
4. Casualty Scale - Human impact
5. Source Coverage - Multi-outlet reporting
6. Escalation Potential - Risk of expansion

Score Range: 0.0 - 1.0
- 0.00-0.29: Low importance
- 0.30-0.49: Medium importance
- 0.50-0.69: High importance
- 0.70-1.00: Critical importance

Reference:
- GDELT Goldstein Scale: https://www.gdeltproject.org/data/lookups/CAMEO.goldsteinscale.txt
- ACLED Methodology: https://acleddata.com/methodology/
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ImportanceLevel(str, Enum):
    """Importance level classification."""
    CRITICAL = "critical"   # 0.70-1.00
    HIGH = "high"           # 0.50-0.69
    MEDIUM = "medium"       # 0.30-0.49
    LOW = "low"             # 0.00-0.29


# =============================================================================
# GOLDSTEIN SCALE - Event Type Scoring
# =============================================================================
# Goldstein Scale ranges from -10 (most conflictual) to +10 (most cooperative)
# We normalize and invert for news importance (conflict = high importance)

# Event patterns mapped to Goldstein-like scores (-10 to +10)
# Lower scores = more conflictual = higher importance
EVENT_TYPE_SCORES: dict[str, float] = {
    # Extreme conflict (-10 to -8) -> Importance 1.0
    "nuclear strike": -10.0,
    "nuclear attack": -10.0,
    "chemical weapon": -9.5,
    "biological weapon": -9.5,
    "genocide": -9.5,
    "ethnic cleansing": -9.0,
    "massacre": -9.0,
    "mass killing": -8.5,
    "declaration of war": -8.5,
    "ground invasion": -8.0,
    "full-scale invasion": -8.0,

    # High conflict (-8 to -5) -> Importance 0.8-0.9
    "airstrike": -7.5,
    "airstrikes": -7.5,
    "air strike": -7.5,
    "missile strike": -7.0,
    "missile attack": -7.0,
    "bombing raid": -7.0,
    "carpet bombing": -7.5,
    "terror attack": -7.5,
    "terrorist attack": -7.5,
    "suicide bombing": -7.0,
    "car bomb": -6.5,
    "mass shooting": -7.0,
    "mass casualty": -6.5,
    "artillery shelling": -6.0,
    "artillery strike": -6.0,
    "drone strike": -5.5,
    "naval blockade": -5.0,

    # Moderate conflict (-5 to -2) -> Importance 0.5-0.7
    "armed clash": -4.5,
    "armed conflict": -4.5,
    "military offensive": -4.0,
    "military operation": -3.5,
    "ceasefire violation": -4.0,
    "ceasefire broken": -4.5,
    "hostage situation": -4.0,
    "kidnapping": -3.5,
    "violent riot": -3.5,
    "violent protest": -3.0,
    "martial law": -3.5,
    "state of emergency": -3.0,
    "coup attempt": -5.0,
    "coup": -5.5,
    "assassination": -5.0,
    "assassination attempt": -4.5,
    "explosion": -3.0,
    "shooting": -3.0,

    # Low conflict (-2 to 0) -> Importance 0.3-0.5
    "mass protest": -2.0,
    "protest": -1.5,
    "demonstration": -1.0,
    "riot": -2.0,
    "clashes": -2.5,
    "military exercise": -1.0,
    "military drill": -0.5,
    "sanctions imposed": -2.0,
    "diplomatic expulsion": -1.5,
    "embassy closure": -1.5,

    # Neutral (0) -> Importance ~0.25
    "troops deployed": 0.0,
    "military convoy": 0.0,
    "warship": -0.5,
    "fighter jet": -0.5,

    # Cooperative (+1 to +5) -> Lower importance
    "ceasefire": 2.0,
    "peace talks": 3.0,
    "peace agreement": 4.0,
    "humanitarian aid": 3.5,
    "prisoner exchange": 2.5,
    "diplomatic talks": 2.0,
}

# Compile patterns for efficient matching
_EVENT_PATTERNS = {
    pattern: score
    for pattern, score in sorted(
        EVENT_TYPE_SCORES.items(),
        key=lambda x: len(x[0]),
        reverse=True  # Longer patterns first for better matching
    )
}


def _normalize_goldstein_to_importance(goldstein_score: float) -> float:
    """
    Convert Goldstein score (-10 to +10) to importance (0 to 1).

    More negative (conflictual) = higher importance.
    """
    # Clamp to valid range
    goldstein_score = max(-10, min(10, goldstein_score))

    # Invert and normalize: -10 -> 1.0, +10 -> 0.0
    importance = (10 - goldstein_score) / 20

    return importance


def calculate_event_type_score(text: str) -> tuple[float, str | None]:
    """
    Calculate event type score based on Goldstein Scale.

    Args:
        text: Event title and content

    Returns:
        Tuple of (importance_score, matched_pattern)
    """
    text_lower = text.lower()

    # Find the most conflictual pattern match
    best_score = 0.0  # Neutral Goldstein
    best_pattern = None

    for pattern, goldstein_score in _EVENT_PATTERNS.items():
        if pattern in text_lower:
            # Use word boundary for single words, substring for phrases
            if " " in pattern:
                # Phrase - substring match is OK
                if goldstein_score < best_score or best_pattern is None:
                    best_score = goldstein_score
                    best_pattern = pattern
            else:
                # Single word - check word boundary
                regex = rf'\b{re.escape(pattern)}\b'
                if re.search(regex, text_lower):
                    if goldstein_score < best_score or best_pattern is None:
                        best_score = goldstein_score
                        best_pattern = pattern

    importance = _normalize_goldstein_to_importance(best_score)

    return importance, best_pattern


# =============================================================================
# ACTOR SIGNIFICANCE - Major powers and organizations
# =============================================================================

# Actor categories with significance weights
ACTOR_SIGNIFICANCE: dict[str, float] = {
    # UN Security Council P5 (highest significance)
    "united states": 1.0,
    "u.s.": 1.0,
    "us military": 1.0,
    "pentagon": 1.0,
    "russia": 1.0,
    "russian": 0.9,
    "kremlin": 1.0,
    "china": 1.0,
    "chinese": 0.9,
    "beijing": 0.9,
    "france": 0.85,
    "french": 0.8,
    "united kingdom": 0.85,
    "uk": 0.8,
    "british": 0.8,

    # Major international organizations
    "united nations": 0.95,
    "un security council": 1.0,
    "nato": 0.95,
    "european union": 0.85,
    "eu": 0.8,
    "world health organization": 0.75,
    "who": 0.7,
    "international criminal court": 0.8,
    "icc": 0.75,

    # G7 countries
    "germany": 0.8,
    "german": 0.75,
    "japan": 0.8,
    "japanese": 0.75,
    "italy": 0.7,
    "italian": 0.65,
    "canada": 0.7,
    "canadian": 0.65,

    # Regional powers
    "india": 0.75,
    "indian": 0.7,
    "brazil": 0.65,
    "turkey": 0.7,
    "turkish": 0.65,
    "iran": 0.8,
    "iranian": 0.75,
    "israel": 0.85,
    "israeli": 0.8,
    "saudi arabia": 0.75,
    "saudi": 0.7,
    "egypt": 0.65,
    "egyptian": 0.6,
    "pakistan": 0.7,
    "north korea": 0.85,
    "south korea": 0.7,
    "ukraine": 0.8,
    "ukrainian": 0.75,

    # Non-state actors (high impact)
    "hamas": 0.8,
    "hezbollah": 0.75,
    "isis": 0.85,
    "islamic state": 0.85,
    "al-qaeda": 0.8,
    "taliban": 0.75,
    "houthi": 0.7,
    "wagner": 0.7,
}


def calculate_actor_significance(text: str) -> tuple[float, list[str]]:
    """
    Calculate actor significance score.

    Args:
        text: Event title and content

    Returns:
        Tuple of (max_significance, list of matched actors)
    """
    text_lower = text.lower()
    matched_actors = []
    max_significance = 0.0

    for actor, significance in ACTOR_SIGNIFICANCE.items():
        if actor in text_lower:
            matched_actors.append(actor)
            max_significance = max(max_significance, significance)

    return max_significance, matched_actors


# =============================================================================
# GEOGRAPHIC SCOPE - Local vs. International
# =============================================================================

# Patterns indicating international scope
INTERNATIONAL_PATTERNS = {
    # Multi-country references
    r'\bmultiple countries\b': 1.0,
    r'\bglobal\b': 0.9,
    r'\bworldwide\b': 0.9,
    r'\binternational\b': 0.85,
    r'\bregional\b': 0.7,
    r'\bcross-border\b': 0.8,
    r'\bborder crossing\b': 0.7,

    # International waterways/airspace
    r'\binternational waters\b': 0.8,
    r'\binternational airspace\b': 0.8,

    # Diplomatic language
    r'\bforeign minister\b': 0.7,
    r'\bambassador\b': 0.65,
    r'\bembassy\b': 0.6,
    r'\bconsulate\b': 0.55,

    # Treaties/agreements
    r'\btreaty\b': 0.7,
    r'\baccord\b': 0.65,
    r'\bsummit\b': 0.6,
}

# Patterns indicating local scope
LOCAL_PATTERNS = {
    r'\blocal\b': -0.3,
    r'\bneighborhood\b': -0.4,
    r'\btown\b': -0.2,
    r'\bvillage\b': -0.3,
    r'\bcounty\b': -0.2,
    r'\bdistrict\b': -0.2,
}


def calculate_geographic_scope(text: str) -> float:
    """
    Calculate geographic scope score (0 = local, 1 = international).

    Args:
        text: Event title and content

    Returns:
        Geographic scope score (0.0 to 1.0)
    """
    text_lower = text.lower()
    score = 0.5  # Default to moderate scope

    # Check international patterns
    for pattern, weight in INTERNATIONAL_PATTERNS.items():
        if re.search(pattern, text_lower):
            score = max(score, weight)

    # Check local patterns (reduce score)
    for pattern, penalty in LOCAL_PATTERNS.items():
        if re.search(pattern, text_lower):
            score += penalty

    # Count unique country mentions for bonus
    country_count = _count_country_mentions(text_lower)
    if country_count >= 3:
        score = max(score, 0.85)
    elif country_count >= 2:
        score = max(score, 0.7)

    return max(0.0, min(1.0, score))


def _count_country_mentions(text: str) -> int:
    """Count unique countries mentioned in text."""
    countries = {
        "united states", "russia", "china", "france", "germany",
        "uk", "japan", "india", "brazil", "iran", "israel",
        "ukraine", "syria", "iraq", "afghanistan", "pakistan",
        "north korea", "south korea", "taiwan", "saudi arabia",
        "egypt", "turkey", "poland", "italy", "spain", "australia",
    }

    count = 0
    for country in countries:
        if country in text:
            count += 1

    return count


# =============================================================================
# CASUALTY SCALE - Human impact
# =============================================================================

# Casualty patterns with scale multipliers
CASUALTY_PATTERNS = [
    # Exact numbers (prioritize these)
    (r'(\d+)\s*(?:people\s+)?killed', lambda m: _scale_casualties(int(m.group(1)))),
    (r'(\d+)\s*(?:people\s+)?dead', lambda m: _scale_casualties(int(m.group(1)))),
    (r'death toll[:\s]+(\d+)', lambda m: _scale_casualties(int(m.group(1)))),
    (r'(\d+)\s*casualties', lambda m: _scale_casualties(int(m.group(1)) * 0.5)),
    (r'(\d+)\s*wounded', lambda m: _scale_casualties(int(m.group(1)) * 0.3)),
    (r'(\d+)\s*injured', lambda m: _scale_casualties(int(m.group(1)) * 0.3)),

    # Qualitative descriptions
    (r'\bmass casualties\b', lambda m: 0.9),
    (r'\bhundreds killed\b', lambda m: 0.85),
    (r'\bdozens killed\b', lambda m: 0.7),
    (r'\bmultiple deaths\b', lambda m: 0.5),
    (r'\bfatalities\b', lambda m: 0.4),
    (r'\bdeadly\b', lambda m: 0.35),
]


def _scale_casualties(count: int) -> float:
    """Convert casualty count to importance score using log scale."""
    if count <= 0:
        return 0.0
    elif count <= 1:
        return 0.3
    elif count <= 5:
        return 0.45
    elif count <= 10:
        return 0.55
    elif count <= 50:
        return 0.7
    elif count <= 100:
        return 0.8
    elif count <= 500:
        return 0.9
    else:
        return 1.0


def calculate_casualty_scale(text: str) -> tuple[float, int | None]:
    """
    Calculate casualty scale score.

    Args:
        text: Event title and content

    Returns:
        Tuple of (casualty_score, estimated_count)
    """
    text_lower = text.lower()
    max_score = 0.0
    estimated_count = None

    for pattern, scorer in CASUALTY_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            try:
                score = scorer(match)
                if score > max_score:
                    max_score = score
                    # Try to extract count if available
                    if match.lastindex and match.group(1).isdigit():
                        estimated_count = int(match.group(1))
            except (ValueError, TypeError):
                pass

    return max_score, estimated_count


# =============================================================================
# SOURCE COVERAGE - Multi-outlet reporting
# =============================================================================


def calculate_source_coverage(sources: list[str]) -> float:
    """
    Calculate source coverage score based on outlet diversity.

    Args:
        sources: List of source domains/names

    Returns:
        Coverage score (0.0 to 1.0)
    """
    if not sources:
        return 0.3  # Single source default

    unique_domains = set()
    tier1_count = 0
    tier2_count = 0

    # Tier-1 wire services
    tier1_domains = {"reuters", "apnews", "afp", "ap."}
    # Tier-2 major outlets
    tier2_domains = {"bbc", "cnn", "nytimes", "guardian", "aljazeera", "dw.", "france24"}

    for source in sources:
        source_lower = source.lower()

        # Extract domain
        domain = source_lower.replace("www.", "").split("/")[0]
        unique_domains.add(domain)

        # Check tier
        if any(t1 in source_lower for t1 in tier1_domains):
            tier1_count += 1
        elif any(t2 in source_lower for t2 in tier2_domains):
            tier2_count += 1

    domain_count = len(unique_domains)

    # Calculate score
    if domain_count >= 5 and tier1_count >= 2:
        return 1.0
    elif domain_count >= 4 and tier1_count >= 1:
        return 0.9
    elif domain_count >= 3:
        return 0.75
    elif domain_count >= 2:
        return 0.55
    elif tier1_count >= 1:
        return 0.5
    elif tier2_count >= 1:
        return 0.4
    else:
        return 0.3


# =============================================================================
# ESCALATION POTENTIAL - Risk of expansion
# =============================================================================

# Patterns indicating escalation risk
ESCALATION_PATTERNS = {
    # High escalation risk
    r'\bthreatens? war\b': 0.95,
    r'\brisk of war\b': 0.9,
    r'\bdeclare war\b': 0.95,
    r'\bnuclear\b': 0.9,
    r'\bwmd\b': 0.85,
    r'\bescalat': 0.8,  # escalate, escalation, escalating
    r'\bretaliat': 0.75,  # retaliate, retaliation
    r'\bprepar(?:e|ing) for war\b': 0.85,
    r'\bmobiliz': 0.75,  # mobilize, mobilization
    r'\bgeneral mobilization\b': 0.9,
    r'\bultimatum\b': 0.7,
    r'\bwar footing\b': 0.8,

    # Medium escalation risk
    r'\btension(?:s)?\b': 0.5,
    r'\bheighten': 0.55,
    r'\bincreas(?:e|ing) military\b': 0.6,
    r'\breinforc': 0.55,  # reinforce, reinforcement
    r'\bdefcon\b': 0.7,
    r'\bhigh alert\b': 0.6,

    # De-escalation (negative indicators)
    r'\bde-escalat': -0.3,
    r'\bceasefire\b': -0.2,
    r'\bpeace\b': -0.1,
    r'\bwithdraw': -0.2,
}


def calculate_escalation_potential(text: str) -> float:
    """
    Calculate escalation potential score.

    Args:
        text: Event title and content

    Returns:
        Escalation score (0.0 to 1.0)
    """
    text_lower = text.lower()
    max_score = 0.3  # Default base

    for pattern, weight in ESCALATION_PATTERNS.items():
        if re.search(pattern, text_lower):
            if weight > 0:
                max_score = max(max_score, weight)
            else:
                # De-escalation reduces score
                max_score += weight

    return max(0.0, min(1.0, max_score))


# =============================================================================
# MAIN IMPORTANCE SCORER
# =============================================================================


@dataclass
class ImportanceResult:
    """Result of importance scoring."""

    # Final score (0.0 to 1.0)
    score: float
    level: ImportanceLevel

    # Component scores
    event_type_score: float
    actor_significance: float
    geographic_scope: float
    casualty_scale: float
    source_coverage: float
    escalation_potential: float

    # Matched patterns/actors
    event_pattern: str | None = None
    matched_actors: list[str] = field(default_factory=list)
    estimated_casualties: int | None = None

    # Weights used
    weights: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "score": round(self.score, 3),
            "level": self.level.value,
            "components": {
                "event_type": round(self.event_type_score, 3),
                "actor_significance": round(self.actor_significance, 3),
                "geographic_scope": round(self.geographic_scope, 3),
                "casualty_scale": round(self.casualty_scale, 3),
                "source_coverage": round(self.source_coverage, 3),
                "escalation_potential": round(self.escalation_potential, 3),
            },
            "matched_event_pattern": self.event_pattern,
            "matched_actors": self.matched_actors[:5],
            "estimated_casualties": self.estimated_casualties,
        }


# Default component weights
DEFAULT_WEIGHTS = {
    "event_type": 0.20,
    "actor_significance": 0.20,
    "geographic_scope": 0.15,
    "casualty_scale": 0.15,
    "source_coverage": 0.15,
    "escalation_potential": 0.15,
}


def calculate_importance(
    title: str,
    content: str = "",
    sources: list[str] | None = None,
    weights: dict[str, float] | None = None,
) -> ImportanceResult:
    """
    Calculate multi-dimensional importance score for a news event.

    Uses GDELT Goldstein Scale and ACLED methodology to assess:
    1. Event type (conflict intensity)
    2. Actor significance (major powers)
    3. Geographic scope (local vs international)
    4. Casualty scale (human impact)
    5. Source coverage (multi-outlet)
    6. Escalation potential (risk)

    Args:
        title: Event title
        content: Event content/body
        sources: List of source domains/names
        weights: Custom component weights (default: equal 0.20/0.15 split)

    Returns:
        ImportanceResult with final score and breakdown
    """
    text = f"{title} {content}"
    weights = weights or DEFAULT_WEIGHTS
    sources = sources or []

    # Calculate component scores
    event_type_score, event_pattern = calculate_event_type_score(text)
    actor_significance, matched_actors = calculate_actor_significance(text)
    geographic_scope = calculate_geographic_scope(text)
    casualty_scale, estimated_casualties = calculate_casualty_scale(text)
    source_coverage = calculate_source_coverage(sources)
    escalation_potential = calculate_escalation_potential(text)

    # Calculate weighted final score
    final_score = (
        event_type_score * weights.get("event_type", 0.20) +
        actor_significance * weights.get("actor_significance", 0.20) +
        geographic_scope * weights.get("geographic_scope", 0.15) +
        casualty_scale * weights.get("casualty_scale", 0.15) +
        source_coverage * weights.get("source_coverage", 0.15) +
        escalation_potential * weights.get("escalation_potential", 0.15)
    )

    # Ensure score is in valid range
    final_score = max(0.0, min(1.0, final_score))

    # Determine level
    if final_score >= 0.70:
        level = ImportanceLevel.CRITICAL
    elif final_score >= 0.50:
        level = ImportanceLevel.HIGH
    elif final_score >= 0.30:
        level = ImportanceLevel.MEDIUM
    else:
        level = ImportanceLevel.LOW

    result = ImportanceResult(
        score=final_score,
        level=level,
        event_type_score=event_type_score,
        actor_significance=actor_significance,
        geographic_scope=geographic_scope,
        casualty_scale=casualty_scale,
        source_coverage=source_coverage,
        escalation_potential=escalation_potential,
        event_pattern=event_pattern,
        matched_actors=matched_actors,
        estimated_casualties=estimated_casualties,
        weights=weights,
    )

    logger.debug(
        f"Importance: {final_score:.2f} [{level.value}] | "
        f"event={event_type_score:.2f} actor={actor_significance:.2f} "
        f"geo={geographic_scope:.2f} casualty={casualty_scale:.2f} "
        f"source={source_coverage:.2f} escalation={escalation_potential:.2f} | "
        f"{title[:50]}..."
    )

    return result


def is_important_event(
    title: str,
    content: str = "",
    sources: list[str] | None = None,
    threshold: float = 0.5,
) -> bool:
    """
    Quick check if event meets importance threshold.

    Args:
        title: Event title
        content: Event content
        sources: Source list
        threshold: Importance threshold (default 0.5 = HIGH)

    Returns:
        True if event meets threshold
    """
    result = calculate_importance(title, content, sources)
    return result.score >= threshold
