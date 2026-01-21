"""
GDELT 트리거 - 뉴스 기반 글로벌 검색

특징:
- 무료, 무제한
- 100,000+ 뉴스 소스
- 15분마다 업데이트
- 소셜 미디어는 포함 안 됨 (뉴스만)
"""

import hashlib
import logging
import time
from datetime import datetime

import httpx

from .base import BaseTrigger, TriggerEvent, TriggerSource

logger = logging.getLogger(__name__)

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

# Time-based hash expiry (24 hours)
HASH_EXPIRY_SECONDS = 86400


class GDELTTrigger(BaseTrigger):
    """
    GDELT 뉴스 트리거

    키워드 기반으로 전 세계 뉴스 검색 (소스 지정 없음)
    """

    def __init__(
        self,
        keywords: list[str] | None = None,
        timespan: str = "1h",
        max_results: int = 100,
    ):
        super().__init__(keywords)
        self.timespan = timespan
        self.max_results = max_results
        # Time-based deduplication: hash -> timestamp
        self.seen_hashes: dict[str, float] = {}

    @property
    def source_type(self) -> TriggerSource:
        return TriggerSource.GDELT

    @property
    def source_name(self) -> str:
        return "GDELT News"

    async def initialize(self) -> bool:
        """GDELT는 인증 불필요"""
        self.is_initialized = True
        logger.info("GDELT trigger initialized (no auth required)")
        return True

    async def scan(self) -> list[TriggerEvent]:
        """
        GDELT에서 키워드 검색

        NOTE: GDELT API는 본문 전체에서 키워드를 검색하므로,
        제목에 키워드가 없어도 관련 기사일 수 있음.
        후처리(significance scoring)에서 최종 필터링.
        """
        self.last_scan = datetime.utcnow()
        events = []

        # OR 연산자로 키워드 조합 (괄호 필수)
        query = "(" + " OR ".join(self.keywords[:15]) + ")"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    GDELT_DOC_API,
                    params={
                        "query": query,
                        "mode": "artlist",
                        "maxrecords": str(self.max_results),
                        "format": "json",
                        "timespan": self.timespan,
                        "sort": "datedesc",
                    },
                )
                response.raise_for_status()

                # JSON 응답 확인
                if not response.headers.get("content-type", "").startswith("application/json"):
                    logger.warning(f"GDELT returned non-JSON: {response.text[:100]}")
                    return []

                data = response.json()
                articles = data.get("articles", [])

                current_time = time.time()

                for art in articles:
                    # 중복 체크 (time-based)
                    content_hash = hashlib.md5(
                        f"{art.get('title', '')}:{art.get('url', '')}".encode()
                    ).hexdigest()

                    if content_hash in self.seen_hashes:
                        continue
                    self.seen_hashes[content_hash] = current_time

                    title = art.get("title", "")

                    # 제목에서 키워드 매칭 확인 (있으면 표시용, 없어도 포함)
                    matched = self._matches_keywords(title)

                    # GDELT가 이미 키워드로 필터링했으므로 모든 기사 포함
                    # 최종 필터링은 significance scoring에서 수행
                    events.append(TriggerEvent(
                        title=title,
                        source=TriggerSource.GDELT,
                        source_name=art.get("domain", "unknown"),
                        url=art.get("url", ""),
                        detected_at=datetime.utcnow(),
                        language=art.get("language", "en"),
                        country=art.get("sourcecountry", ""),
                        keywords_matched=matched if matched else ["[gdelt-fulltext]"],
                        raw_data=art,
                    ))

                # 메모리 관리: 만료된 해시 정리
                self._cleanup_expired_hashes(current_time)

                logger.info(f"GDELT scan: {len(articles)} articles, {len(events)} new")

        except httpx.TimeoutException:
            logger.warning("GDELT API timeout")
        except Exception as e:
            logger.error(f"GDELT scan error: {e}")

        return events

    def _cleanup_expired_hashes(self, current_time: float) -> None:
        """Remove expired hashes older than HASH_EXPIRY_SECONDS."""
        expired_hashes = [
            h for h, ts in self.seen_hashes.items()
            if current_time - ts > HASH_EXPIRY_SECONDS
        ]

        for h in expired_hashes:
            del self.seen_hashes[h]

        if expired_hashes:
            logger.debug(
                f"Cleaned up {len(expired_hashes)} expired hashes, "
                f"{len(self.seen_hashes)} remaining"
            )

    async def close(self):
        """정리 (GDELT는 특별한 정리 불필요)"""
        self.seen_hashes.clear()
