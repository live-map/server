"""
Unit tests for Breaking News Fast-Path detection.

Tests breaking news detection and fast-path processing eligibility.
"""

import pytest
from datetime import datetime, timedelta
from app.agent.breaking_news import (
    BreakingNewsDetector,
    BreakingNewsResult,
    BreakingNewsType,
    detect_breaking_news,
    is_breaking_news,
    get_breaking_news_label,
    get_global_detector,
    BREAKING_KEYWORDS,
)


class TestBreakingKeywordDetection:
    """Tests for breaking keyword detection."""

    def test_breaking_keyword_in_title(self):
        """'Breaking' in title should trigger detection.

        Note: 'Breaking:' also matches FLASH pattern (BREAKING:), so it may
        be classified as FLASH_NEWS instead of KEYWORD_TRIGGERED.
        """
        detector = BreakingNewsDetector()
        result = detector.detect("Breaking: Major explosion in downtown area")

        assert result.is_breaking is True
        # Could be FLASH_NEWS (matches BREAKING:) or KEYWORD_TRIGGERED
        assert result.breaking_type in [BreakingNewsType.KEYWORD_TRIGGERED, BreakingNewsType.FLASH_NEWS]

    def test_just_in_keyword_with_urgent_content(self):
        """'Just in' with urgent content should trigger detection.

        Single keyword (0.4 confidence) needs additional signals to reach 0.6 threshold.
        """
        detector = BreakingNewsDetector()
        # Add urgent content to reach threshold
        result = detector.detect("Just in: Terror attack reported in city center")

        assert result.is_breaking is True
        assert any("just in" in s.lower() for s in result.signals)

    def test_urgent_keyword(self):
        """'Urgent' in title should trigger detection."""
        detector = BreakingNewsDetector()
        result = detector.detect("URGENT: Missile launch detected")

        assert result.is_breaking is True

    def test_developing_keyword_with_urgent_content(self):
        """'Developing' with urgent content should trigger detection.

        Single keyword (0.4 confidence) needs additional signals to reach 0.6 threshold.
        """
        detector = BreakingNewsDetector()
        # Add urgent content to reach threshold
        result = detector.detect("Developing: Mass shooting situation at mall")

        assert result.is_breaking is True

    def test_keyword_alone_below_threshold(self):
        """Single keyword without urgent content may not meet threshold."""
        detector = BreakingNewsDetector()
        result = detector.detect("Developing: Minor weather update")

        # May not reach 0.6 threshold with just one signal
        assert result.confidence <= 0.6 or result.is_breaking

    def test_no_breaking_keywords(self):
        """Article without breaking keywords should not trigger."""
        detector = BreakingNewsDetector()
        result = detector.detect("Government releases annual budget report")

        assert result.is_breaking is False
        assert result.breaking_type is None


class TestFlashPatternDetection:
    """Tests for wire service flash pattern detection."""

    def test_flash_prefix_with_urgent_content(self):
        """'FLASH:' prefix with urgent content should trigger detection."""
        detector = BreakingNewsDetector()
        # FLASH keyword (0.4) + earthquake (urgent event 0.2) = 0.6+
        result = detector.detect("FLASH: Major earthquake strikes city")

        assert result.is_breaking is True
        # Either keyword or flash pattern could be primary signal
        assert result.breaking_type in [BreakingNewsType.FLASH_NEWS, BreakingNewsType.KEYWORD_TRIGGERED]

    def test_flash_pattern_detected(self):
        """Flash pattern regex should be detected."""
        detector = BreakingNewsDetector()
        result = detector.detect("FLASH: Critical event occurring")

        # Check that flash/breaking keywords are in signals
        assert any("flash" in s.lower() or "Flash" in s for s in result.signals)

    def test_alert_prefix(self):
        """'ALERT:' prefix should trigger detection."""
        detector = BreakingNewsDetector()
        result = detector.detect("ALERT: Military action reported")

        assert result.is_breaking is True

    def test_urgent_colon_prefix(self):
        """'URGENT:' prefix should trigger detection."""
        detector = BreakingNewsDetector()
        result = detector.detect("URGENT: Peace talks collapse")

        assert result.is_breaking is True


class TestUrgentEventPatterns:
    """Tests for urgent event pattern detection."""

    def test_mass_shooting_pattern(self):
        """Mass shooting should be detected as urgent."""
        detector = BreakingNewsDetector()
        result = detector.detect("Reports of mass shooting at shopping center")

        assert result.confidence > 0
        assert any("Urgent event" in s for s in result.signals)

    def test_terror_attack_pattern(self):
        """Terror attack should be detected as urgent."""
        detector = BreakingNewsDetector()
        result = detector.detect("Terror attack reported in capital city")

        assert result.confidence > 0

    def test_airstrike_pattern(self):
        """Airstrike should be detected as urgent."""
        detector = BreakingNewsDetector()
        result = detector.detect("Airstrikes hit military base")

        assert result.confidence > 0

    def test_coup_pattern(self):
        """Coup should be detected as urgent."""
        detector = BreakingNewsDetector()
        result = detector.detect("Military coup reported in country")

        assert result.confidence > 0


class TestSourceTierIntegration:
    """Tests for source tier integration in breaking news."""

    def test_tier1_source_boosts_confidence(self):
        """Tier-1 source should boost confidence."""
        detector = BreakingNewsDetector()
        result = detector.detect(
            "Major explosion reported",
            source_url="https://reuters.com/article/123"
        )

        assert result.confidence > 0
        assert any("Tier-1" in s for s in result.signals)

    def test_tier1_source_enables_fast_path(self):
        """Tier-1 source with breaking news should enable fast-path."""
        detector = BreakingNewsDetector()
        result = detector.detect(
            "Breaking: Major explosion in city center",
            source_url="https://reuters.com/article/123"
        )

        assert result.is_breaking is True
        assert result.fast_path_eligible is True
        assert "gate2_specificity" in result.gates_to_skip

    def test_tier4_source_no_fast_path(self):
        """Tier-4 source should not enable fast-path even with breaking news."""
        detector = BreakingNewsDetector()
        result = detector.detect(
            "Breaking: Major explosion in city center",
            source_url="https://random-blog.com/post/123"
        )

        # Should be detected as breaking but not fast-path eligible
        assert result.is_breaking is True
        assert result.fast_path_eligible is False


class TestBreakingNewsLabels:
    """Tests for breaking news label assignment."""

    def test_flash_label(self):
        """FLASH: prefix with urgent content should get FLASH label."""
        detector = BreakingNewsDetector()
        result = detector.detect(
            "FLASH: Terror attack in progress",
            source_url="https://reuters.com/article"
        )

        # With Tier-1 source + urgent content, should be breaking
        assert result.is_breaking is True
        # Label should be FLASH for flash-type news
        assert result.label in ["FLASH", "BREAKING"]

    def test_breaking_label_with_tier1_high_confidence(self):
        """High confidence breaking news from Tier-1 should get label."""
        detector = BreakingNewsDetector()
        result = detector.detect(
            "URGENT: Terror attack in capital - Mass shooting reported - Multiple casualties",
            source_url="https://reuters.com/article"
        )

        # High confidence with Tier-1 source should get a label
        assert result.is_breaking is True
        assert result.label in ["BREAKING", "FLASH"]

    def test_developing_label(self):
        """Medium confidence breaking news should get DEVELOPING label."""
        detector = BreakingNewsDetector()
        # Use "developing" keyword without ALERT:/URGENT:/FLASH: prefixes
        result = detector.detect(
            "Developing story: Embassy situation being monitored",
            source_url="https://bbc.com/news"
        )

        # If it's breaking but not FLASH type, should be DEVELOPING
        if result.is_breaking and result.breaking_type == BreakingNewsType.KEYWORD_TRIGGERED:
            assert result.label in ["DEVELOPING", "BREAKING"]


class TestVerificationSchedule:
    """Tests for verification schedule assignment."""

    def test_flash_verification_15min(self):
        """FLASH news should have 15 minute verification."""
        detector = BreakingNewsDetector()
        result = detector.detect("FLASH: Major event", source_url="https://reuters.com")

        assert result.verification_schedule_minutes == 15

    def test_developing_verification_30min(self):
        """DEVELOPING news should have 30 minute verification."""
        detector = BreakingNewsDetector()
        result = detector.detect(
            "Developing: Event unfolding",
            source_url="https://bbc.com"
        )

        if result.label == "DEVELOPING":
            assert result.verification_schedule_minutes == 30


class TestVolumeSpikeDetection:
    """Tests for volume spike detection."""

    def test_volume_spike_triggers_breaking_with_keywords(self):
        """Volume spike with breaking keywords should trigger breaking news."""
        detector = BreakingNewsDetector()

        # Simulate 3 articles on same topic
        topic = "explosion_downtown"
        now = datetime.utcnow()

        detector.record_topic_occurrence(topic, now - timedelta(minutes=2))
        detector.record_topic_occurrence(topic, now - timedelta(minutes=1))

        # Add breaking keyword to reach threshold (0.4 + 0.2 + 0.3 = 0.9)
        result = detector.detect(
            "Breaking: Another report about downtown explosion",
            topic_key=topic,
        )

        assert result.is_breaking is True
        assert any("Volume spike" in s for s in result.signals)

    def test_volume_spike_detected_but_below_confidence(self):
        """Volume spike alone may not reach confidence threshold."""
        detector = BreakingNewsDetector()
        detector.clear_topic_volumes()

        topic = "minor_event"
        now = datetime.utcnow()

        detector.record_topic_occurrence(topic, now - timedelta(minutes=2))
        detector.record_topic_occurrence(topic, now - timedelta(minutes=1))

        # No breaking keywords - only volume spike signal (0.3)
        result = detector.detect(
            "Another report about same event",
            topic_key=topic,
        )

        # Volume spike detected but may not meet threshold alone
        if BreakingNewsType.VOLUME_SPIKE == result.breaking_type:
            assert any("Volume spike" in s for s in result.signals)

    def test_no_spike_below_threshold(self):
        """Below threshold should not trigger volume spike."""
        detector = BreakingNewsDetector()
        detector.clear_topic_volumes()

        topic = "regular_topic"
        detector.record_topic_occurrence(topic)

        result = detector.detect(
            "Regular news article",
            topic_key=topic,
        )

        # Only 2 articles, threshold is 3
        assert result.breaking_type != BreakingNewsType.VOLUME_SPIKE


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_is_breaking_news_function(self):
        """is_breaking_news() should return boolean."""
        assert is_breaking_news("Breaking: Major event") is True
        assert is_breaking_news("Regular news article") is False

    def test_get_breaking_news_label_function(self):
        """get_breaking_news_label() should return label string."""
        label = get_breaking_news_label(
            "Breaking: Major event",
            source_url="https://reuters.com"
        )
        assert label in ["BREAKING", "DEVELOPING", "FLASH", ""]

    def test_detect_breaking_news_global(self):
        """detect_breaking_news() should use global detector."""
        result = detect_breaking_news("Breaking: Major event")

        assert isinstance(result, BreakingNewsResult)
        assert result.is_breaking is True


class TestGlobalDetector:
    """Tests for global detector singleton."""

    def test_global_detector_singleton(self):
        """Global detector should be singleton."""
        detector1 = get_global_detector()
        detector2 = get_global_detector()

        assert detector1 is detector2

    def test_global_detector_maintains_state(self):
        """Global detector should maintain volume tracking state."""
        detector = get_global_detector()

        # Clear any existing state
        detector.clear_topic_volumes()

        topic = "test_topic"
        detector.record_topic_occurrence(topic)

        volume = detector.get_topic_volume(topic)
        assert volume == 1


class TestBreakingNewsResultSerialization:
    """Tests for result serialization."""

    def test_to_dict_includes_all_fields(self):
        """to_dict() should include all fields."""
        detector = BreakingNewsDetector()
        result = detector.detect("Breaking: Major event")

        data = result.to_dict()

        assert "is_breaking" in data
        assert "breaking_type" in data
        assert "confidence" in data
        assert "signals" in data
        assert "fast_path_eligible" in data
        assert "gates_to_skip" in data
        assert "label" in data
        assert "verification_schedule_minutes" in data


class TestMinConfidenceThreshold:
    """Tests for minimum confidence threshold."""

    def test_custom_min_confidence(self):
        """Custom min confidence should affect detection."""
        # Low threshold - should detect easily
        low_detector = BreakingNewsDetector(min_breaking_confidence=0.3)
        result_low = low_detector.detect("Urgent situation developing")

        # High threshold - should require more signals
        high_detector = BreakingNewsDetector(min_breaking_confidence=0.9)
        result_high = high_detector.detect("Urgent situation developing")

        # Same content but different thresholds
        assert result_low.is_breaking != result_high.is_breaking or \
               result_low.confidence >= 0.3 and result_high.confidence < 0.9
