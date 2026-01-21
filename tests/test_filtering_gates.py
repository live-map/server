"""
Tests for content filtering gates

Tests:
1. Check-worthiness gate (entertainment, speculation)
2. Specificity gate (date, location, numbers)
3. Evidence sufficiency gate
"""

import pytest

from app.agent.checkworthiness import check_worthiness, RejectionReason
from app.agent.specificity import check_specificity


class TestCheckWorthiness:
    """Tests for check-worthiness gate"""

    def test_sophie_turner_rejected(self):
        """Sophie Turner 기사는 연예 콘텐츠로 거부되어야 함"""
        text = """Sophie Turner recently shared her insights on the liberating
        experience of reaching one's lowest point during an interview,
        emphasizing the personal growth that can emerge from such challenges."""

        result = check_worthiness(text)
        assert not result.is_checkworthy
        assert result.rejection_reason == RejectionReason.ENTERTAINMENT

    def test_celebrity_interview_rejected(self):
        """Celebrity interview should be rejected"""
        text = """The famous actor talks about his new movie premiere
        and reveals details about his relationship with his co-star."""

        result = check_worthiness(text)
        assert not result.is_checkworthy
        assert result.rejection_reason == RejectionReason.ENTERTAINMENT

    def test_speculation_rejected(self):
        """Speculation content should be rejected"""
        text = """Analysts say the situation might escalate as sources suggest
        tensions could potentially increase in the coming weeks."""

        result = check_worthiness(text)
        assert not result.is_checkworthy
        assert result.rejection_reason == RejectionReason.SPECULATION

    def test_breaking_news_accepted(self):
        """Real breaking news should pass"""
        text = """Russian forces launched missile strikes on Kyiv early Monday,
        killing at least 12 people and wounding 35, according to Ukrainian officials."""

        result = check_worthiness(text)
        assert result.is_checkworthy
        assert result.rejection_reason == RejectionReason.NONE

    def test_military_operation_accepted(self):
        """Military operation news should pass"""
        text = """Ukrainian forces conducted a counteroffensive operation in
        the Kherson region, recapturing two villages from Russian control."""

        result = check_worthiness(text)
        assert result.is_checkworthy

    def test_promotional_rejected(self):
        """Promotional content should be rejected"""
        text = """Buy now and get 50% discount! Limited time offer.
        Subscribe to our newsletter for exclusive deals."""

        result = check_worthiness(text)
        assert not result.is_checkworthy
        assert result.rejection_reason == RejectionReason.PROMOTIONAL


class TestSpecificity:
    """Tests for specificity gate"""

    def test_generic_ukraine_rejected(self):
        """일반 배경 기사는 거부되어야 함"""
        text = """Ukraine and Russia have engaged in renewed conflict,
        leading to reported casualties on both sides. The conflict,
        which has been ongoing since 2014, has seen numerous flare-ups."""

        result = check_specificity(text)
        assert not result.is_specific
        assert result.score < 0.4

    def test_vague_background_rejected(self):
        """Vague background article should be rejected"""
        text = """The long-standing conflict in the region has been ongoing
        for decades. Various regions have seen continued fighting throughout
        the nation as border areas remain unstable."""

        result = check_specificity(text)
        assert not result.is_specific
        assert result.details["has_vague_time"]
        assert result.details["has_vague_location"]

    def test_specific_breaking_news_accepted(self):
        """구체적 속보는 통과해야 함"""
        text = """Russian missile strike on Kyiv killed 12 people on January 20, 2026,
        Ukrainian officials confirmed. The attack occurred at 6:45 AM local time
        in the Shevchenkivskyi district."""

        result = check_specificity(text)
        assert result.is_specific
        assert result.has_recent_date
        assert result.has_specific_location
        assert result.has_specific_numbers

    def test_specific_location_accepted(self):
        """Specific location should boost score"""
        text = """Fighting intensified in Bakhmut today as Ukrainian forces
        repelled multiple Russian attacks."""

        result = check_specificity(text)
        assert result.has_specific_location

    def test_specific_numbers_accepted(self):
        """Specific casualty numbers should boost score"""
        text = """At least 45 people killed and 120 wounded in the attack
        according to local officials."""

        result = check_specificity(text)
        assert result.has_specific_numbers

    def test_recent_date_accepted(self):
        """Recent date reference should boost score"""
        text = """The incident occurred yesterday morning when explosions
        were reported across the city."""

        result = check_specificity(text)
        assert result.has_recent_date

    def test_combined_specificity_accepted(self):
        """Article with all specific elements should pass"""
        text = """Hamas attacked Israeli settlements on Monday, killing 45 civilians
        and wounding over 100. The attack on Tel Aviv occurred at 8:30 AM local time."""

        result = check_specificity(text)
        assert result.is_specific
        assert result.score >= 0.4


class TestEdgeCases:
    """Edge case tests"""

    def test_empty_text(self):
        """Empty text should return default results"""
        result_cw = check_worthiness("")
        assert result_cw.is_checkworthy  # No patterns matched

        result_sp = check_specificity("")
        assert not result_sp.is_specific  # Low score

    def test_short_text(self):
        """Short text handling"""
        result = check_worthiness("Breaking news")
        assert result.is_checkworthy

    def test_mixed_content(self):
        """Mixed content with both specific and vague elements"""
        text = """The ongoing conflict in Gaza has intensified today
        with at least 50 casualties reported in Jerusalem."""

        result = check_specificity(text)
        # Should still pass due to specific elements
        assert result.has_specific_location
        assert result.has_specific_numbers


class TestThresholds:
    """Threshold configuration tests"""

    def test_custom_entertainment_threshold(self):
        """Custom entertainment threshold"""
        # This text matches only 1 pattern (actress)
        text = """The actress went to the store."""

        # With threshold 2, should pass (only 1 pattern)
        result = check_worthiness(text, entertainment_threshold=2)
        assert result.is_checkworthy

        # Text with 2 patterns (actress + interview)
        text = """The actress gave an interview."""
        result = check_worthiness(text, entertainment_threshold=2)
        assert not result.is_checkworthy

    def test_custom_specificity_threshold(self):
        """Custom specificity score threshold"""
        # Text with only location (score 0.3)
        text = """Fighting reported in Kyiv."""

        # With threshold 0.3, should pass
        result = check_specificity(text, min_score=0.3)
        assert result.is_specific

        # With higher threshold, should fail
        result = check_specificity(text, min_score=0.5)
        assert not result.is_specific
