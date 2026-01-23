"""
GDELT 트리거 - 뉴스 기반 글로벌 검색

특징:
- 무료, 무제한
- 100,000+ 뉴스 소스
- 15분마다 업데이트
- 소셜 미디어는 포함 안 됨 (뉴스만)

Enhanced Features (v2):
- GKG Themes: Crisis theme monitoring
- Goldstein/Tone filter: Conflict intensity filtering
- Theme-based query support
"""

import hashlib
import logging
import time
from datetime import datetime

import httpx

from .base import BaseTrigger, TriggerEvent, TriggerSource
from .date_extractor import extract_date_from_url, validate_article_recency

logger = logging.getLogger(__name__)

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

# Time-based hash expiry (24 hours)
HASH_EXPIRY_SECONDS = 86400

# GKG Crisis Themes for enhanced detection
GKG_CRISIS_THEMES = [
    "CRISISLEX_CRISISLEXREC",
    "CRISISLEX_T01_CASUALTIES_DAMAGE",
    "TAX_ETHNICITY_VIOLENCE",
    "PROTEST",
    "TERROR",
    "MILITARY",
    "ARMED_CONFLICT",
    "NATURAL_DISASTER",
]


class GDELTTrigger(BaseTrigger):
    """
    GDELT 뉴스 트리거

    키워드 기반으로 전 세계 뉴스 검색 (소스 지정 없음)

    Enhanced Features (v2):
    - GKG Themes: Crisis theme monitoring
    - Goldstein/Tone filter: Conflict intensity filtering
    """

    def __init__(
        self,
        keywords: list[str] | None = None,
        timespan: str = "1h",
        max_results: int = 100,
        use_gkg_themes: bool = False,
        gkg_themes: list[str] | None = None,
        tone_threshold: float | None = None,  # Filter by tone (proxy for Goldstein)
    ):
        super().__init__(keywords)
        self.timespan = timespan
        self.max_results = max_results
        self.use_gkg_themes = use_gkg_themes
        self.gkg_themes = gkg_themes or GKG_CRISIS_THEMES
        self.tone_threshold = tone_threshold  # None = no filter, -5.0 = negative tone
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

        Enhanced: Supports GKG themes and tone filtering.
        """
        self.last_scan = datetime.utcnow()
        events = []

        # Build query based on settings
        query = self._build_query()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                params = {
                    "query": query,
                    "mode": "artlist",
                    "maxrecords": str(self.max_results),
                    "format": "json",
                    "timespan": self.timespan,
                    "sort": "datedesc",
                }

                # Use tone sorting if threshold is set
                if self.tone_threshold is not None:
                    params["sort"] = "toneasc"  # Most negative first

                response = await client.get(GDELT_DOC_API, params=params)
                response.raise_for_status()

                # JSON 응답 확인
                if not response.headers.get("content-type", "").startswith("application/json"):
                    logger.warning(f"GDELT returned non-JSON: {response.text[:100]}")
                    return []

                data = response.json()
                articles = data.get("articles", [])

                current_time = time.time()

                for art in articles:
                    # Apply tone filter if threshold is set
                    if self.tone_threshold is not None:
                        tone = art.get("tone", 0)
                        if tone > self.tone_threshold:
                            continue

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

                    # Determine source marker
                    source_marker = "[gdelt-fulltext]"
                    if self.use_gkg_themes:
                        source_marker = "[gkg-theme]"
                    if self.tone_threshold is not None:
                        source_marker = "[tone-filtered]"

                    # Extract seendate from GDELT response
                    # GDELT uses "seendate" field in format "YYYYMMDDTHHmmssZ"
                    pub_date_str = art.get("seendate", "")
                    try:
                        # Handle format: "20260123T104500Z"
                        clean_date = pub_date_str.replace("T", "").replace("Z", "")
                        seendate = (
                            datetime.strptime(clean_date[:14], "%Y%m%d%H%M%S")
                            if clean_date and len(clean_date) >= 14
                            else datetime.utcnow()
                        )
                    except (ValueError, TypeError):
                        seendate = datetime.utcnow()

                    # Validate article recency using URL date
                    url = art.get("url", "")
                    is_recent, reason, url_date = validate_article_recency(
                        url=url,
                        seendate=seendate,
                        max_age_hours=48,
                        max_discrepancy_hours=72,
                    )

                    if not is_recent:
                        logger.info(f"[GDELT-RECENCY] Rejected: {reason} | {title[:50]}...")
                        continue

                    # Use URL date if available, otherwise seendate
                    detected_at = url_date if url_date else seendate

                    # GDELT가 이미 키워드로 필터링했으므로 모든 기사 포함
                    # 최종 필터링은 significance scoring에서 수행
                    events.append(TriggerEvent(
                        title=title,
                        source=TriggerSource.GDELT,
                        source_name=art.get("domain", "unknown"),
                        url=art.get("url", ""),
                        detected_at=detected_at,
                        language=art.get("language", "en"),
                        country=art.get("sourcecountry", ""),
                        keywords_matched=matched if matched else [source_marker],
                        raw_data={
                            **art,
                            "gkg_themes_enabled": self.use_gkg_themes,
                            "tone_threshold": self.tone_threshold,
                            "url_date": url_date.isoformat() if url_date else None,
                            "seendate_parsed": seendate.isoformat(),
                            "recency_reason": reason,
                        },
                    ))

                # 메모리 관리: 만료된 해시 정리
                self._cleanup_expired_hashes(current_time)

                logger.info(f"GDELT scan: {len(articles)} articles, {len(events)} new")

        except httpx.TimeoutException:
            logger.warning("GDELT API timeout")
        except Exception as e:
            logger.error(f"GDELT scan error: {e}")

        return events

    def _build_query(self) -> str:
        """Build GDELT query string based on settings"""
        query_parts = []

        # Add keyword query
        if self.keywords:
            keyword_query = "(" + " OR ".join(self.keywords[:15]) + ")"
            query_parts.append(keyword_query)

        # Add GKG theme query if enabled
        if self.use_gkg_themes and self.gkg_themes:
            theme_query = "(" + " OR ".join(f"theme:{t}" for t in self.gkg_themes[:5]) + ")"
            query_parts.append(theme_query)

        # Combine with OR if both present
        if len(query_parts) > 1:
            return " OR ".join(query_parts)
        elif query_parts:
            return query_parts[0]
        else:
            return ""

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
