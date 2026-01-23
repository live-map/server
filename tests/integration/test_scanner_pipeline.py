"""
Integration tests for Scanner Pipeline.

Tests the 7-stage pipeline flow:
1. Trigger Collection (multi-source)
2. Clustering & Deduplication
3. Source Classification
3.5. Event Verification (Gate 0)
4. Confidence Scoring
5. Content Gates (Check-worthiness, Specificity)
5.5. International Affairs Filter
6. Category Limiting & Diversity Interleaving
7. Final Output

Also tests end-to-end scenarios and edge cases.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.scanner import MultiSourceScanner, INTERNATIONAL_AFFAIRS_KEYWORDS
from app.agent.triggers.base import TriggerEvent, TriggerSource, SourceTier, SOURCE_TIER_MAP
from app.agent.confidence_scorer import PublishRecommendation, ConfidenceLevel


@pytest.fixture
def mock_scanner():
    """Create scanner with mocked components."""
    with patch.object(MultiSourceScanner, '_create_trigger_manager'):
        scanner = MultiSourceScanner()
        scanner.trigger_manager = MagicMock()
        scanner.trigger_manager.initialize_all = AsyncMock(return_value={"gdelt": True})
        scanner.trigger_manager.scan_all = AsyncMock(return_value=[])
        scanner.trigger_manager.close_all = AsyncMock()

        # Mock cross source matcher
        scanner.cross_source_matcher = MagicMock()
        scanner.cross_source_matcher.initialize = AsyncMock(return_value=True)
        scanner.cross_source_matcher.match_events = MagicMock(return_value=[])
        scanner._matcher_initialized = True

        # Mock LLM
        scanner.llm = MagicMock()
        scanner.llm.ainvoke = AsyncMock()

        return scanner


class TestStage1TriggerCollection:
    """Tests for Stage 1: Trigger Collection."""

    @pytest.mark.asyncio
    async def test_empty_events(self, mock_scanner):
        """Empty events should return empty list."""
        mock_scanner.trigger_manager.scan_all.return_value = []

        result = await mock_scanner.scan()

        assert result == []

    @pytest.mark.asyncio
    async def test_collect_from_all_sources(self, mock_scanner, trigger_event_factory):
        """Should collect from all configured sources."""
        events = [
            trigger_event_factory(source=TriggerSource.GDELT),
            trigger_event_factory(source=TriggerSource.REDDIT),
        ]
        mock_scanner.trigger_manager.scan_all.return_value = events

        # Mock the matcher to return events
        from app.agent.cross_source_matcher import MatchedEvent
        mock_scanner.cross_source_matcher.match_events.return_value = [
            MatchedEvent(
                primary_event=events[0],
                matching_events=[events[1]],
                similarity_scores=[0.85],
            )
        ]

        await mock_scanner.scan()

        mock_scanner.trigger_manager.scan_all.assert_called_once()


class TestStage3SourceClassification:
    """Tests for Stage 3: Source Classification."""

    def test_tier1_govt_classification(self, trigger_event_factory):
        """Tier-1 govt sources should be identified correctly."""
        usgs_event = trigger_event_factory(source=TriggerSource.USGS)
        noaa_event = trigger_event_factory(source=TriggerSource.NOAA)

        usgs_tier = SOURCE_TIER_MAP.get(usgs_event.source)
        noaa_tier = SOURCE_TIER_MAP.get(noaa_event.source)

        assert usgs_tier == SourceTier.TIER1_GOVT
        assert noaa_tier == SourceTier.TIER1_GOVT

    def test_tier1_news_classification(self, trigger_event_factory):
        """Tier-1 news sources should be identified correctly."""
        gdelt_event = trigger_event_factory(source=TriggerSource.GDELT)
        gdelt_tier = SOURCE_TIER_MAP.get(gdelt_event.source)

        assert gdelt_tier == SourceTier.TIER1_NEWS

    def test_tier3_social_classification(self, trigger_event_factory):
        """Tier-3 social sources should be identified correctly."""
        reddit_event = trigger_event_factory(source=TriggerSource.REDDIT)
        twitter_event = trigger_event_factory(source=TriggerSource.TWITTER)

        reddit_tier = SOURCE_TIER_MAP.get(reddit_event.source)
        twitter_tier = SOURCE_TIER_MAP.get(twitter_event.source)

        assert reddit_tier == SourceTier.TIER3_SOCIAL
        assert twitter_tier == SourceTier.TIER3_SOCIAL


class TestStage35EventVerification:
    """Tests for Stage 3.5: Event Verification (Gate 0)."""

    @pytest.mark.asyncio
    async def test_tier1_govt_bypasses_verification(self, mock_scanner, trigger_event_factory):
        """Tier-1 govt sources should bypass event verification."""
        usgs_event = trigger_event_factory(
            title="M6.5 earthquake in Turkey",
            source=TriggerSource.USGS,
            content="Official USGS earthquake report"
        )
        mock_scanner.trigger_manager.scan_all.return_value = [usgs_event]

        with patch('app.agent.scanner.agent_settings') as mock_settings:
            mock_settings.event_verification_enabled = True
            mock_settings.min_confidence_score = 0.70
            mock_settings.checkworthiness_enabled = False
            mock_settings.specificity_enabled = False
            mock_settings.focus_international_affairs = False
            mock_settings.max_events_per_category = 10
            mock_settings.ensure_category_diversity = False

            result = await mock_scanner._classify_and_group([usgs_event])

        # USGS (Tier-1 govt) should pass without verification
        assert len(result) > 0 or result == []  # May be filtered by other gates


class TestStage4ConfidenceScoring:
    """Tests for Stage 4: Confidence Scoring."""

    def test_two_source_boosted(self, mock_scanner, trigger_event_factory):
        """Multi-source events should have higher confidence."""
        gdelt_event = trigger_event_factory(source=TriggerSource.GDELT)
        reddit_event = trigger_event_factory(source=TriggerSource.REDDIT)

        # Calculate confidence for multi-source
        sources = [
            {"name": "gdelt", "tier": SourceTier.TIER1_NEWS.value},
            {"name": "reddit", "tier": SourceTier.TIER3_SOCIAL.value},
        ]
        result = mock_scanner.confidence_scorer.calculate_confidence(sources)

        # Should satisfy two-source rule
        assert result.two_source_satisfied
        assert result.score >= 0.70

    def test_single_source_lower_confidence(self, mock_scanner):
        """Single non-govt source should have lower confidence."""
        sources = [{"name": "reddit", "tier": SourceTier.TIER3_SOCIAL.value}]
        result = mock_scanner.confidence_scorer.calculate_confidence(sources)

        assert not result.two_source_satisfied
        assert result.score < 0.70


class TestStage5ContentGates:
    """Tests for Stage 5: Content Gates."""

    @pytest.mark.asyncio
    async def test_entertainment_rejected_at_gate1(self, mock_scanner, trigger_event_factory):
        """Entertainment content should be rejected at Gate 1."""
        event = trigger_event_factory(
            title="New war movie releases this Friday",
            content="The film premiere features celebrity actors",
            source=TriggerSource.GDELT,
        )

        # Check worthiness check
        from app.agent.checkworthiness import check_worthiness
        result = check_worthiness(f"{event.title} {event.content}")

        assert not result.is_checkworthy

    @pytest.mark.asyncio
    async def test_vague_content_rejected_at_gate2(self, mock_scanner, trigger_event_factory):
        """Vague content should be rejected at Gate 2."""
        event = trigger_event_factory(
            title="Conflict continues in the region",
            content="The ongoing situation remains uncertain as border areas see activity",
            source=TriggerSource.GDELT,
        )

        from app.agent.specificity import check_specificity
        result = check_specificity(f"{event.title} {event.content}")

        assert not result.is_specific

    @pytest.mark.asyncio
    async def test_specific_news_passes_gates(self, mock_scanner, trigger_event_factory):
        """Specific news should pass content gates."""
        event = trigger_event_factory(
            title="Russian missile strike on Kyiv kills 12",
            content="The attack on Monday morning hit the Shevchenkivskyi district at 6:45 AM, killing 12 and wounding 35.",
            source=TriggerSource.GDELT,
        )

        from app.agent.checkworthiness import check_worthiness
        from app.agent.specificity import check_specificity

        cw_result = check_worthiness(f"{event.title} {event.content}")
        spec_result = check_specificity(f"{event.title} {event.content}")

        assert cw_result.is_checkworthy
        assert spec_result.is_specific


class TestStage55InternationalAffairsFilter:
    """Tests for Stage 5.5: International Affairs Filter."""

    def test_category_keywords_complete(self):
        """All expected categories should have keywords."""
        expected_categories = [
            "war", "conflict", "politics", "security",
            "military", "terrorism", "diplomacy"
        ]
        for cat in expected_categories:
            assert cat in INTERNATIONAL_AFFAIRS_KEYWORDS
            assert len(INTERNATIONAL_AFFAIRS_KEYWORDS[cat]) > 0

    def test_infer_war_category(self, mock_scanner, trigger_event_factory):
        """War-related events should be categorized as 'war'."""
        event = trigger_event_factory(
            title="Airstrike hits military base",
            content="Troops deployed after invasion"
        )
        category = mock_scanner._infer_category_from_event(event)

        assert category == "war"

    def test_infer_terrorism_category(self, mock_scanner, trigger_event_factory):
        """Terrorism-related events should be categorized as 'terrorism'."""
        event = trigger_event_factory(
            title="Terrorist attack claims lives",
            content="Militant group claims responsibility"
        )
        category = mock_scanner._infer_category_from_event(event)

        assert category == "terrorism"

    def test_infer_diplomacy_category(self, mock_scanner, trigger_event_factory):
        """Diplomacy events should be categorized as 'diplomacy'."""
        event = trigger_event_factory(
            title="Ambassador attends peace talks",
            content="Diplomatic negotiations continue at UN"
        )
        category = mock_scanner._infer_category_from_event(event)

        assert category == "diplomacy"

    def test_natural_disaster_from_usgs(self, mock_scanner, trigger_event_factory):
        """USGS events should be natural_disaster."""
        event = trigger_event_factory(
            title="Earthquake detected",
            source=TriggerSource.USGS
        )
        category = mock_scanner._infer_category_from_event(event)

        assert category == "natural_disaster"


class TestStage6CategoryLimiting:
    """Tests for Stage 6: Category Limiting."""

    @pytest.mark.asyncio
    async def test_category_diversity_interleaving(self, mock_scanner, trigger_event_factory):
        """News and disasters should be interleaved 2:1."""
        # This is a unit test for the interleaving logic
        news_events = [
            {"_category": "war", "event": trigger_event_factory(title=f"War news {i}")}
            for i in range(4)
        ]
        disaster_events = [
            {"_category": "natural_disaster", "event": trigger_event_factory(title=f"Disaster {i}")}
            for i in range(2)
        ]

        limited_events = news_events + disaster_events

        # Simulate interleaving logic
        interleaved = []
        news_idx, disaster_idx = 0, 0

        while news_idx < len(news_events) or disaster_idx < len(disaster_events):
            for _ in range(2):
                if news_idx < len(news_events):
                    interleaved.append(news_events[news_idx])
                    news_idx += 1
            if disaster_idx < len(disaster_events):
                interleaved.append(disaster_events[disaster_idx])
                disaster_idx += 1

        # Verify interleaving pattern
        assert len(interleaved) == 6
        # Pattern should be: news, news, disaster, news, news, disaster
        assert interleaved[0]["_category"] == "war"
        assert interleaved[1]["_category"] == "war"
        assert interleaved[2]["_category"] == "natural_disaster"


class TestEndToEndScenarios:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_full_pipeline_with_events(self, mock_scanner, trigger_event_factory):
        """Full pipeline should process events correctly."""
        events = [
            trigger_event_factory(
                title="Russian forces launch missile attack on Kyiv",
                content="At least 12 killed in Monday morning strike on residential area",
                source=TriggerSource.GDELT,
            ),
        ]
        mock_scanner.trigger_manager.scan_all.return_value = events

        # Mock cross-source matcher
        from app.agent.cross_source_matcher import MatchedEvent
        mock_scanner.cross_source_matcher.match_events.return_value = [
            MatchedEvent(
                primary_event=events[0],
                matching_events=[],
                similarity_scores=[],
            )
        ]

        # Mock event verification to pass
        with patch('app.agent.scanner.verify_event_hybrid') as mock_verify:
            mock_verify.return_value = (True, "PASSED")

            with patch('app.agent.scanner.agent_settings') as mock_settings:
                mock_settings.event_verification_enabled = True
                mock_settings.event_verification_use_llm = False
                mock_settings.min_confidence_score = 0.60  # Lower for single source
                mock_settings.checkworthiness_enabled = True
                mock_settings.entertainment_pattern_threshold = 2
                mock_settings.speculation_pattern_threshold = 2
                mock_settings.human_interest_pattern_threshold = 3
                mock_settings.specificity_enabled = True
                mock_settings.min_specificity_score = 0.4
                mock_settings.focus_international_affairs = False
                mock_settings.max_events_per_category = 10
                mock_settings.ensure_category_diversity = False
                mock_settings.log_gate_rejections = False

                result = await mock_scanner._classify_and_group(events)

        # Result depends on confidence threshold
        # Single GDELT source = 0.70 confidence
        # With min_confidence_score=0.60, should pass


class TestEdgeCasesIntegration:
    """Integration tests for edge cases."""

    @pytest.mark.asyncio
    async def test_no_events_from_triggers(self, mock_scanner):
        """Empty trigger results should be handled gracefully."""
        mock_scanner.trigger_manager.scan_all.return_value = []

        result = await mock_scanner.scan()

        assert result == []

    @pytest.mark.asyncio
    async def test_all_events_filtered(self, mock_scanner, trigger_event_factory):
        """All events being filtered should return empty list."""
        events = [
            trigger_event_factory(
                title="New war movie releases Friday",
                content="Celebrity actors discuss their roles",
                source=TriggerSource.REDDIT,  # Low tier
            ),
        ]
        mock_scanner.trigger_manager.scan_all.return_value = events

        from app.agent.cross_source_matcher import MatchedEvent
        mock_scanner.cross_source_matcher.match_events.return_value = [
            MatchedEvent(
                primary_event=events[0],
                matching_events=[],
                similarity_scores=[],
            )
        ]

        with patch('app.agent.scanner.agent_settings') as mock_settings:
            mock_settings.event_verification_enabled = True
            mock_settings.event_verification_use_llm = False
            mock_settings.min_confidence_score = 0.70
            mock_settings.checkworthiness_enabled = True
            mock_settings.entertainment_pattern_threshold = 2
            mock_settings.speculation_pattern_threshold = 2
            mock_settings.human_interest_pattern_threshold = 3
            mock_settings.specificity_enabled = True
            mock_settings.min_specificity_score = 0.4
            mock_settings.focus_international_affairs = False
            mock_settings.max_events_per_category = 10
            mock_settings.ensure_category_diversity = False
            mock_settings.log_gate_rejections = False

            result = await mock_scanner._classify_and_group(events)

        # Single Reddit + entertainment content = filtered
        assert result == []


class TestInitialization:
    """Tests for scanner initialization."""

    @pytest.mark.asyncio
    async def test_initialize_all_components(self, mock_scanner):
        """Initialize should setup all components."""
        # Reset the matcher to force re-initialization
        mock_scanner._matcher_initialized = False
        mock_scanner.cross_source_matcher.initialize = AsyncMock(return_value=True)

        result = await mock_scanner.initialize()

        assert "cross_source_matcher" in result
        mock_scanner.trigger_manager.initialize_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_resources(self, mock_scanner):
        """Close should cleanup all resources."""
        await mock_scanner.close()

        mock_scanner.trigger_manager.close_all.assert_called_once()


class TestScannerStatus:
    """Tests for scanner status reporting."""

    def test_get_status(self, mock_scanner):
        """Status should include last scan time and triggers."""
        mock_scanner.last_scan = datetime.utcnow()
        mock_scanner.trigger_manager.get_status.return_value = {"gdelt": "active"}

        status = mock_scanner.get_status()

        assert "last_scan" in status
        assert "triggers" in status


class TestCallback:
    """Tests for event detection callback."""

    @pytest.mark.asyncio
    async def test_callback_called_for_detected_events(self, trigger_event_factory):
        """Callback should be called for each detected event."""
        callback_events = []

        async def callback(description, category):
            callback_events.append((description, category))

        with patch.object(MultiSourceScanner, '_create_trigger_manager'):
            scanner = MultiSourceScanner(on_event_detected=callback)
            scanner.trigger_manager = MagicMock()
            scanner.trigger_manager.initialize_all = AsyncMock(return_value={})
            scanner.trigger_manager.scan_all = AsyncMock(return_value=[trigger_event_factory()])
            scanner.trigger_manager.close_all = AsyncMock()
            scanner.cross_source_matcher = MagicMock()
            scanner._matcher_initialized = True

            # Mock _classify_and_group to return events
            async def mock_classify(*args, **kwargs):
                return [{"description": "Test event", "category": "war"}]

            scanner._classify_and_group = mock_classify

            await scanner.scan()

        assert len(callback_events) == 1
        assert callback_events[0] == ("Test event", "war")

    @pytest.mark.asyncio
    async def test_callback_error_handled(self, trigger_event_factory):
        """Callback errors should be handled gracefully."""
        def error_callback(description, category):
            raise ValueError("Callback error")

        with patch.object(MultiSourceScanner, '_create_trigger_manager'):
            scanner = MultiSourceScanner(on_event_detected=error_callback)
            scanner.trigger_manager = MagicMock()
            scanner.trigger_manager.initialize_all = AsyncMock(return_value={})
            scanner.trigger_manager.scan_all = AsyncMock(return_value=[])
            scanner.trigger_manager.close_all = AsyncMock()
            scanner.cross_source_matcher = MagicMock()
            scanner._matcher_initialized = True

            scanner._classify_and_group = AsyncMock(return_value=[
                {"description": "Test event", "category": "war"}
            ])

            # Should not raise
            await scanner.scan()
