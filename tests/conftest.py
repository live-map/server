"""
Shared test fixtures for LiveMap backend tests.

Fixtures:
- mock_llm_response: Mock ChatOpenAI responses
- mock_gdelt_response: Mock GDELT API responses
- trigger_event_factory: TriggerEvent factory for test data
- sample_claims: Sample claim data for verification tests
"""

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

try:
    from app.agent.triggers.base import TriggerSource, TriggerEvent, SourceTier
except ImportError:
    TriggerSource = None
    TriggerEvent = None
    SourceTier = None


# ============================================
# TriggerEvent Factory
# ============================================


@pytest.fixture
def trigger_event_factory():
    """
    Factory for creating TriggerEvent instances.

    Usage:
        event = trigger_event_factory(
            title="Iran attacks US bases",
            source=TriggerSource.GDELT
        )
    """
    def _create_event(
        title: str = "Test event title",
        source: TriggerSource = TriggerSource.GDELT,
        source_name: str = "reuters.com",
        url: str = "https://example.com/news/123",
        detected_at: datetime | None = None,
        content: str = "",
        language: str = "en",
        country: str = "",
        keywords_matched: list[str] | None = None,
        media_urls: list[str] | None = None,
        author: str = "",
        engagement: dict | None = None,
        raw_data: dict | None = None,
    ) -> TriggerEvent:
        return TriggerEvent(
            title=title,
            source=source,
            source_name=source_name,
            url=url,
            detected_at=detected_at or datetime.utcnow(),
            content=content,
            language=language,
            country=country,
            keywords_matched=keywords_matched or [],
            media_urls=media_urls or [],
            author=author,
            engagement=engagement or {},
            raw_data=raw_data or {},
        )

    return _create_event


@pytest.fixture
def sample_gdelt_event(trigger_event_factory):
    """Sample GDELT event for testing."""
    return trigger_event_factory(
        title="Russian forces launch missile strike on Kyiv",
        source=TriggerSource.GDELT,
        source_name="reuters.com",
        content="Russian forces launched multiple missile strikes on Kyiv early Monday morning, killing at least 12 people.",
        country="UA",
        keywords_matched=["missile", "strike", "Kyiv"],
    )


@pytest.fixture
def sample_usgs_event(trigger_event_factory):
    """Sample USGS government event for testing."""
    return trigger_event_factory(
        title="M6.5 earthquake strikes Turkey",
        source=TriggerSource.USGS,
        source_name="USGS Earthquake API",
        content="A magnitude 6.5 earthquake struck eastern Turkey at 14:32 UTC.",
        country="TR",
        keywords_matched=["earthquake"],
    )


@pytest.fixture
def sample_reddit_event(trigger_event_factory):
    """Sample Reddit social event for testing."""
    return trigger_event_factory(
        title="Breaking: Reports of explosions in Kyiv",
        source=TriggerSource.REDDIT,
        source_name="r/worldnews",
        content="Multiple users reporting explosions heard in Kyiv area",
        country="UA",
        engagement={"score": 1500, "comments": 234},
    )


@pytest.fixture
def multi_source_events(trigger_event_factory):
    """Multiple events from different sources for cross-source testing."""
    now = datetime.utcnow()

    return [
        # GDELT (Tier-1 News)
        trigger_event_factory(
            title="Iran launches drone attack on US military base in Iraq",
            source=TriggerSource.GDELT,
            source_name="reuters.com",
            detected_at=now,
            content="Iranian-backed forces launched multiple drone attacks on US military installations.",
        ),
        # Reddit (Tier-3 Social)
        trigger_event_factory(
            title="Breaking: US base in Iraq under drone attack from Iran",
            source=TriggerSource.REDDIT,
            source_name="r/worldnews",
            detected_at=now - timedelta(minutes=5),
            content="Reports coming in of drone attacks on American bases",
            engagement={"score": 2000},
        ),
        # Currents (Tier-2 News)
        trigger_event_factory(
            title="Iranian drones target American forces in Iraq",
            source=TriggerSource.CURRENTS,
            source_name="Currents API",
            detected_at=now - timedelta(minutes=10),
            content="Multiple Iranian drones struck US military facilities in Iraq.",
        ),
    ]


# ============================================
# LLM Mock Fixtures
# ============================================


@pytest.fixture
def mock_llm_response():
    """
    Factory for mocking ChatOpenAI responses.

    Usage:
        mock_llm = mock_llm_response("VERDICT: YES\nREASON: Real event")
        result = await verify_event_hybrid(text, mock_llm)
    """
    def _create_mock(content: str) -> MagicMock:
        mock = MagicMock()
        mock_response = MagicMock()
        mock_response.content = content
        mock.ainvoke = AsyncMock(return_value=mock_response)
        return mock

    return _create_mock


@pytest.fixture
def mock_llm_yes(mock_llm_response):
    """Mock LLM that always returns PASS (international affairs event)."""
    return mock_llm_response("VERDICT: PASS\nREASON: Military conflict between nations - international affairs")


@pytest.fixture
def mock_llm_no(mock_llm_response):
    """Mock LLM that always returns REJECT (not international affairs)."""
    return mock_llm_response("VERDICT: REJECT\nREASON: This is entertainment content.")


@pytest.fixture
def mock_llm_timeout():
    """Mock LLM that raises a timeout error."""
    mock = MagicMock()
    mock.ainvoke = AsyncMock(side_effect=TimeoutError("LLM request timed out"))
    return mock


@pytest.fixture
def mock_llm_error():
    """Mock LLM that raises a generic error."""
    mock = MagicMock()
    mock.ainvoke = AsyncMock(side_effect=Exception("API Error"))
    return mock


# ============================================
# Source/Confidence Score Fixtures
# ============================================


@pytest.fixture
def single_gdelt_source():
    """Single GDELT source for confidence scoring."""
    return [{"name": "GDELT", "tier": SourceTier.TIER1_NEWS.value}]


@pytest.fixture
def single_usgs_source():
    """Single USGS government source for confidence scoring."""
    return [{"name": "USGS", "tier": SourceTier.TIER1_GOVT.value}]


@pytest.fixture
def single_reddit_source():
    """Single Reddit source for confidence scoring."""
    return [{"name": "Reddit", "tier": SourceTier.TIER3_SOCIAL.value}]


@pytest.fixture
def gdelt_plus_reddit_sources():
    """GDELT + Reddit sources (multi-source)."""
    return [
        {"name": "GDELT", "tier": SourceTier.TIER1_NEWS.value},
        {"name": "Reddit", "tier": SourceTier.TIER3_SOCIAL.value},
    ]


@pytest.fixture
def three_tier_sources():
    """Sources from all three tiers."""
    return [
        {"name": "GDELT", "tier": SourceTier.TIER1_NEWS.value},
        {"name": "Currents", "tier": SourceTier.TIER2_NEWS.value},
        {"name": "Reddit", "tier": SourceTier.TIER3_SOCIAL.value},
    ]


# ============================================
# Sample Claims Fixtures
# ============================================


@pytest.fixture
def sample_claims():
    """Sample claims for verification testing."""
    return [
        {
            "claim": "12 people were killed in the attack",
            "evidence": "Ukrainian officials confirmed 12 casualties",
            "verdict": "SUPPORTED",
        },
        {
            "claim": "The attack occurred at 6:45 AM local time",
            "evidence": "Multiple sources report early morning timing",
            "verdict": "SUPPORTED",
        },
        {
            "claim": "100 missiles were launched",
            "evidence": "No reliable source confirms this number",
            "verdict": "NOT_SUPPORTED",
        },
    ]


# ============================================
# Test Text Samples
# ============================================


@pytest.fixture
def real_event_texts():
    """Sample texts that should pass event verification."""
    return [
        "Iran attacks US bases in Iraq, 3 soldiers injured",
        "North Korea fires ballistic missile toward Sea of Japan",
        "Protesters clash with police in Paris over pension reform",
        "Putin and Xi meet in Beijing for summit talks",
        "M6.2 earthquake hits Turkey, 15 dead",
        "Israeli forces conduct airstrike on Gaza",
        "Russian forces shell Kharkiv residential area",
        "Hamas militants launch attack on Israeli settlements",
    ]


@pytest.fixture
def not_event_texts():
    """Sample texts that should NOT pass event verification."""
    return [
        "New war movie 'Invasion' releases this Friday",
        "Call of Duty: Modern Warfare gets new update",
        "In 1945, World War II ended with Japan's surrender",
        "If Russia invades, NATO might respond with force",
        "World Cup final: France defeats Argentina 3-2",
        "My review of the new documentary about war",
        "Game of Thrones season 8 episode 3 battle scene",
        "50% off sale on military-style jackets",
        "Opinion: What the war means for global economy",
        "Analysts predict conflict could escalate",
    ]


@pytest.fixture
def edge_case_texts():
    """Edge case texts for robustness testing."""
    return {
        "empty": "",
        "whitespace": "   \n\t  ",
        "unicode_korean": "북한이 미사일을 발사했다",
        "unicode_chinese": "中国和俄罗斯举行联合军事演习",
        "very_long": "Breaking news: " + "This is important news. " * 500,
        "special_chars": "Attack!!! @#$%^& **** (location: unknown)",
        "mixed_content": "The movie about war was released. Meanwhile, real fighting continued in Gaza with 15 casualties reported.",
    }


# ============================================
# GDELT API Mock Fixtures
# ============================================


@pytest.fixture
def mock_gdelt_response():
    """
    Factory for mocking GDELT API responses.

    Usage:
        with mock_gdelt_response(articles=[...]):
            result = await gdelt_trigger.scan()
    """
    def _create_mock(articles: list[dict] | None = None) -> dict:
        if articles is None:
            articles = [
                {
                    "title": "Russia launches new offensive in Ukraine",
                    "url": "https://reuters.com/article/123",
                    "seendate": datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"),
                    "domain": "reuters.com",
                    "language": "English",
                    "sourcecountry": "United States",
                }
            ]
        return {"articles": articles}

    return _create_mock


@pytest.fixture
def mock_empty_gdelt_response():
    """Empty GDELT response for testing empty results."""
    return {"articles": []}


# ============================================
# Embedding Mock Fixtures
# ============================================


@pytest.fixture
def mock_embeddings():
    """Mock embedding vectors for semantic matching tests."""
    import numpy as np

    # Create sample embeddings (1024 dimensions for BGE-M3)
    base_vector = np.random.randn(1024)
    base_vector = base_vector / np.linalg.norm(base_vector)

    return {
        "event1": base_vector.tolist(),
        "event2": (base_vector + np.random.randn(1024) * 0.1).tolist(),  # Similar
        "event3": np.random.randn(1024).tolist(),  # Different
    }


@pytest.fixture
def mock_sentence_transformer():
    """Mock SentenceTransformer for cross-source matcher tests."""
    import numpy as np

    def _create_mock():
        mock = MagicMock()

        def encode_fn(texts, normalize_embeddings=True, show_progress_bar=False):
            # Return 1024-dim vectors
            embeddings = np.random.randn(len(texts), 1024)
            if normalize_embeddings:
                embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
            return embeddings

        mock.encode = encode_fn
        return mock

    return _create_mock


# ============================================
# Database Mock Fixtures
# ============================================


@pytest.fixture
def mock_db_session():
    """Mock async database session for deduplication tests."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


# ============================================
# Test Categories
# ============================================


# Pytest markers for test organization
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "api: API endpoint tests")
    config.addinivalue_line("markers", "slow: Slow tests (require LLM or external APIs)")
    config.addinivalue_line("markers", "requires_llm: Tests requiring actual LLM")
    config.addinivalue_line("markers", "requires_db: Tests requiring database")
