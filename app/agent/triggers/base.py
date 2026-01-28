"""
트리거 기본 인터페이스

모든 트리거 소스는 이 인터페이스를 구현해야 함
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# Default hash expiry (24 hours)
DEFAULT_HASH_EXPIRY_SECONDS = 86400


class TriggerSource(str, Enum):
    """트리거 소스 유형"""
    # Tier-1: Primary Sources
    GDELT = "gdelt"
    USGS = "usgs"
    NOAA = "noaa"
    EMSC = "emsc"

    # Tier-2: Secondary Sources
    CURRENTS = "currents"
    WORLDNEWS = "worldnews"
    ACLED = "acled"
    BRAVE = "brave"

    # Tier-3: Signal Sources
    TWITTER = "twitter"
    TELEGRAM = "telegram"
    REDDIT = "reddit"
    BLUESKY = "bluesky"
    GOOGLE_TRENDS = "google_trends"


class SourceTier(str, Enum):
    """Source credibility tiers for confidence scoring"""
    TIER1_GOVT = "tier1_govt"    # Government APIs (0.99)
    TIER1_NEWS = "tier1_news"    # Major news aggregators (0.90)
    TIER2_DATA = "tier2_data"    # Research data (0.85)
    TIER2_NEWS = "tier2_news"    # Secondary news APIs (0.75)
    TIER3_SOCIAL = "tier3_social"  # Social media (0.40)
    TIER3_MSG = "tier3_msg"      # Messaging platforms (0.35)
    TIER3_TREND = "tier3_trend"  # Trend indicators (0.30)


# Mapping from TriggerSource to SourceTier
SOURCE_TIER_MAP: dict[TriggerSource, SourceTier] = {
    # Tier-1: Primary Sources
    TriggerSource.GDELT: SourceTier.TIER1_NEWS,
    TriggerSource.USGS: SourceTier.TIER1_GOVT,
    TriggerSource.NOAA: SourceTier.TIER1_GOVT,
    TriggerSource.EMSC: SourceTier.TIER1_GOVT,
    # Tier-2: Secondary Sources
    TriggerSource.CURRENTS: SourceTier.TIER2_NEWS,
    TriggerSource.WORLDNEWS: SourceTier.TIER2_NEWS,
    TriggerSource.ACLED: SourceTier.TIER2_DATA,
    TriggerSource.BRAVE: SourceTier.TIER2_NEWS,
    # Tier-3: Signal Sources
    TriggerSource.TWITTER: SourceTier.TIER3_SOCIAL,
    TriggerSource.TELEGRAM: SourceTier.TIER3_MSG,
    TriggerSource.REDDIT: SourceTier.TIER3_SOCIAL,
    TriggerSource.BLUESKY: SourceTier.TIER3_SOCIAL,
    TriggerSource.GOOGLE_TRENDS: SourceTier.TIER3_TREND,
}


@dataclass
class TriggerEvent:
    """
    트리거 이벤트 - 감지된 사건 정보

    모든 트리거 소스가 동일한 형식으로 이벤트를 반환
    """
    # 필수 필드
    title: str                    # 이벤트 제목/요약
    source: TriggerSource         # 트리거 소스 (gdelt, twitter, telegram)
    source_name: str              # 구체적 소스명 (예: @IranIntl, reuters.com)
    url: str                      # 원본 URL
    detected_at: datetime         # 감지 시간

    # 선택 필드
    content: str = ""             # 전체 내용
    language: str = "en"          # 언어
    country: str = ""             # 관련 국가
    keywords_matched: list[str] = field(default_factory=list)  # 매칭된 키워드
    media_urls: list[str] = field(default_factory=list)        # 미디어 URL
    author: str = ""              # 작성자
    engagement: dict = field(default_factory=dict)  # 참여도 (likes, retweets 등)

    # 메타데이터
    raw_data: dict = field(default_factory=dict)  # 원본 데이터

    @property
    def source_tier(self) -> SourceTier:
        """Get the credibility tier for this event's source"""
        return SOURCE_TIER_MAP.get(self.source, SourceTier.TIER2_NEWS)

    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return {
            "title": self.title,
            "source": self.source.value,
            "source_tier": self.source_tier.value,
            "source_name": self.source_name,
            "url": self.url,
            "detected_at": self.detected_at.isoformat(),
            "content": self.content,
            "language": self.language,
            "country": self.country,
            "keywords_matched": self.keywords_matched,
            "media_urls": self.media_urls,
            "author": self.author,
            "engagement": self.engagement,
        }


class BaseTrigger(ABC):
    """
    트리거 기본 클래스

    모든 트리거 소스가 구현해야 하는 인터페이스
    """

    def __init__(self, keywords: list[str] | None = None):
        """
        Args:
            keywords: 감지할 키워드 목록
        """
        self.keywords = keywords or self._default_keywords()
        self.is_initialized = False
        self.last_scan: datetime | None = None

    @property
    @abstractmethod
    def source_type(self) -> TriggerSource:
        """트리거 소스 유형"""
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """트리거 소스 이름 (표시용)"""
        pass

    @property
    def source_tier(self) -> SourceTier:
        """Source credibility tier for confidence scoring"""
        return SOURCE_TIER_MAP.get(self.source_type, SourceTier.TIER2_NEWS)

    @abstractmethod
    async def initialize(self) -> bool:
        """
        트리거 초기화 (인증 등)

        Returns:
            초기화 성공 여부
        """
        pass

    @abstractmethod
    async def scan(self) -> list[TriggerEvent]:
        """
        키워드 기반 스캔 실행

        Returns:
            감지된 이벤트 목록
        """
        pass

    @abstractmethod
    async def close(self):
        """리소스 정리"""
        pass

    def _default_keywords(self) -> list[str]:
        """
        기본 키워드 목록 (v2: GDELT API 제한에 맞춘 15개)

        NOTE: GDELT는 키워드를 최대 15개까지 지원
        후처리에서 significance scoring으로 노이즈 필터링 필요
        """
        return [
            # 전쟁/분쟁 (최우선)
            "airstrike",
            "missile",
            "shelling",
            "troops",
            "invasion",

            # 대량 피해
            "casualties",
            "massacre",
            "killed",

            # 테러
            "bombing",
            "explosion",

            # 시위/폭동
            "protest",
            "riot",

            # 주요 분쟁 지역 (고유명사)
            "Ukraine",
            "Gaza",
            "Hamas",
        ]

    def _matches_keywords(self, text: str) -> list[str]:
        """텍스트에서 매칭된 키워드 찾기"""
        text_lower = text.lower()
        return [kw for kw in self.keywords if kw.lower() in text_lower]


class HashCleanupMixin:
    """
    Mixin for time-based hash deduplication and cleanup.

    Provides:
    - seen_hashes storage
    - _cleanup_expired_hashes() method

    Usage:
        class MyTrigger(BaseTrigger, HashCleanupMixin):
            def __init__(self):
                self.seen_hashes: dict[str, float] = {}
                self.hash_expiry_seconds = 86400  # Optional override
    """

    seen_hashes: dict[str, float]
    hash_expiry_seconds: int = DEFAULT_HASH_EXPIRY_SECONDS

    def _cleanup_expired_hashes(self, current_time: float) -> None:
        """Remove expired hashes older than hash_expiry_seconds."""
        expiry = getattr(self, "hash_expiry_seconds", DEFAULT_HASH_EXPIRY_SECONDS)
        expired = [
            h for h, ts in self.seen_hashes.items()
            if current_time - ts > expiry
        ]
        for h in expired:
            del self.seen_hashes[h]

        if expired:
            logger.debug(
                f"[{self.__class__.__name__}] Cleaned up {len(expired)} expired hashes, "
                f"{len(self.seen_hashes)} remaining"
            )
