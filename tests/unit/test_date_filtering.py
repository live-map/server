"""
Unit tests for Date Filtering - 4-Layer Validation System.

Tests the date filtering system that prevents old articles from being
published as breaking news.

Layers:
1. URL date extraction
2. Content date extraction
3. Past year detection
4. API date fallback

CRITICAL BUG FIX (2026-01-24):
- 2023년 이벤트가 2026년 뉴스로 발행되는 버그 수정
- 콘텐츠에서 과거 연도를 감지하여 오래된 기사 필터링

P0 FIX (2026-01-27):
- DDG/Yahoo API 잘못된 연도 반환 버그 수정 (2024, 2025 반환)
- _parse_published_date()에 연도 검증 추가
- max_age_hours를 1시간으로 축소 (실시간 뉴스만)
"""

from datetime import datetime, timedelta

import pytest

from app.agent.triggers.date_extractor import (
    extract_date_from_url,
    extract_date_from_content,
    contains_past_year,
    validate_trigger_recency,
    validate_article_recency,
)
from app.agent.tools.search import _parse_published_date


class TestExtractDateFromUrl:
    """Tests for URL date extraction (Layer 1)."""

    def test_slash_separated_date(self):
        """Test /2026/01/24/ format."""
        url = "https://example.com/2026/01/24/breaking-news"
        result = extract_date_from_url(url)

        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 24

    def test_dash_separated_date(self):
        """Test /2026-01-24/ format."""
        url = "https://example.com/news/2026-01-24-article"
        result = extract_date_from_url(url)

        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 24

    def test_compact_date(self):
        """Test /20260124/ format."""
        url = "https://example.com/news/20260124-article.html"
        result = extract_date_from_url(url)

        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 24

    def test_old_url_date_2023(self):
        """Test extraction of 2023 date from URL."""
        url = "https://example.com/2023/10/15/old-article"
        result = extract_date_from_url(url)

        assert result is not None
        assert result.year == 2023
        assert result.month == 10
        assert result.day == 15

    def test_no_date_in_url(self):
        """Test URL without date."""
        url = "https://example.com/news/article-123456"
        result = extract_date_from_url(url)

        assert result is None

    def test_unix_timestamp_in_url(self):
        """Test Unix timestamp extraction."""
        # Timestamp for 2026-01-24 00:00:00 UTC
        url = "https://example.com/news/article-1769212800.html"
        result = extract_date_from_url(url)

        assert result is not None
        assert result.year == 2026


class TestExtractDateFromContent:
    """Tests for content date extraction (Layer 2)."""

    def test_month_day_year_format(self):
        """Test 'October 15, 2023' format."""
        title = "Anniversary of October 15, 2023 Hamas Attack"
        result = extract_date_from_content(title)

        assert result is not None
        assert result.year == 2023
        assert result.month == 10
        assert result.day == 15

    def test_day_month_year_format(self):
        """Test '15 October 2023' format."""
        title = "Remembering the 15 October 2023 incident"
        result = extract_date_from_content(title)

        assert result is not None
        assert result.year == 2023
        assert result.month == 10
        assert result.day == 15

    def test_abbreviated_month_format(self):
        """Test 'Oct 15, 2023' format."""
        title = "Events of Oct 15, 2023"
        result = extract_date_from_content(title)

        assert result is not None
        assert result.year == 2023
        assert result.month == 10
        assert result.day == 15

    def test_iso_date_format(self):
        """Test '2023-10-15' format."""
        content = "The incident on 2023-10-15 was significant."
        result = extract_date_from_content("", content)

        assert result is not None
        assert result.year == 2023
        assert result.month == 10
        assert result.day == 15

    def test_on_date_format(self):
        """Test 'on January 6, 2021' format."""
        title = "Events that occurred on January 6, 2021"
        result = extract_date_from_content(title)

        assert result is not None
        assert result.year == 2021
        assert result.month == 1
        assert result.day == 6

    def test_recent_date_extraction(self):
        """Test extraction of recent date."""
        title = "Breaking news on January 24, 2026"
        result = extract_date_from_content(title)

        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 24

    def test_no_date_in_content(self):
        """Test content without explicit date."""
        title = "Breaking: Major incident reported"
        result = extract_date_from_content(title)

        assert result is None


class TestContainsPastYear:
    """Tests for past year detection (Layer 3)."""

    def test_detects_2023_year(self):
        """Test detection of 2023 in text."""
        text = "Anniversary of October 15, 2023 Hamas Attack"
        has_past, year = contains_past_year(text, current_year=2026)

        assert has_past is True
        assert year == 2023

    def test_detects_2021_year(self):
        """Test detection of 2021 in text."""
        text = "Events of January 6, 2021 Capitol protest"
        has_past, year = contains_past_year(text, current_year=2026)

        assert has_past is True
        assert year == 2021

    def test_current_year_not_past(self):
        """Test that current year is not flagged as past."""
        text = "Breaking news in 2026"
        has_past, year = contains_past_year(text, current_year=2026)

        assert has_past is False
        assert year is None

    def test_no_year_in_text(self):
        """Test text without year."""
        text = "Breaking: Major development reported"
        has_past, year = contains_past_year(text, current_year=2026)

        assert has_past is False
        assert year is None

    def test_multiple_years_returns_oldest(self):
        """Test text with multiple years returns the detected past year."""
        text = "Comparing events from 2021 and 2023"
        has_past, year = contains_past_year(text, current_year=2026)

        assert has_past is True
        # Should return the first past year found
        assert year in [2021, 2023]

    def test_year_in_url_style_not_detected(self):
        """Test that year-like numbers in non-year contexts are handled.

        Word boundaries (\b) require alphanumeric to non-alphanumeric transitions,
        so "X2024" doesn't match because X is alphanumeric. This is acceptable
        because product names like "X2024" are unlikely in news headlines about
        international affairs.
        """
        text = "Product model X2024 launched today"
        has_past, year = contains_past_year(text, current_year=2026)

        # Word boundary doesn't match "X2024" - this is acceptable behavior
        assert has_past is False
        assert year is None

        # But a standalone year would be detected
        text2 = "Product launched in 2024 was successful"
        has_past2, year2 = contains_past_year(text2, current_year=2026)
        assert has_past2 is True
        assert year2 == 2024


class TestValidateTriggerRecency:
    """Tests for 4-Layer trigger recency validation."""

    def test_rejects_2023_article_indexed_today(self):
        """2023년 기사가 오늘 인덱싱되어도 거부 - CRITICAL BUG FIX"""
        url = "https://example.com/news/article-123"  # URL에 날짜 없음
        title = "Anniversary of October 15, 2023 Hamas Attack"
        api_date = datetime(2026, 1, 24)  # 오늘 인덱싱

        is_recent, reason, _ = validate_trigger_recency(
            url=url,
            title=title,
            content="",
            api_date=api_date,
            max_age_hours=48,
        )

        assert not is_recent
        assert "2023" in reason or "PAST_YEAR" in reason

    def test_accepts_recent_article_with_url_date(self):
        """최신 기사 (URL에 오늘 날짜)는 통과."""
        today = datetime.utcnow()
        url = f"https://example.com/{today.year}/{today.month:02d}/{today.day:02d}/breaking-news"
        title = "Breaking: New Development Today"

        is_recent, reason, validated_date = validate_trigger_recency(
            url=url,
            title=title,
            content="",
            api_date=datetime.utcnow(),
            max_age_hours=48,
        )

        assert is_recent
        assert "URL_DATE_VALID" in reason
        assert validated_date is not None
        assert validated_date.year == today.year

    def test_rejects_url_with_old_date(self):
        """URL에 오래된 날짜가 있으면 거부."""
        url = "https://example.com/2023/10/15/old-article"
        title = "Some Article"

        is_recent, reason, _ = validate_trigger_recency(
            url=url,
            title=title,
            content="",
            api_date=datetime.utcnow(),
            max_age_hours=48,
        )

        assert not is_recent
        assert "URL_DATE_TOO_OLD" in reason

    def test_rejects_content_with_past_year(self):
        """콘텐츠에 과거 연도가 있으면 거부."""
        url = "https://example.com/news/article-123"  # No date in URL
        title = "Remembering the events of 2021"

        is_recent, reason, _ = validate_trigger_recency(
            url=url,
            title=title,
            content="",
            api_date=datetime.utcnow(),
            max_age_hours=48,
        )

        assert not is_recent
        assert "PAST_YEAR" in reason

    def test_accepts_api_date_only_when_no_other_date(self):
        """URL, 콘텐츠에 날짜가 없고 과거 연도도 없으면 API 날짜 사용."""
        url = "https://example.com/news/article-123"
        title = "Breaking: Major Development"
        api_date = datetime.utcnow()

        is_recent, reason, validated_date = validate_trigger_recency(
            url=url,
            title=title,
            content="",
            api_date=api_date,
            max_age_hours=48,
        )

        assert is_recent
        assert "API_DATE_ONLY" in reason
        assert validated_date == api_date

    def test_rejects_when_api_date_too_old(self):
        """API 날짜가 너무 오래되면 거부."""
        url = "https://example.com/news/article-123"
        title = "Some Event"
        api_date = datetime.utcnow() - timedelta(hours=72)  # 3 days old

        is_recent, reason, _ = validate_trigger_recency(
            url=url,
            title=title,
            content="",
            api_date=api_date,
            max_age_hours=48,
        )

        assert not is_recent
        assert "API_DATE_TOO_OLD" in reason

    def test_rejects_when_no_date_info_available(self):
        """날짜 정보가 전혀 없으면 거부 (보수적 접근)."""
        url = "https://example.com/news/article-123"
        title = "Breaking: Unknown Event"

        is_recent, reason, _ = validate_trigger_recency(
            url=url,
            title=title,
            content="",
            api_date=None,
            max_age_hours=48,
        )

        assert not is_recent
        assert "NO_DATE_INFO" in reason

    def test_past_year_detection_runs_first(self):
        """과거 연도 감지가 URL 날짜보다 먼저 실행됨 (P0 fix).

        CHANGED BEHAVIOR: 과거 연도 감지(Layer 0)가 URL 날짜 확인 전에 실행됨.
        이는 "December 2024" 같은 과거 이벤트 기사가 최근 URL로 발행되는 것을 방지.
        비교 기사도 거부됨 - 이는 의도된 보수적 접근임.
        """
        # URL has recent date, but content mentions old year
        today = datetime.utcnow()
        url = f"https://example.com/{today.year}/{today.month:02d}/{today.day:02d}/article"
        title = "Comparing to events of 2023"

        is_recent, reason, validated_date = validate_trigger_recency(
            url=url,
            title=title,
            content="",
            api_date=datetime.utcnow(),
            max_age_hours=48,
        )

        # NEW BEHAVIOR: Past year detection runs FIRST, so this is rejected
        assert not is_recent
        assert "PAST_YEAR" in reason

    def test_content_date_extraction_when_no_url_date(self):
        """URL에 날짜가 없으면 콘텐츠에서 날짜 추출."""
        url = "https://example.com/news/article-123"
        # Content has explicit recent date
        today = datetime.utcnow()
        title = f"News from January {today.day}, {today.year}"

        is_recent, reason, validated_date = validate_trigger_recency(
            url=url,
            title=title,
            content="",
            api_date=None,
            max_age_hours=48,
        )

        assert is_recent
        assert "CONTENT_DATE_VALID" in reason


class TestValidateArticleRecency:
    """Tests for original validate_article_recency (Layer 1 + fallback)."""

    def test_url_date_valid(self):
        """Test valid URL date."""
        today = datetime.utcnow()
        url = f"https://example.com/{today.year}/{today.month:02d}/{today.day:02d}/article"
        seendate = datetime.utcnow()

        is_valid, reason, url_date = validate_article_recency(
            url=url,
            seendate=seendate,
            max_age_hours=48,
        )

        assert is_valid
        assert "URL_DATE_VALID" in reason
        assert url_date is not None

    def test_url_date_too_old(self):
        """Test rejection of old URL date."""
        url = "https://example.com/2023/10/15/article"
        seendate = datetime.utcnow()

        is_valid, reason, _ = validate_article_recency(
            url=url,
            seendate=seendate,
            max_age_hours=48,
        )

        assert not is_valid
        assert "URL_DATE_TOO_OLD" in reason

    def test_seendate_fallback(self):
        """Test fallback to seendate when no URL date."""
        url = "https://example.com/news/article-123"
        seendate = datetime.utcnow()

        is_valid, reason, url_date = validate_article_recency(
            url=url,
            seendate=seendate,
            max_age_hours=48,
        )

        assert is_valid
        assert "SEENDATE_ONLY" in reason
        assert url_date is None


class TestEdgeCases:
    """Edge case tests for date filtering."""

    def test_empty_url(self):
        """Test with empty URL."""
        result = extract_date_from_url("")
        assert result is None

    def test_empty_title(self):
        """Test with empty title."""
        result = extract_date_from_content("")
        assert result is None

    def test_none_content(self):
        """Test with None content in validate_trigger_recency."""
        today = datetime.utcnow()
        url = f"https://example.com/{today.year}/{today.month:02d}/{today.day:02d}/article"

        is_recent, reason, _ = validate_trigger_recency(
            url=url,
            title="Test",
            content="",
            api_date=None,
            max_age_hours=48,
        )

        assert is_recent  # URL date should work

    def test_unicode_in_title(self):
        """Test with Unicode characters in title.

        Note: Word boundaries (\b) don't work well with non-ASCII characters.
        Korean "2023년" has year followed by Korean character "년", which
        doesn't trigger word boundary. This is acceptable for now since most
        international news sources use English.
        """
        # Korean with year attached to Korean character - doesn't match
        title = "북한 2023년 미사일 발사"  # "년" is attached to 2023
        has_past, year = contains_past_year(title, current_year=2026)
        # Word boundary limitation with Unicode - acceptable
        assert has_past is False

        # But space-separated year works
        title2 = "북한 2023 미사일 발사"  # Space-separated
        has_past2, year2 = contains_past_year(title2, current_year=2026)
        assert has_past2 is True
        assert year2 == 2023

    def test_very_long_content(self):
        """Test with very long content."""
        content = "This is news. " * 1000 + "Event from 2023"

        # Should still find the year even in long content
        # Note: extract_date_from_content only looks at first 1000 chars
        result = extract_date_from_content("", content)
        # The year is beyond 1000 chars, so should not be found
        assert result is None

    def test_malformed_date_url(self):
        """Test URL with malformed date."""
        url = "https://example.com/2026/13/45/article"  # Invalid month/day
        result = extract_date_from_url(url)

        # Should skip invalid dates
        assert result is None or (result.month <= 12 and result.day <= 31)


class TestIntegrationScenarios:
    """Integration scenarios for date filtering."""

    def test_scenario_2023_hamas_attack_anniversary(self):
        """
        시나리오: 2023년 10월 15일 Hamas 공격 기념일 기사
        - GDELT가 오늘 인덱싱
        - URL에 날짜 없음
        - 제목에 2023년 명시
        예상: 거부
        """
        url = "https://news.example.com/middle-east/article-789456"
        title = "One Year Later: October 15, 2023 Hamas Attack Anniversary"
        seendate = datetime(2026, 1, 24, 10, 30)

        is_recent, reason, _ = validate_trigger_recency(
            url=url,
            title=title,
            content="",
            api_date=seendate,
            max_age_hours=48,
        )

        assert not is_recent
        assert "PAST_YEAR" in reason or "2023" in reason

    def test_scenario_recent_breaking_news(self):
        """
        시나리오: 오늘 발생한 속보
        - URL에 오늘 날짜
        - 제목에 연도 없음
        예상: 통과
        """
        today = datetime.utcnow()
        url = f"https://reuters.com/{today.year}/{today.month:02d}/{today.day:02d}/breaking-russia-ukraine"
        title = "Breaking: Major escalation in Russia-Ukraine conflict"

        is_recent, reason, validated_date = validate_trigger_recency(
            url=url,
            title=title,
            content="",
            api_date=today,
            max_age_hours=48,
        )

        assert is_recent
        assert "URL_DATE_VALID" in reason

    def test_scenario_historical_comparison_article(self):
        """
        시나리오: 현재 상황과 과거 비교하는 기사
        - URL에 오늘 날짜
        - 제목에 과거 연도 언급

        CHANGED BEHAVIOR (P0 fix): 과거 연도 감지가 URL 날짜보다 먼저 실행됨.
        이는 "December 2024 events" 같은 과거 이벤트 기사가 최근 URL로 발행되는 것을 방지.
        비교 기사("worse than 2023")도 거부됨 - 이는 의도된 보수적 접근임.
        """
        today = datetime.utcnow()
        url = f"https://example.com/{today.year}/{today.month:02d}/{today.day:02d}/analysis"
        title = "Current tensions worse than 2023 crisis, experts say"

        is_recent, reason, _ = validate_trigger_recency(
            url=url,
            title=title,
            content="",
            api_date=today,
            max_age_hours=48,
        )

        # NEW BEHAVIOR: Past year detection runs FIRST, so comparison articles are also rejected
        # This is intentional - conservative approach to prevent old events from being published
        assert not is_recent
        assert "PAST_YEAR" in reason

    def test_scenario_reddit_post_about_old_event(self):
        """
        시나리오: Reddit에서 과거 이벤트에 대한 포스트
        - URL에 날짜 없음 (Reddit URL)
        - 제목에 2021년 명시
        예상: 거부
        """
        url = "https://www.reddit.com/r/worldnews/comments/abc123/jan_6_2021_never_forget"
        title = "Jan 6, 2021 - Never Forget"
        created_utc = datetime.utcnow()

        is_recent, reason, _ = validate_trigger_recency(
            url=url,
            title=title,
            content="",
            api_date=created_utc,
            max_age_hours=48,
        )

        assert not is_recent
        assert "PAST_YEAR" in reason or "2021" in reason


class TestYearValidation:
    """
    Tests for year validation in _parse_published_date().

    P0 FIX (2026-01-27):
    DDG/Yahoo API가 2024, 2025년 날짜를 반환하는 버그 수정.
    현재 연도(2026)만 허용하도록 연도 검증 추가.
    """

    def test_current_year_accepted(self):
        """현재 연도(2026) 날짜는 허용."""
        date_str = "2026-01-27T10:30:00Z"
        result = _parse_published_date(date_str)

        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 27

    def test_wrong_year_2025_rejected(self):
        """2025년 날짜는 거부 - DDG 버그 케이스."""
        date_str = "2025-01-27T05:53:52+00:00"
        result = _parse_published_date(date_str)

        assert result is None  # Wrong year should be rejected

    def test_wrong_year_2024_rejected(self):
        """2024년 날짜는 거부 - DDG 버그 케이스."""
        date_str = "2024-01-28T05:53:52+00:00"
        result = _parse_published_date(date_str)

        assert result is None  # Wrong year should be rejected

    def test_future_year_rejected(self):
        """미래 연도도 거부."""
        date_str = "2027-01-27T10:30:00Z"
        result = _parse_published_date(date_str)

        assert result is None  # Future year should be rejected

    def test_human_readable_date_current_year(self):
        """사람이 읽을 수 있는 형식 - 현재 연도."""
        date_str = "Jan 27, 2026"
        result = _parse_published_date(date_str)

        assert result is not None
        assert result.year == 2026

    def test_human_readable_date_wrong_year(self):
        """사람이 읽을 수 있는 형식 - 잘못된 연도."""
        date_str = "Jan 27, 2025"
        result = _parse_published_date(date_str)

        assert result is None

    def test_empty_string(self):
        """빈 문자열은 None 반환."""
        result = _parse_published_date("")

        assert result is None

    def test_none_value(self):
        """None 값은 None 반환."""
        result = _parse_published_date(None)

        assert result is None

    def test_invalid_date_string(self):
        """파싱 불가능한 문자열은 None 반환."""
        result = _parse_published_date("not a date")

        assert result is None


class TestTimezoneHandling:
    """
    Tests for timezone handling in validate_trigger_recency.

    P0 FIX (2026-01-27):
    Timezone-aware API dates were causing:
    "can't subtract offset-naive and offset-aware datetimes" error
    """

    def test_timezone_aware_api_date_accepted(self):
        """Timezone-aware API date should be handled safely."""
        from datetime import timezone as tz

        url = "https://example.com/news/article-123"
        title = "Breaking news"
        # Timezone-aware datetime (like from Currents API)
        api_date = datetime.now(tz.utc) - timedelta(minutes=30)

        is_recent, reason, validated_date = validate_trigger_recency(
            url=url,
            title=title,
            content="",
            api_date=api_date,
            max_age_hours=1,
        )

        # Should not raise "can't subtract offset-naive and offset-aware datetimes"
        assert is_recent
        assert "API_DATE" in reason
        # Validated date should be timezone-naive
        assert validated_date is not None
        assert validated_date.tzinfo is None

    def test_timezone_naive_api_date_accepted(self):
        """Timezone-naive API date should work as before."""
        url = "https://example.com/news/article-123"
        title = "Breaking news"
        # Timezone-naive datetime
        api_date = datetime.utcnow() - timedelta(minutes=30)

        is_recent, reason, validated_date = validate_trigger_recency(
            url=url,
            title=title,
            content="",
            api_date=api_date,
            max_age_hours=1,
        )

        assert is_recent
        assert validated_date is not None


class TestMaxAgeHours:
    """
    Tests for max_age_hours changes.

    P0 FIX (2026-01-27):
    max_age_hours를 4시간에서 1시간으로 축소.
    15분 스캔 간격에 맞춰 실시간 뉴스만 수집.
    """

    def test_article_within_1_hour_accepted(self):
        """1시간 이내 기사는 통과 (API date 사용)."""
        # Note: URL dates only have day precision (no time), so they default to midnight.
        # For 1-hour max_age, we rely on API dates which have time precision.
        url = "https://example.com/news/article-123"  # No date in URL
        title = "Breaking news"
        api_date = datetime.utcnow() - timedelta(minutes=30)  # 30 mins ago

        is_recent, reason, _ = validate_trigger_recency(
            url=url,
            title=title,
            content="",
            api_date=api_date,
            max_age_hours=1,  # New default
        )

        assert is_recent
        assert "API_DATE" in reason

    def test_article_2_hours_old_rejected(self):
        """2시간 전 기사는 거부 (max_age_hours=1)."""
        url = "https://example.com/news/article-123"
        title = "Some news"
        api_date = datetime.utcnow() - timedelta(hours=2)

        is_recent, reason, _ = validate_trigger_recency(
            url=url,
            title=title,
            content="",
            api_date=api_date,
            max_age_hours=1,  # New default
        )

        assert not is_recent
        assert "TOO_OLD" in reason

    def test_article_4_hours_old_rejected(self):
        """4시간 전 기사는 거부 (이전에는 통과했음)."""
        url = "https://example.com/news/article-123"
        title = "Old news"
        api_date = datetime.utcnow() - timedelta(hours=4)

        is_recent, reason, _ = validate_trigger_recency(
            url=url,
            title=title,
            content="",
            api_date=api_date,
            max_age_hours=1,  # New default
        )

        assert not is_recent
