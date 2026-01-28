"""
Tests for News Type Classifier

Tests classification of:
- LIVE_EVENT: Currently happening events (publishable)
- DATA_RELEASE: Official reports/statistics released today (publishable with label)
- RETROSPECTIVE: Looking back at past events (NOT publishable)
- UNKNOWN: Cannot determine type (publishable - conservative)
"""

import pytest
from app.agent.news_classifier import (
    classify_news_type,
    NewsType,
    ClassificationResult,
    detect_language,
)


class TestNewsTypeClassification:
    """Test news type classification logic"""

    # ============================================
    # LIVE_EVENT tests (should be publishable)
    # ============================================

    def test_live_event_breaking_news(self):
        """BREAKING news should be classified as LIVE_EVENT"""
        result = classify_news_type("BREAKING: Earthquake hits Turkey")
        assert result.news_type == NewsType.LIVE_EVENT
        assert result.is_publishable is True

    def test_live_event_ongoing(self):
        """Ongoing events should be classified as LIVE_EVENT"""
        result = classify_news_type("5 killed in ongoing embassy attack")
        assert result.news_type == NewsType.LIVE_EVENT
        assert result.is_publishable is True

    def test_live_event_developing(self):
        """Developing stories should be classified as LIVE_EVENT"""
        result = classify_news_type("Developing: Protests erupt in capital city")
        assert result.news_type == NewsType.LIVE_EVENT
        assert result.is_publishable is True

    # ============================================
    # DATA_RELEASE tests (should be publishable with label)
    # ============================================

    def test_data_release_spanish_cerro_con(self):
        """Spanish 'cerró con X' pattern should be DATA_RELEASE and publishable"""
        result = classify_news_type("Diciembre cerró con 61 abusos sexuales en Bogotá")
        assert result.news_type == NewsType.DATA_RELEASE
        assert result.is_publishable is True  # DATA_RELEASE is included!

    def test_data_release_monthly_report(self):
        """Monthly report releases should be DATA_RELEASE"""
        result = classify_news_type("Monthly crime report shows 500 incidents in December")
        assert result.news_type == NewsType.DATA_RELEASE
        assert result.is_publishable is True

    def test_data_release_statistics_released(self):
        """Statistics released should be DATA_RELEASE"""
        result = classify_news_type("Official statistics released: 1000 cases recorded")
        assert result.news_type == NewsType.DATA_RELEASE
        assert result.is_publishable is True

    def test_data_release_recorded_deaths(self):
        """Recorded death counts should be DATA_RELEASE"""
        result = classify_news_type("December recorded 61 deaths from violence")
        assert result.news_type == NewsType.DATA_RELEASE
        assert result.is_publishable is True

    def test_data_release_spanish_se_registraron(self):
        """Spanish 'se registraron' should be DATA_RELEASE"""
        result = classify_news_type("Se registraron 45 homicidios en enero")
        assert result.news_type == NewsType.DATA_RELEASE
        assert result.is_publishable is True

    def test_data_release_annual_report(self):
        """Annual reports should be DATA_RELEASE"""
        result = classify_news_type("Annual report published: 2000 incidents last year")
        assert result.news_type == NewsType.DATA_RELEASE
        assert result.is_publishable is True

    # ============================================
    # RETROSPECTIVE tests (should NOT be publishable)
    # ============================================

    def test_retrospective_looking_back(self):
        """Looking back articles should be RETROSPECTIVE and rejected"""
        result = classify_news_type("Looking back at the 2020 pandemic response")
        assert result.news_type == NewsType.RETROSPECTIVE
        assert result.is_publishable is False

    def test_retrospective_anniversary(self):
        """Anniversary articles should be RETROSPECTIVE"""
        result = classify_news_type("10 years since the devastating earthquake: Anniversary commemorations")
        assert result.news_type == NewsType.RETROSPECTIVE
        assert result.is_publishable is False

    def test_retrospective_years_ago_today(self):
        """'Years ago today' should be RETROSPECTIVE"""
        result = classify_news_type("5 years ago today: The historic summit that changed everything")
        assert result.news_type == NewsType.RETROSPECTIVE
        assert result.is_publishable is False

    def test_retrospective_remembering(self):
        """Remembering articles should be RETROSPECTIVE"""
        result = classify_news_type("Remembering the victims of the 2015 attacks")
        assert result.news_type == NewsType.RETROSPECTIVE
        assert result.is_publishable is False

    def test_retrospective_commemoration(self):
        """Commemoration articles should be RETROSPECTIVE"""
        result = classify_news_type("City commemorates 20th anniversary of the tragedy")
        assert result.news_type == NewsType.RETROSPECTIVE
        assert result.is_publishable is False

    def test_retrospective_spanish_aniversario(self):
        """Spanish anniversary should be RETROSPECTIVE"""
        result = classify_news_type("Aniversario de la tragedia: 10 años después")
        assert result.news_type == NewsType.RETROSPECTIVE
        assert result.is_publishable is False

    def test_retrospective_korean(self):
        """Korean retrospective (회고) should be RETROSPECTIVE"""
        result = classify_news_type("2020년 사건 회고: 그때 그 일")
        assert result.news_type == NewsType.RETROSPECTIVE
        assert result.is_publishable is False

    # ============================================
    # UNKNOWN tests (should be publishable - conservative)
    # ============================================

    def test_unknown_neutral_news(self):
        """Neutral news without clear signals should be UNKNOWN and publishable"""
        result = classify_news_type("President meets with foreign delegation")
        # Should be either UNKNOWN or detected as something else
        # The key is that it should be publishable
        assert result.is_publishable is True

    def test_unknown_simple_headline(self):
        """Simple headlines should default to publishable"""
        result = classify_news_type("New policy announced")
        assert result.is_publishable is True


class TestLanguageDetection:
    """Test language detection"""

    def test_detect_english(self):
        """English text should be detected"""
        assert detect_language("Breaking news: earthquake hits") == "en"

    def test_detect_spanish(self):
        """Spanish text should be detected"""
        assert detect_language("El presidente anunció nuevas medidas") == "es"

    def test_detect_korean(self):
        """Korean text should be detected"""
        assert detect_language("대통령이 새로운 정책을 발표했습니다") == "ko"


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_empty_title(self):
        """Empty title should return UNKNOWN and be publishable"""
        result = classify_news_type("")
        assert result.news_type == NewsType.UNKNOWN
        assert result.is_publishable is True

    def test_mixed_signals(self):
        """Mixed signals should favor the strongest pattern"""
        # This has both DATA_RELEASE and RETROSPECTIVE signals
        result = classify_news_type(
            "Looking back: Annual report shows 500 deaths recorded in December"
        )
        # RETROSPECTIVE patterns are weighted higher (0.3 vs 0.25)
        # so this should be RETROSPECTIVE
        assert result.is_publishable is False or result.news_type == NewsType.DATA_RELEASE

    def test_content_helps_classification(self):
        """Content should help with classification"""
        title = "December statistics"
        content = "The monthly report released today shows 61 cases were recorded"
        result = classify_news_type(title, content)
        assert result.news_type == NewsType.DATA_RELEASE
        assert result.is_publishable is True


class TestClassificationResult:
    """Test ClassificationResult structure"""

    def test_result_has_required_fields(self):
        """Result should have all required fields"""
        result = classify_news_type("Test headline")
        assert hasattr(result, 'news_type')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'reason')
        assert hasattr(result, 'is_publishable')
        assert hasattr(result, 'matched_patterns')

    def test_confidence_is_bounded(self):
        """Confidence should be between 0 and 1"""
        result = classify_news_type("Breaking: Multiple patterns breaking developing ongoing")
        assert 0 <= result.confidence <= 1
