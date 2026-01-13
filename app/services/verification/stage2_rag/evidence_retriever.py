"""
Evidence retriever using SearXNG.

신규 뉴스 교차 검증을 위한 증거 검색:
- 다른 뉴스 소스에서 같은 사건 보도 확인
- 신뢰 소스 가중치 적용
- 최근 뉴스 우선 (시간 기반 점수)
"""

import logging
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.services.verification.stage2_rag.models import Evidence

logger = logging.getLogger(__name__)


class EvidenceRetriever:
    """Retrieve evidence from SearXNG for news cross-verification."""

    # Tier 1: 최고 신뢰 소스 (국제 통신사, 공영 방송)
    TIER1_DOMAINS = [
        "reuters.com",
        "apnews.com",
        "afp.com",
        "bbc.com",
        "bbc.co.uk",
    ]

    # Tier 2: 높은 신뢰 소스 (주요 언론사)
    TIER2_DOMAINS = [
        "nytimes.com",
        "theguardian.com",
        "washingtonpost.com",
        "aljazeera.com",
        "france24.com",
        "dw.com",
        "cnn.com",
        "npr.org",
        "pbs.org",
        "economist.com",
    ]

    # Tier 3: 신뢰 소스 (지역/전문 언론)
    TIER3_DOMAINS = [
        "kyivindependent.com",
        "timesofisrael.com",
        "jpost.com",
        "scmp.com",
        "japantimes.co.jp",
        "straitstimes.com",
    ]

    def __init__(self, searxng_url: str | None = None):
        self.searxng_url = searxng_url or getattr(
            settings, "SEARXNG_URL", "http://localhost:8888"
        )

    def _get_source_tier(self, url: str) -> int:
        """Get source trust tier (1=highest, 4=unknown)."""
        url_lower = url.lower()
        if any(domain in url_lower for domain in self.TIER1_DOMAINS):
            return 1
        elif any(domain in url_lower for domain in self.TIER2_DOMAINS):
            return 2
        elif any(domain in url_lower for domain in self.TIER3_DOMAINS):
            return 3
        return 4

    def _is_trusted_source(self, url: str) -> bool:
        """Check if URL is from a trusted source (Tier 1-3)."""
        return self._get_source_tier(url) <= 3

    def _calculate_freshness_score(self, published_date: datetime | None) -> float:
        """
        Calculate freshness score based on publication time.

        신규 뉴스 검증이므로 최근 뉴스에 높은 점수:
        - 24시간 이내: 1.0
        - 48시간 이내: 0.8
        - 7일 이내: 0.5
        - 그 이상: 0.2
        """
        if not published_date:
            return 0.3  # 날짜 없으면 중간 점수

        try:
            now = datetime.now(timezone.utc)
            if published_date.tzinfo is None:
                published_date = published_date.replace(tzinfo=timezone.utc)

            hours_ago = (now - published_date).total_seconds() / 3600

            if hours_ago <= 24:
                return 1.0
            elif hours_ago <= 48:
                return 0.8
            elif hours_ago <= 168:  # 7일
                return 0.5
            else:
                return 0.2
        except Exception:
            return 0.3

    def _calculate_relevance(self, result: dict, published_date: datetime | None) -> float:
        """
        Calculate relevance score for cross-source verification.

        점수 구성:
        - 소스 신뢰도: 0.4 (Tier 기반)
        - 시간 신선도: 0.4 (최근 뉴스 우선)
        - 검색 점수: 0.2 (SearXNG 점수)
        """
        url = result.get("url", "")
        tier = self._get_source_tier(url)

        # 소스 신뢰도 점수 (0-0.4)
        tier_scores = {1: 0.4, 2: 0.35, 3: 0.25, 4: 0.1}
        source_score = tier_scores.get(tier, 0.1)

        # 시간 신선도 점수 (0-0.4)
        freshness = self._calculate_freshness_score(published_date) * 0.4

        # 검색 엔진 점수 (0-0.2)
        engine_score = 0.1
        if result.get("score"):
            engine_score = min(result["score"] / 10, 0.2)

        return min(source_score + freshness + engine_score, 1.0)

    def _parse_date(self, date_str: str | None) -> datetime | None:
        """Parse date string from search result."""
        if not date_str:
            return None
        try:
            # Try common formats
            for fmt in ["%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                try:
                    return datetime.strptime(date_str[:26], fmt)
                except ValueError:
                    continue
            return None
        except Exception:
            return None

    async def search(
        self,
        query: str,
        num_results: int = 10,
        categories: str = "news",
    ) -> list[Evidence]:
        """
        Search for evidence using SearXNG.

        Args:
            query: Search query (the claim to verify)
            num_results: Maximum number of results
            categories: SearXNG categories (news, general, etc.)

        Returns:
            List of Evidence objects
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.searxng_url}/search",
                    params={
                        "q": query,
                        "format": "json",
                        "categories": categories,
                    },
                )
                response.raise_for_status()
                data = response.json()

        except httpx.HTTPError as e:
            logger.error(f"SearXNG search failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in search: {e}")
            return []

        results = data.get("results", [])
        evidences = []

        for result in results[:num_results]:
            url = result.get("url", "")
            published_date = self._parse_date(result.get("publishedDate"))
            is_trusted = self._is_trusted_source(url)
            relevance = self._calculate_relevance(result, published_date)
            tier = self._get_source_tier(url)

            evidence = Evidence(
                text=result.get("content", ""),
                source=result.get("engine", "unknown"),
                url=url,
                title=result.get("title", ""),
                published_date=published_date,
                relevance_score=relevance,
                is_trusted_source=is_trusted,
                source_tier=tier,
            )
            evidences.append(evidence)

        # Sort by relevance (신뢰 소스 + 최근 뉴스 우선)
        evidences.sort(key=lambda x: x.relevance_score, reverse=True)

        return evidences

    async def search_multiple_queries(
        self,
        queries: list[str],
        num_results_per_query: int = 5,
    ) -> list[Evidence]:
        """
        Search with multiple query variations.

        Useful for finding more diverse evidence.
        """
        all_evidences = []
        seen_urls = set()

        for query in queries:
            evidences = await self.search(query, num_results_per_query)
            for evidence in evidences:
                if evidence.url not in seen_urls:
                    seen_urls.add(evidence.url)
                    all_evidences.append(evidence)

        # Sort by relevance
        all_evidences.sort(key=lambda x: x.relevance_score, reverse=True)

        return all_evidences
