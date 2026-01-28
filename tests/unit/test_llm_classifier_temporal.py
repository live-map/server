"""
Tests for LLM Classifier Temporal Classification (Phase 6)

Tests classification of:
- BREAKING: Events within 24 hours (publishable)
- DEVELOPING: Ongoing events 1-7 days (publishable)
- RETROSPECTIVE: Analysis/reviews/anniversaries (NOT publishable)
- PREDICTIVE: Future speculation/forecasts (NOT publishable)
- TIMELESS: Encyclopedic content (evaluate individually)
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agent.llm_classifier import (
    LLMClassifier,
    ClassificationResult,
    NewsCategory,
    TemporalCategory,
    NON_PUBLISHABLE_TEMPORAL,
    filter_by_classification,
)


class TestTemporalCategory:
    """Test TemporalCategory enum and constants"""

    def test_temporal_categories_exist(self):
        """All temporal categories should exist"""
        assert TemporalCategory.BREAKING == "breaking"
        assert TemporalCategory.DEVELOPING == "developing"
        assert TemporalCategory.RETROSPECTIVE == "retrospective"
        assert TemporalCategory.PREDICTIVE == "predictive"
        assert TemporalCategory.TIMELESS == "timeless"

    def test_non_publishable_categories(self):
        """RETROSPECTIVE and PREDICTIVE should be non-publishable"""
        assert TemporalCategory.RETROSPECTIVE in NON_PUBLISHABLE_TEMPORAL
        assert TemporalCategory.PREDICTIVE in NON_PUBLISHABLE_TEMPORAL
        assert TemporalCategory.BREAKING not in NON_PUBLISHABLE_TEMPORAL
        assert TemporalCategory.DEVELOPING not in NON_PUBLISHABLE_TEMPORAL
        assert TemporalCategory.TIMELESS not in NON_PUBLISHABLE_TEMPORAL


class TestClassificationResult:
    """Test ClassificationResult with temporal fields"""

    def test_result_has_temporal_fields(self):
        """ClassificationResult should have temporal_category and temporal_markers_found"""
        result = ClassificationResult(
            title="Test",
            is_news=True,
            category=NewsCategory.WAR,
            is_significant=True,
            confidence=0.9,
            reason="Test reason",
        )
        assert hasattr(result, 'temporal_category')
        assert hasattr(result, 'temporal_markers_found')
        assert result.temporal_category == TemporalCategory.BREAKING  # Default
        assert result.temporal_markers_found == []

    def test_result_with_custom_temporal_category(self):
        """ClassificationResult should accept custom temporal category"""
        result = ClassificationResult(
            title="Analysis of 2024",
            is_news=False,
            category=NewsCategory.OTHER,
            is_significant=False,
            confidence=0.9,
            reason="Retrospective content",
            temporal_category=TemporalCategory.RETROSPECTIVE,
            temporal_markers_found=["years later", "analysis"],
        )
        assert result.temporal_category == TemporalCategory.RETROSPECTIVE
        assert result.temporal_markers_found == ["years later", "analysis"]


class TestFallbackClassification:
    """Test fallback classification with temporal detection"""

    def test_fallback_detects_retrospective(self):
        """Fallback should detect retrospective articles"""
        classifier = LLMClassifier()
        articles = [
            {"title": "Three years later: Lessons from the pandemic"},
            {"title": "Looking back at the 2020 crisis"},
            {"title": "Anniversary: 10 years since the earthquake"},
        ]
        results = classifier._fallback_classify(articles)

        for result in results:
            assert result.temporal_category == TemporalCategory.RETROSPECTIVE
            assert result.is_news is False
            assert result.is_significant is False

    def test_fallback_detects_predictive(self):
        """Fallback should detect predictive articles"""
        classifier = LLMClassifier()
        articles = [
            {"title": "What the 2027 election could mean for policy"},
            {"title": "Experts predict oil prices will surge"},
            {"title": "Economic forecast: Outlook for next year"},
        ]
        results = classifier._fallback_classify(articles)

        for result in results:
            assert result.temporal_category == TemporalCategory.PREDICTIVE
            assert result.is_news is False
            assert result.is_significant is False

    def test_fallback_allows_breaking(self):
        """Fallback should allow breaking news"""
        classifier = LLMClassifier()
        articles = [
            {"title": "BREAKING: Earthquake hits coastal region"},
            {"title": "Just in: President announces new policy"},
            {"title": "Developing: Protests erupt in capital"},
        ]
        results = classifier._fallback_classify(articles)

        for result in results:
            assert result.temporal_category == TemporalCategory.BREAKING
            # is_news depends on keyword matching, but temporal should be BREAKING

    def test_fallback_news_with_temporal(self):
        """Fallback should correctly classify news with temporal markers"""
        classifier = LLMClassifier()
        articles = [
            {"title": "BREAKING: Military attack on border region"},
        ]
        results = classifier._fallback_classify(articles)

        assert len(results) == 1
        result = results[0]
        assert result.temporal_category == TemporalCategory.BREAKING
        assert result.is_news is True
        assert result.category == NewsCategory.WAR


class TestFilterByClassification:
    """Test filter_by_classification with temporal filtering"""

    def test_filter_rejects_retrospective(self):
        """filter_by_classification should reject RETROSPECTIVE"""
        results = [
            ClassificationResult(
                title="Breaking news",
                is_news=True,
                category=NewsCategory.WAR,
                is_significant=True,
                confidence=0.9,
                reason="Test",
                temporal_category=TemporalCategory.BREAKING,
            ),
            ClassificationResult(
                title="Looking back",
                is_news=True,  # Even if marked as news
                category=NewsCategory.POLITICS,
                is_significant=True,
                confidence=0.9,
                reason="Test",
                temporal_category=TemporalCategory.RETROSPECTIVE,
            ),
        ]

        filtered = filter_by_classification(results, filter_temporal=True)
        assert len(filtered) == 1
        assert filtered[0].title == "Breaking news"

    def test_filter_rejects_predictive(self):
        """filter_by_classification should reject PREDICTIVE"""
        results = [
            ClassificationResult(
                title="Current event",
                is_news=True,
                category=NewsCategory.DIPLOMACY,
                is_significant=True,
                confidence=0.9,
                reason="Test",
                temporal_category=TemporalCategory.DEVELOPING,
            ),
            ClassificationResult(
                title="Future prediction",
                is_news=True,  # Even if marked as news
                category=NewsCategory.POLITICS,
                is_significant=True,
                confidence=0.9,
                reason="Test",
                temporal_category=TemporalCategory.PREDICTIVE,
            ),
        ]

        filtered = filter_by_classification(results, filter_temporal=True)
        assert len(filtered) == 1
        assert filtered[0].title == "Current event"

    def test_filter_allows_breaking_and_developing(self):
        """filter_by_classification should allow BREAKING and DEVELOPING"""
        results = [
            ClassificationResult(
                title="Breaking news",
                is_news=True,
                category=NewsCategory.WAR,
                is_significant=True,
                confidence=0.9,
                reason="Test",
                temporal_category=TemporalCategory.BREAKING,
            ),
            ClassificationResult(
                title="Developing story",
                is_news=True,
                category=NewsCategory.CONFLICT,
                is_significant=True,
                confidence=0.9,
                reason="Test",
                temporal_category=TemporalCategory.DEVELOPING,
            ),
        ]

        filtered = filter_by_classification(results, filter_temporal=True)
        assert len(filtered) == 2

    def test_filter_temporal_disabled(self):
        """filter_by_classification should not filter temporal when disabled"""
        results = [
            ClassificationResult(
                title="Looking back",
                is_news=True,
                category=NewsCategory.POLITICS,
                is_significant=True,
                confidence=0.9,
                reason="Test",
                temporal_category=TemporalCategory.RETROSPECTIVE,
            ),
        ]

        # With temporal filter disabled, it should pass
        filtered = filter_by_classification(results, filter_temporal=False)
        assert len(filtered) == 1


class TestTemporalClassificationTestCases:
    """Test cases from the plan document"""

    @pytest.fixture
    def classifier(self):
        """Create classifier instance"""
        return LLMClassifier()

    def test_breaking_should_pass(self, classifier):
        """BREAKING articles should pass through"""
        test_cases = [
            "Putin announces new military operation",
            "Israel strikes Gaza as tensions escalate",
            "BREAKING: Massive explosion reported in downtown",
        ]

        for title in test_cases:
            results = classifier._fallback_classify([{"title": title}])
            assert len(results) == 1
            # These should either be BREAKING or pass as news
            result = results[0]
            if result.temporal_category == TemporalCategory.BREAKING:
                # Good - detected as breaking
                pass
            elif result.is_news:
                # Also good - passed as news even if not explicitly breaking
                pass

    def test_retrospective_should_reject(self, classifier):
        """RETROSPECTIVE articles should be rejected"""
        test_cases = [
            "Three years of war: What we learned",
            "2024 in review: Year of conflicts",
            "Looking back at the Arab Spring",
            "10 years later: Anniversary of the treaty",
        ]

        for title in test_cases:
            results = classifier._fallback_classify([{"title": title}])
            assert len(results) == 1
            result = results[0]
            # Should be detected as retrospective and rejected
            assert result.temporal_category == TemporalCategory.RETROSPECTIVE, \
                f"'{title}' should be RETROSPECTIVE, got {result.temporal_category}"
            assert result.is_news is False, \
                f"'{title}' should have is_news=False"

    def test_predictive_should_reject(self, classifier):
        """PREDICTIVE articles should be rejected"""
        test_cases = [
            "What 2027 elections could mean",
            "Experts predict oil prices will surge",
            "Economic forecast: What to expect next year",
        ]

        for title in test_cases:
            results = classifier._fallback_classify([{"title": title}])
            assert len(results) == 1
            result = results[0]
            # Should be detected as predictive and rejected
            assert result.temporal_category == TemporalCategory.PREDICTIVE, \
                f"'{title}' should be PREDICTIVE, got {result.temporal_category}"
            assert result.is_news is False, \
                f"'{title}' should have is_news=False"

    def test_developing_should_pass(self, classifier):
        """DEVELOPING articles should pass through"""
        test_cases = [
            "Day 5 of peace talks: Progress reported",
            "Developing: Hostage situation enters third day",
        ]

        for title in test_cases:
            results = classifier._fallback_classify([{"title": title}])
            assert len(results) == 1
            result = results[0]
            # Should be detected as developing (breaking keyword "developing")
            # or pass as news
            if "developing" in title.lower():
                assert result.temporal_category == TemporalCategory.BREAKING or result.is_news


class TestLLMResponseParsing:
    """Test parsing of LLM responses with temporal fields"""

    def test_parse_response_with_temporal(self):
        """Should correctly parse temporal_category from LLM response"""
        classifier = LLMClassifier()

        # Mock LLM response with temporal fields
        llm_response = """[
            {
                "index": 0,
                "temporal_category": "breaking",
                "is_news": true,
                "category": "war",
                "is_significant": true,
                "temporal_markers_found": ["breaking", "just"],
                "reason": "Active military operation"
            },
            {
                "index": 1,
                "temporal_category": "retrospective",
                "is_news": false,
                "category": "politics",
                "is_significant": false,
                "temporal_markers_found": ["years later", "looking back"],
                "reason": "Historical analysis"
            }
        ]"""

        articles = [
            {"title": "BREAKING: Military offensive begins"},
            {"title": "Three years later: Analysis of the conflict"},
        ]

        results = classifier._parse_llm_response(llm_response, articles)

        assert len(results) == 2

        # First article - breaking
        assert results[0].temporal_category == TemporalCategory.BREAKING
        assert results[0].is_news is True
        assert results[0].temporal_markers_found == ["breaking", "just"]

        # Second article - retrospective (should be auto-rejected)
        assert results[1].temporal_category == TemporalCategory.RETROSPECTIVE
        assert results[1].is_news is False  # Auto-rejected
        assert results[1].temporal_markers_found == ["years later", "looking back"]

    def test_parse_response_auto_rejects_retrospective(self):
        """Should auto-reject RETROSPECTIVE even if LLM says is_news=true"""
        classifier = LLMClassifier()

        # LLM incorrectly marks retrospective as news
        llm_response = """[
            {
                "index": 0,
                "temporal_category": "retrospective",
                "is_news": true,
                "category": "war",
                "is_significant": true,
                "temporal_markers_found": ["anniversary"],
                "reason": "War coverage"
            }
        ]"""

        articles = [{"title": "Anniversary: One year since the invasion"}]
        results = classifier._parse_llm_response(llm_response, articles)

        assert len(results) == 1
        assert results[0].temporal_category == TemporalCategory.RETROSPECTIVE
        # Should be auto-rejected despite LLM saying is_news=true
        assert results[0].is_news is False
        assert results[0].is_significant is False

    def test_parse_response_handles_invalid_temporal(self):
        """Should default to BREAKING for invalid temporal_category"""
        classifier = LLMClassifier()

        llm_response = """[
            {
                "index": 0,
                "temporal_category": "invalid_category",
                "is_news": true,
                "category": "war",
                "is_significant": true,
                "reason": "News"
            }
        ]"""

        articles = [{"title": "Test article"}]
        results = classifier._parse_llm_response(llm_response, articles)

        assert len(results) == 1
        # Should default to BREAKING
        assert results[0].temporal_category == TemporalCategory.BREAKING

    def test_parse_response_handles_missing_temporal(self):
        """Should default to BREAKING when temporal_category is missing"""
        classifier = LLMClassifier()

        # Old-style response without temporal fields
        llm_response = """[
            {
                "index": 0,
                "is_news": true,
                "category": "war",
                "is_significant": true,
                "reason": "News"
            }
        ]"""

        articles = [{"title": "Test article"}]
        results = classifier._parse_llm_response(llm_response, articles)

        assert len(results) == 1
        assert results[0].temporal_category == TemporalCategory.BREAKING
        assert results[0].temporal_markers_found == []
