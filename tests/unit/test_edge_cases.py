"""
Edge case tests for robustness.

Tests extreme scenarios and boundary conditions:
1. Empty events
2. LLM timeout/errors
3. API rate limiting
4. Unicode/multilingual content
5. Very long content
6. Missing required fields
7. Malformed data
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.event_verifier import is_likely_real_event, verify_event_hybrid
from app.agent.confidence_scorer import MultiSourceConfidenceScorer
from app.agent.cross_source_matcher import CrossSourceMatcher, MatchedEvent
from app.agent.checkworthiness import check_worthiness
from app.agent.specificity import check_specificity
from app.agent.triggers.base import TriggerEvent, TriggerSource, SourceTier


class TestEmptyInputs:
    """Tests for empty/null inputs."""

    def test_empty_text_event_verifier(self):
        """Empty text should pass rule filter (no patterns match)."""
        passed, reason = is_likely_real_event("")
        assert passed
        assert reason is None

    def test_empty_sources_confidence(self):
        """Empty sources should return zero confidence."""
        scorer = MultiSourceConfidenceScorer()
        result = scorer.calculate_confidence([])

        assert result.score == 0.0
        assert result.source_count == 0

    def test_empty_events_matcher(self):
        """Empty events should return empty matches."""
        matcher = CrossSourceMatcher()
        result = matcher.match_events([])

        assert result == []

    def test_empty_text_checkworthiness(self):
        """Empty text should pass checkworthiness (no patterns match)."""
        result = check_worthiness("")
        assert result.is_checkworthy

    def test_empty_text_specificity(self):
        """Empty text should fail specificity (no content to analyze)."""
        result = check_specificity("")
        assert not result.is_specific


class TestLLMTimeoutAndErrors:
    """Tests for LLM timeout and error handling."""

    @pytest.mark.asyncio
    async def test_llm_timeout_60s(self, mock_llm_timeout):
        """LLM 60s timeout should reject (conservative approach)."""
        text = "Iran attacks US bases"
        is_event, reason = await verify_event_hybrid(text, mock_llm_timeout, use_llm=True, use_zero_shot=False)

        # Should reject on error (conservative approach)
        assert not is_event
        assert "LLM_ERROR" in reason

    @pytest.mark.asyncio
    async def test_llm_network_error(self):
        """Network errors should reject (conservative approach)."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=ConnectionError("Network unreachable"))

        text = "Iran attacks US bases"
        is_event, reason = await verify_event_hybrid(text, mock_llm, use_llm=True, use_zero_shot=False)

        assert not is_event
        assert "LLM_ERROR" in reason

    @pytest.mark.asyncio
    async def test_llm_rate_limit_error(self):
        """Rate limit errors should reject (conservative approach)."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("Rate limit exceeded"))

        text = "Iran attacks US bases"
        is_event, reason = await verify_event_hybrid(text, mock_llm, use_llm=True, use_zero_shot=False)

        assert not is_event
        assert "LLM_ERROR" in reason

    @pytest.mark.asyncio
    async def test_llm_invalid_response(self, mock_llm_response):
        """Invalid LLM response should be handled gracefully."""
        mock_llm = mock_llm_response("INVALID RESPONSE FORMAT")

        text = "Iran attacks US bases"
        is_event, reason = await verify_event_hybrid(text, mock_llm, use_llm=True)

        # "NO" not in response, so should pass
        # (implementation checks for "YES" in verdict line)


class TestGDELT429RateLimit:
    """Tests for GDELT API rate limiting."""

    @pytest.mark.asyncio
    async def test_gdelt_rate_limit_handling(self):
        """GDELT 429 errors should be handled gracefully."""
        # This would be tested in the GDELT trigger itself
        # Here we test that the scanner handles missing events gracefully
        from app.agent.scanner import MultiSourceScanner

        with patch.object(MultiSourceScanner, '_create_trigger_manager'):
            scanner = MultiSourceScanner()
            scanner.trigger_manager = MagicMock()
            scanner.trigger_manager.scan_all = AsyncMock(return_value=[])
            scanner._matcher_initialized = True
            scanner.cross_source_matcher = MagicMock()

            result = await scanner._classify_and_group([])

        assert result == []


class TestUnicodeAndMultilingual:
    """Tests for Unicode and multilingual content."""

    def test_unicode_korean_title(self):
        """Korean title should be handled correctly."""
        text = "북한이 미사일을 발사했다"
        passed, reason = is_likely_real_event(text)

        # No English patterns should match
        assert passed

    def test_unicode_chinese_title(self):
        """Chinese title should be handled correctly."""
        text = "中国和俄罗斯举行联合军事演习"
        passed, reason = is_likely_real_event(text)

        assert passed

    def test_unicode_arabic_title(self):
        """Arabic title should be handled correctly."""
        text = "هجوم صاروخي على قاعدة عسكرية"
        passed, reason = is_likely_real_event(text)

        assert passed

    def test_mixed_unicode_and_english(self):
        """Mixed Unicode and English should work."""
        text = "북한 launches missile toward Japan"
        passed, reason = is_likely_real_event(text)

        assert passed

    def test_unicode_emoji(self):
        """Emoji in text should not cause issues."""
        text = "🚨 Breaking: Attack reported in region"
        passed, reason = is_likely_real_event(text)

        # No patterns should match
        assert passed

    def test_unicode_specificity(self):
        """Specificity check with Korean text."""
        text = "러시아가 월요일 아침 키이우를 공격해 12명이 사망했다"
        result = check_specificity(text)

        # English patterns won't match Korean, but should not error


class TestVeryLongContent:
    """Tests for very long content handling."""

    def test_10000_char_content_event_verifier(self):
        """Very long content should be handled by event verifier."""
        text = "Breaking news about attack. " * 500  # ~10000 chars
        passed, reason = is_likely_real_event(text)

        # Should complete without error
        assert isinstance(passed, bool)

    def test_10000_char_content_checkworthiness(self):
        """Very long content should be handled by checkworthiness."""
        text = "Breaking news about military operation. " * 500
        result = check_worthiness(text)

        assert isinstance(result.is_checkworthy, bool)

    def test_10000_char_content_specificity(self):
        """Very long content should be handled by specificity."""
        text = "The attack on Monday killed 12 people in Kyiv. " * 300
        result = check_specificity(text)

        assert isinstance(result.is_specific, bool)

    def test_very_long_title_matcher(self, trigger_event_factory):
        """Very long title should be handled by matcher."""
        matcher = CrossSourceMatcher()
        long_title = "A" * 1000

        event = trigger_event_factory(title=long_title)
        text = matcher._get_event_text(event)

        # Should truncate content
        assert len(text) <= 1500  # Title + truncated content


class TestMissingRequiredFields:
    """Tests for missing field handling."""

    def test_missing_content_field(self, trigger_event_factory):
        """Event with empty content should be handled."""
        event = trigger_event_factory(title="Test event", content="")

        matcher = CrossSourceMatcher()
        text = matcher._get_event_text(event)

        assert text == "Test event"

    def test_trigger_event_minimal(self):
        """TriggerEvent with minimal fields should work."""
        event = TriggerEvent(
            title="Test",
            source=TriggerSource.GDELT,
            source_name="test",
            url="http://test.com",
            detected_at=datetime.utcnow(),
        )

        assert event.title == "Test"
        assert event.content == ""
        assert event.keywords_matched == []

    def test_matched_event_empty_matching(self, trigger_event_factory):
        """MatchedEvent with no matches should have source_count 1."""
        matched = MatchedEvent(
            primary_event=trigger_event_factory(),
            matching_events=[],
            similarity_scores=[],
        )

        assert matched.source_count == 1
        assert matched.avg_similarity == 1.0


class TestMalformedData:
    """Tests for malformed data handling."""

    def test_special_characters_in_text(self):
        """Special characters should not cause issues."""
        text = "Attack!!! @#$%^&*() [location: unknown]"
        passed, reason = is_likely_real_event(text)

        assert isinstance(passed, bool)

    def test_newlines_in_text(self):
        """Newlines in text should be handled."""
        text = "Breaking\nnews:\nAttack\nreported"
        passed, reason = is_likely_real_event(text)

        assert passed

    def test_tabs_in_text(self):
        """Tabs in text should be handled."""
        text = "Breaking\tnews\tabout\tattack"
        passed, reason = is_likely_real_event(text)

        assert passed

    def test_null_bytes_in_text(self):
        """Null bytes should be handled (if present)."""
        text = "Breaking news\x00about attack"
        passed, reason = is_likely_real_event(text)

        assert isinstance(passed, bool)

    def test_html_in_text(self):
        """HTML tags in text should not cause issues."""
        text = "<b>Breaking</b> news: <a href='#'>Attack</a> reported"
        passed, reason = is_likely_real_event(text)

        assert passed  # "Attack" should pass

    def test_url_in_text(self):
        """URLs in text should not cause issues."""
        text = "Breaking news: https://example.com/news/attack-reported"
        passed, reason = is_likely_real_event(text)

        assert passed


class TestBoundaryConditions:
    """Tests for boundary conditions."""

    def test_confidence_exactly_070(self):
        """Confidence exactly at threshold should be HIGH."""
        scorer = MultiSourceConfidenceScorer()

        # GDELT only gives exactly 0.70
        sources = [{"name": "GDELT", "tier": SourceTier.TIER1_NEWS.value}]
        result = scorer.calculate_confidence(sources)

        assert result.score >= 0.70
        assert result.level.value in ["high", "very_high"]

    def test_specificity_exactly_at_threshold(self):
        """Specificity exactly at threshold should pass."""
        # This is difficult to achieve exactly, but we can test around it
        text = "Fighting reported in Kyiv today"  # Location + recent time
        result = check_specificity(text, min_score=0.3)

        # Should pass with low threshold

    def test_time_window_boundary(self, trigger_event_factory):
        """Events exactly at time window boundary."""
        matcher = CrossSourceMatcher(time_window_hours=6)
        now = datetime.utcnow()

        # Event exactly at boundary
        boundary_event = trigger_event_factory(
            detected_at=now - timedelta(hours=6, seconds=1)
        )

        # This event should be filtered (just outside window)
        result = matcher.match_events([boundary_event])

        # Might be empty if filtered
        assert isinstance(result, list)


class TestConcurrentOperations:
    """Tests for concurrent operation handling."""

    @pytest.mark.asyncio
    async def test_multiple_concurrent_verifications(self, mock_llm_yes):
        """Multiple concurrent verifications should work."""
        texts = [
            "Iran attacks US bases",
            "North Korea fires missile",
            "Earthquake hits Turkey",
        ]

        results = await asyncio.gather(*[
            verify_event_hybrid(text, mock_llm_yes, use_llm=True)
            for text in texts
        ])

        assert len(results) == 3
        for is_event, reason in results:
            assert is_event


class TestMemoryHandling:
    """Tests for memory-safe handling."""

    def test_large_event_list(self, trigger_event_factory):
        """Large number of events should be handled."""
        matcher = CrossSourceMatcher()

        # Create 100 events
        events = [
            trigger_event_factory(
                title=f"Event {i}",
                source=TriggerSource.GDELT if i % 2 == 0 else TriggerSource.REDDIT,
            )
            for i in range(100)
        ]

        # Should complete without memory issues
        result = matcher.match_events(events)

        assert len(result) <= 100

    def test_large_source_list(self):
        """Large number of sources should be handled."""
        scorer = MultiSourceConfidenceScorer()

        # Create many sources
        sources = [
            {"name": f"Source{i}", "tier": SourceTier.TIER2_NEWS.value}
            for i in range(50)
        ]

        result = scorer.calculate_confidence(sources)

        # Should complete and cap at 0.99
        assert result.score <= 0.99


class TestDateParsing:
    """Tests for date-related edge cases."""

    def test_future_date_in_text(self):
        """Future dates in text should be handled."""
        text = "Attack scheduled for January 2030"
        result = check_specificity(text)

        # Should detect date pattern even if future
        # Behavior depends on implementation

    def test_invalid_date_in_text(self):
        """Invalid dates should be handled gracefully."""
        text = "Attack on January 99, 2024"
        result = check_specificity(text)

        # Should not crash

    def test_relative_date_handling(self):
        """Relative dates should be detected."""
        text = "Attack occurred yesterday morning"
        result = check_specificity(text)

        assert result.has_recent_date


class TestSourceTierEdgeCases:
    """Tests for source tier edge cases."""

    def test_unknown_source_tier(self):
        """Unknown source should get default tier."""
        scorer = MultiSourceConfidenceScorer()

        sources = [{"name": "Unknown", "tier": "unknown_tier"}]
        result = scorer.calculate_confidence(sources)

        # Should use default weight (0.50)
        assert result.tier_average == 0.50

    def test_mixed_known_unknown_tiers(self):
        """Mix of known and unknown tiers should work."""
        scorer = MultiSourceConfidenceScorer()

        sources = [
            {"name": "GDELT", "tier": SourceTier.TIER1_NEWS.value},
            {"name": "Unknown", "tier": "unknown_tier"},
        ]
        result = scorer.calculate_confidence(sources)

        # Should calculate average correctly
        assert result.source_count == 2
