# Trigger Implementation Guide

이 가이드는 LiveMap 시스템에 새 데이터 소스(트리거)를 추가하는 방법을 설명합니다.

## 개요

트리거는 외부 API에서 뉴스 이벤트를 스캔하는 데이터 소스 커넥터입니다. 각 트리거는:
- `BaseTrigger`를 상속
- 이벤트를 가져오는 async `scan()` 구현
- `TriggerEvent` 객체 반환
- 신뢰도 점수화를 위한 소스 티어 보유

## Step 1: Trigger 클래스 생성

`app/agent/triggers/`에 새 파일 생성:

```python
# app/agent/triggers/newsapi.py
"""
NewsAPI Trigger - 2차 뉴스 수집
Tier-2: tier2_news (0.75 신뢰도)
"""

import logging
from datetime import datetime
from typing import Any

import httpx

from .base import BaseTrigger, TriggerEvent, TriggerSource, SourceTier

logger = logging.getLogger(__name__)


class NewsAPITrigger(BaseTrigger):
    """
    뉴스 수집을 위한 NewsAPI 트리거.

    API 문서: https://newsapi.org/docs
    """

    def __init__(
        self,
        api_key: str,
        keywords: list[str] | None = None,
        language: str = "en",
        page_size: int = 50,
    ):
        super().__init__(keywords=keywords)
        self.api_key = api_key
        self.language = language
        self.page_size = page_size
        self._client: httpx.AsyncClient | None = None

    @property
    def source_type(self) -> TriggerSource:
        """소스 enum 값 반환."""
        # 먼저 TriggerSource enum에 추가 (Step 2 참조)
        return TriggerSource.NEWSAPI

    @property
    def source_name(self) -> str:
        """사람이 읽을 수 있는 소스 이름."""
        return "NewsAPI"

    async def initialize(self) -> bool:
        """
        HTTP 클라이언트 초기화 및 API 키 확인.

        Returns:
            초기화 성공 시 True
        """
        try:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"X-Api-Key": self.api_key}
            )

            # 테스트 요청으로 API 키 확인
            response = await self._client.get(
                "https://newsapi.org/v2/top-headlines",
                params={"country": "us", "pageSize": 1}
            )

            if response.status_code == 401:
                logger.error("NewsAPI: Invalid API key")
                return False

            self.is_initialized = True
            logger.info("NewsAPI trigger initialized")
            return True

        except Exception as e:
            logger.error(f"NewsAPI initialization failed: {e}")
            return False

    async def scan(self) -> list[TriggerEvent]:
        """
        일치하는 기사를 위해 NewsAPI 스캔.

        Returns:
            TriggerEvent 객체 리스트
        """
        if not self.is_initialized or not self._client:
            logger.warning("NewsAPI not initialized, skipping scan")
            return []

        events: list[TriggerEvent] = []
        self.last_scan = datetime.utcnow()

        try:
            # 키워드로 쿼리 구성
            query = " OR ".join(self.keywords)

            response = await self._client.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "language": self.language,
                    "pageSize": self.page_size,
                    "sortBy": "publishedAt",
                }
            )

            if response.status_code != 200:
                logger.warning(f"NewsAPI error: {response.status_code}")
                return []

            data = response.json()
            articles = data.get("articles", [])

            for article in articles:
                event = self._parse_article(article)
                if event:
                    events.append(event)

            logger.info(f"NewsAPI scan complete: {len(events)} events")
            return events

        except Exception as e:
            logger.error(f"NewsAPI scan error: {e}")
            return []

    def _parse_article(self, article: dict) -> TriggerEvent | None:
        """NewsAPI 기사를 TriggerEvent로 파싱."""
        title = article.get("title", "")
        if not title:
            return None

        # 키워드 일치 확인
        text = f"{title} {article.get('description', '')}"
        keywords_matched = self._matches_keywords(text)
        if not keywords_matched:
            return None

        # 게시 날짜 파싱
        published = article.get("publishedAt", "")
        try:
            detected_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError:
            detected_at = datetime.utcnow()

        return TriggerEvent(
            title=title,
            source=self.source_type,
            source_name=article.get("source", {}).get("name", "NewsAPI"),
            url=article.get("url", ""),
            detected_at=detected_at,
            content=article.get("description", ""),
            language=self.language,
            author=article.get("author", ""),
            raw_data=article,
            keywords_matched=keywords_matched,
        )

    async def close(self):
        """HTTP 클라이언트 정리."""
        if self._client:
            await self._client.aclose()
            self._client = None
```

## Step 2: Source Enum 추가

`app/agent/triggers/base.py`에 추가:

```python
class TriggerSource(str, Enum):
    # 기존 소스들...
    NEWSAPI = "newsapi"  # 이것 추가


# 티어 매핑 추가
SOURCE_TIER_MAP = {
    # 기존 매핑들...
    TriggerSource.NEWSAPI: SourceTier.TIER2_NEWS,  # 이것 추가
}
```

## Step 3: TriggerManager에 등록

`app/agent/triggers/manager.py` 업데이트:

```python
from .newsapi import NewsAPITrigger


class TriggerManager:
    # ... 기존 코드 ...

    def add_newsapi(
        self,
        api_key: str,
        keywords: list[str] | None = None,
        language: str = "en",
    ) -> "TriggerManager":
        """NewsAPI 트리거 추가."""
        trigger = NewsAPITrigger(
            api_key=api_key,
            keywords=keywords,
            language=language,
        )
        self.triggers.append(trigger)
        return self
```

## Step 4: 설정 추가

`app/agent/config.py` 업데이트:

```python
class AgentSettings(BaseSettings):
    # ... 기존 설정 ...

    # NewsAPI
    newsapi_enabled: bool = False
    newsapi_api_key: str = ""
    newsapi_language: str = "en"
```

## Step 5: Scanner에 통합

`app/agent/scanner.py` 업데이트:

```python
def _create_trigger_manager(self) -> TriggerManager:
    manager = TriggerManager(...)

    # ... 기존 트리거들 ...

    # NewsAPI (Tier-2)
    if agent_settings.newsapi_enabled and agent_settings.newsapi_api_key:
        manager.add_newsapi(
            api_key=agent_settings.newsapi_api_key,
            language=agent_settings.newsapi_language,
        )
        logger.info("NewsAPI trigger added (Tier-2)")

    return manager
```

## Step 6: 테스트 작성

`tests/unit/test_trigger_newsapi.py` 생성:

```python
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent.triggers.newsapi import NewsAPITrigger
from app.agent.triggers.base import TriggerSource, SourceTier


class TestNewsAPITrigger:
    """NewsAPI 트리거 테스트."""

    def test_source_type(self):
        """소스 타입은 NEWSAPI여야 함."""
        trigger = NewsAPITrigger(api_key="test")
        assert trigger.source_type == TriggerSource.NEWSAPI

    def test_source_tier(self):
        """소스 티어는 TIER2_NEWS여야 함."""
        trigger = NewsAPITrigger(api_key="test")
        assert trigger.source_tier == SourceTier.TIER2_NEWS

    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """유효한 API 키로 초기화는 True를 반환해야 함."""
        trigger = NewsAPITrigger(api_key="valid_key")

        with patch.object(trigger, '_client') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)

            trigger._client = mock_client
            trigger.is_initialized = True

            # 초기화 성공 확인
            assert trigger.is_initialized

    @pytest.mark.asyncio
    async def test_scan_returns_events(self):
        """스캔은 TriggerEvent 리스트를 반환해야 함."""
        trigger = NewsAPITrigger(api_key="test", keywords=["attack"])
        trigger.is_initialized = True

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "articles": [{
                "title": "Attack reported in region",
                "url": "https://example.com/article",
                "publishedAt": "2024-01-20T10:00:00Z",
                "description": "Details about the attack",
                "source": {"name": "Test Source"},
            }]
        }

        trigger._client = MagicMock()
        trigger._client.get = AsyncMock(return_value=mock_response)

        events = await trigger.scan()

        assert len(events) == 1
        assert events[0].title == "Attack reported in region"
        assert events[0].source == TriggerSource.NEWSAPI
```

## Trigger 체크리스트

- [ ] `BaseTrigger` 상속
- [ ] `source_type` 속성 구현 (enum에 추가)
- [ ] `source_name` 속성 구현
- [ ] `initialize()` 메서드 구현
- [ ] `scan()` 메서드 구현
- [ ] `close()` 메서드 구현
- [ ] 적절한 티어로 `SOURCE_TIER_MAP`에 추가
- [ ] `add_xxx()` 메서드로 `TriggerManager`에 추가
- [ ] `AgentSettings`에 설정 추가
- [ ] `MultiSourceScanner`에 통합
- [ ] 단위 테스트 작성
- [ ] API 제한 및 속도 제한 문서화

## 모범 사례

1. **속도 제한**: API 속도 제한 준수
2. **에러 처리**: 오류 로깅, 실패 시 빈 리스트 반환
3. **키워드 필터링**: 처리 감소를 위해 `scan()`에서 필터링
4. **타임아웃 처리**: 합리적인 HTTP 타임아웃 사용
5. **리소스 정리**: `close()`에서 연결 적절히 닫기
