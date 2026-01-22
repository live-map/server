"""
Multi-Source Confidence Scorer

Calculates confidence scores based on multi-source cross-verification.
Implements the Two-Source Rule and tier-based weighting.

Score Range: 0.0 - 0.99
- 0.00-0.49: Low (do not publish)
- 0.50-0.69: Medium (review required)
- 0.70-0.84: High (publishable)
- 0.85-0.99: Very High (immediate publish)
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .triggers.base import SourceTier

logger = logging.getLogger(__name__)


# Tier credibility weights
TIER_WEIGHTS: dict[str, float] = {
    SourceTier.TIER1_GOVT.value: 0.99,
    SourceTier.TIER1_NEWS.value: 0.90,
    SourceTier.TIER2_DATA.value: 0.85,
    SourceTier.TIER2_NEWS.value: 0.75,
    SourceTier.TIER3_SOCIAL.value: 0.40,
    SourceTier.TIER3_MSG.value: 0.35,
    SourceTier.TIER3_TREND.value: 0.30,
}


class ConfidenceLevel(str, Enum):
    """Confidence level classification"""
    LOW = "low"           # 0.00-0.49
    MEDIUM = "medium"     # 0.50-0.69
    HIGH = "high"         # 0.70-0.84
    VERY_HIGH = "very_high"  # 0.85-0.99


class PublishRecommendation(str, Enum):
    """Publication recommendation based on confidence"""
    DO_NOT_PUBLISH = "do_not_publish"
    REVIEW_REQUIRED = "review_required"
    PUBLISHABLE = "publishable"
    IMMEDIATE_PUBLISH = "immediate_publish"


@dataclass
class ConfidenceResult:
    """Result of confidence score calculation"""
    score: float
    level: ConfidenceLevel
    recommendation: PublishRecommendation

    # Score components
    source_count: int
    base_score: float
    tier_average: float
    diversity_bonus: float

    # Source details
    sources: list[dict] = field(default_factory=list)
    tier_types: list[str] = field(default_factory=list)

    # Two-Source Rule
    two_source_satisfied: bool = False

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 3),
            "level": self.level.value,
            "recommendation": self.recommendation.value,
            "components": {
                "source_count": self.source_count,
                "base_score": round(self.base_score, 3),
                "tier_average": round(self.tier_average, 3),
                "diversity_bonus": round(self.diversity_bonus, 3),
            },
            "sources": self.sources,
            "tier_types": self.tier_types,
            "two_source_satisfied": self.two_source_satisfied,
        }


class MultiSourceConfidenceScorer:
    """
    Calculates confidence scores based on multi-source verification.

    Implements:
    1. Two-Source Rule (journalism standard)
    2. Tier-based credibility weighting
    3. Source diversity bonus
    """

    # Publication thresholds
    THRESHOLD_VERY_HIGH = 0.85
    THRESHOLD_HIGH = 0.70
    THRESHOLD_MEDIUM = 0.50

    def __init__(
        self,
        tier_weights: dict[str, float] | None = None,
        min_publish_confidence: float = 0.70,
    ):
        self.tier_weights = tier_weights or TIER_WEIGHTS
        self.min_publish_confidence = min_publish_confidence

    def calculate_confidence(
        self,
        sources: list[dict[str, str]],
    ) -> ConfidenceResult:
        """
        Calculate confidence score for a set of sources.

        Args:
            sources: List of source dicts with 'name' and 'tier' keys
                    e.g., [{"name": "GDELT", "tier": "tier1_news"}, ...]

        Returns:
            ConfidenceResult with score and recommendation
        """
        if not sources:
            return ConfidenceResult(
                score=0.0,
                level=ConfidenceLevel.LOW,
                recommendation=PublishRecommendation.DO_NOT_PUBLISH,
                source_count=0,
                base_score=0.0,
                tier_average=0.0,
                diversity_bonus=0.0,
                two_source_satisfied=False,
            )

        # 1. Count unique sources
        unique_sources = list({s["name"]: s for s in sources}.values())
        source_count = len(unique_sources)

        # 2. Calculate base score from source count
        if source_count == 1:
            base_score = 0.50
        elif source_count == 2:
            base_score = 0.70
        else:
            base_score = 0.85

        # 3. Calculate tier weight average
        tier_scores = []
        for source in unique_sources:
            tier = source.get("tier", "tier2_news")
            weight = self.tier_weights.get(tier, 0.50)
            tier_scores.append(weight)

        tier_average = sum(tier_scores) / len(tier_scores) if tier_scores else 0.50

        # 4. Calculate diversity bonus
        tier_types = list(set(
            s.get("tier", "tier2_news").split("_")[0]
            for s in unique_sources
        ))
        diversity_bonus = (len(tier_types) - 1) * 0.03

        # 5. Calculate final score
        final_score = (base_score * 0.5) + (tier_average * 0.5) + diversity_bonus
        final_score = min(final_score, 0.99)

        # 6. Determine level and recommendation
        level = self._determine_level(final_score)
        recommendation = self._determine_recommendation(final_score, unique_sources)

        # 7. Check Two-Source Rule
        two_source_satisfied = self._check_two_source_rule(unique_sources)

        return ConfidenceResult(
            score=final_score,
            level=level,
            recommendation=recommendation,
            source_count=source_count,
            base_score=base_score,
            tier_average=tier_average,
            diversity_bonus=diversity_bonus,
            sources=unique_sources,
            tier_types=tier_types,
            two_source_satisfied=two_source_satisfied,
        )

    def _determine_level(self, score: float) -> ConfidenceLevel:
        """Determine confidence level from score"""
        if score >= self.THRESHOLD_VERY_HIGH:
            return ConfidenceLevel.VERY_HIGH
        elif score >= self.THRESHOLD_HIGH:
            return ConfidenceLevel.HIGH
        elif score >= self.THRESHOLD_MEDIUM:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def _determine_recommendation(
        self,
        score: float,
        sources: list[dict],
    ) -> PublishRecommendation:
        """Determine publication recommendation"""
        # Check for Tier-1 government source (always publishable)
        has_govt_source = any(
            s.get("tier") == SourceTier.TIER1_GOVT.value
            for s in sources
        )
        if has_govt_source:
            return PublishRecommendation.IMMEDIATE_PUBLISH

        # Score-based recommendation
        if score >= self.THRESHOLD_VERY_HIGH:
            return PublishRecommendation.IMMEDIATE_PUBLISH
        elif score >= self.THRESHOLD_HIGH:
            return PublishRecommendation.PUBLISHABLE
        elif score >= self.THRESHOLD_MEDIUM:
            return PublishRecommendation.REVIEW_REQUIRED
        else:
            return PublishRecommendation.DO_NOT_PUBLISH

    def _check_two_source_rule(self, sources: list[dict]) -> bool:
        """
        Check if Two-Source Rule is satisfied.

        The rule is satisfied if:
        1. At least 2 independent sources, OR
        2. Single Tier-1 government source (USGS, NOAA, etc.)
        """
        # Single Tier-1 govt source is sufficient
        if len(sources) == 1:
            tier = sources[0].get("tier", "")
            return tier == SourceTier.TIER1_GOVT.value

        # Two or more independent sources
        return len(sources) >= 2

    def is_publishable(self, sources: list[dict[str, str]]) -> bool:
        """Quick check if sources meet publication threshold"""
        result = self.calculate_confidence(sources)
        return result.score >= self.min_publish_confidence

    def get_required_sources(
        self,
        current_sources: list[dict[str, str]],
        target_confidence: float = 0.70,
    ) -> str:
        """Get recommendation for additional sources needed"""
        result = self.calculate_confidence(current_sources)

        if result.score >= target_confidence:
            return "Sufficient sources for publication"

        gap = target_confidence - result.score

        if gap > 0.20:
            return "Need 2+ additional Tier-1/Tier-2 sources"
        elif gap > 0.10:
            return "Need 1 additional Tier-1 source or 2 Tier-2 sources"
        else:
            return "Need 1 additional source for cross-verification"


# Convenience function
def calculate_confidence(sources: list[dict[str, str]]) -> ConfidenceResult:
    """Calculate confidence score for sources"""
    scorer = MultiSourceConfidenceScorer()
    return scorer.calculate_confidence(sources)
