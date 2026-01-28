"""
Title Matcher for fast title similarity comparison.

Uses SequenceMatcher for quick duplicate detection before expensive
semantic embedding comparisons.

Design:
- Layer 1 of multi-layer deduplication
- Runs BEFORE embedding generation to save compute
- 85%+ similarity = definite duplicate
- 70-85% = potential duplicate (needs semantic verification)
"""

import logging
import re
from difflib import SequenceMatcher
from typing import NamedTuple

logger = logging.getLogger(__name__)


class TitleMatchResult(NamedTuple):
    """Result of title similarity comparison."""
    is_duplicate: bool          # >= DUPLICATE_THRESHOLD
    is_potential: bool          # >= POTENTIAL_THRESHOLD
    similarity: float           # 0.0 - 1.0
    matched_title: str | None   # Title that matched
    reason: str                 # Explanation


class TitleMatcher:
    """
    Fast title similarity matcher using SequenceMatcher.

    Design:
    - Normalizes titles (lowercase, remove punctuation, collapse whitespace)
    - Uses difflib SequenceMatcher for robust string similarity
    - Two-tier thresholds for duplicate vs potential duplicate

    Usage:
        matcher = TitleMatcher()
        result = matcher.find_duplicate(
            "Israel Recovers Hostage Body from Gaza",
            ["Israel recovers last hostage body from Gaza tunnel"]
        )
        if result.is_duplicate:
            print(f"Duplicate found: {result.similarity:.2%} match")
    """

    # Thresholds (can be overridden in __init__)
    DUPLICATE_THRESHOLD = 0.85    # >= 85% = definite duplicate
    POTENTIAL_THRESHOLD = 0.70    # 70-85% = potential duplicate

    def __init__(
        self,
        duplicate_threshold: float = 0.85,
        potential_threshold: float = 0.70,
    ):
        """
        Initialize TitleMatcher.

        Args:
            duplicate_threshold: Similarity >= this = duplicate (skip)
            potential_threshold: Similarity >= this = potential duplicate (verify)
        """
        self.duplicate_threshold = duplicate_threshold
        self.potential_threshold = potential_threshold

    def normalize_title(self, title: str) -> str:
        """
        Normalize title for comparison.

        Steps:
        1. Lowercase
        2. Remove punctuation except hyphens
        3. Collapse whitespace
        4. Strip leading/trailing whitespace

        Args:
            title: Original title

        Returns:
            Normalized title
        """
        if not title:
            return ""

        # Lowercase
        title = title.lower()

        # Remove punctuation (keep hyphens for compound words)
        title = re.sub(r'[^\w\s\-]', '', title)

        # Collapse whitespace
        title = ' '.join(title.split())

        return title.strip()

    def calculate_similarity(self, title1: str, title2: str) -> float:
        """
        Calculate similarity between two titles.

        Uses SequenceMatcher which is robust to:
        - Word order variations
        - Minor additions/deletions
        - Typos

        Args:
            title1: First title
            title2: Second title

        Returns:
            Similarity score (0.0 - 1.0)
        """
        if not title1 or not title2:
            return 0.0

        # Normalize both titles
        t1 = self.normalize_title(title1)
        t2 = self.normalize_title(title2)

        if not t1 or not t2:
            return 0.0

        # Use SequenceMatcher for robust comparison
        return SequenceMatcher(None, t1, t2).ratio()

    def find_duplicate(
        self,
        title: str,
        recent_titles: list[str],
        metadata: list[dict] | None = None,
    ) -> TitleMatchResult:
        """
        Find duplicate among recent titles.

        Args:
            title: Title to check
            recent_titles: List of recent titles to compare against
            metadata: Optional list of dicts with additional info for each title

        Returns:
            TitleMatchResult with match information
        """
        if not title or not recent_titles:
            return TitleMatchResult(
                is_duplicate=False,
                is_potential=False,
                similarity=0.0,
                matched_title=None,
                reason="NO_COMPARISON_DATA",
            )

        best_similarity = 0.0
        best_match_title = None
        best_match_idx = -1

        normalized_input = self.normalize_title(title)

        for idx, recent_title in enumerate(recent_titles):
            similarity = self.calculate_similarity(title, recent_title)

            if similarity > best_similarity:
                best_similarity = similarity
                best_match_title = recent_title
                best_match_idx = idx

        # Determine match type
        is_duplicate = best_similarity >= self.duplicate_threshold
        is_potential = best_similarity >= self.potential_threshold and not is_duplicate

        # Build reason string
        if is_duplicate:
            reason = f"TITLE_DUPLICATE: {best_similarity:.2%} >= {self.duplicate_threshold:.0%}"
        elif is_potential:
            reason = f"TITLE_POTENTIAL: {best_similarity:.2%} >= {self.potential_threshold:.0%}"
        else:
            reason = f"TITLE_NO_MATCH: {best_similarity:.2%} < {self.potential_threshold:.0%}"

        if is_duplicate or is_potential:
            logger.info(
                f"[TITLE-MATCH] {reason} | "
                f"Input: '{title[:50]}...' | "
                f"Match: '{best_match_title[:50] if best_match_title else 'N/A'}...'"
            )

        return TitleMatchResult(
            is_duplicate=is_duplicate,
            is_potential=is_potential,
            similarity=best_similarity,
            matched_title=best_match_title,
            reason=reason,
        )

    def find_all_similar(
        self,
        title: str,
        recent_titles: list[str],
        threshold: float = 0.60,
    ) -> list[tuple[str, float]]:
        """
        Find all titles above a similarity threshold.

        Useful for debugging and threshold tuning.

        Args:
            title: Title to check
            recent_titles: List of recent titles
            threshold: Minimum similarity to include

        Returns:
            List of (title, similarity) tuples, sorted by similarity desc
        """
        results = []

        for recent_title in recent_titles:
            similarity = self.calculate_similarity(title, recent_title)
            if similarity >= threshold:
                results.append((recent_title, similarity))

        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)

        return results


# Module-level instance for convenience
_title_matcher: TitleMatcher | None = None


def get_title_matcher() -> TitleMatcher:
    """Get singleton TitleMatcher instance."""
    global _title_matcher
    if _title_matcher is None:
        from app.agent.config import agent_settings
        _title_matcher = TitleMatcher(
            duplicate_threshold=getattr(agent_settings, 'title_similarity_duplicate', 0.85),
            potential_threshold=getattr(agent_settings, 'title_similarity_potential', 0.70),
        )
    return _title_matcher
