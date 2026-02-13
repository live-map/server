"""
Async Semantic Scholar API wrapper for academic paper search.

Semantic Scholar는 무료 학술 검색 API로,
논문 제목, 초록, 인용 횟수 등을 반환합니다.
"""

import logging

import httpx

from app.services.research.state import SourceItem

logger = logging.getLogger(__name__)

SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"


class SemanticScholarClient:
    """Semantic Scholar 학술 검색 래퍼."""

    async def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[SourceItem]:
        """학술 논문을 검색하고 SourceItem 목록을 반환합니다."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # API 키 없이 요청 (무료 티어, rate limit 주의)
                response = await client.get(
                    f"{SEMANTIC_SCHOLAR_API}/paper/search",
                    params={
                        "query": query,
                        "limit": max_results,
                        "fields": "title,abstract,url,citationCount,year,authors",
                    },
                )
                response.raise_for_status()
                data = response.json()

            sources: list[SourceItem] = []
            for paper in data.get("data", []):
                citation_count = paper.get("citationCount", 0) or 0
                if citation_count > 50:
                    credibility = "HIGH"
                elif citation_count > 10:
                    credibility = "MEDIUM"
                else:
                    credibility = "LOW"

                authors = paper.get("authors", [])
                author_str = ", ".join(
                    a.get("name", "") for a in authors[:3]
                )
                year = paper.get("year", "")
                desc = f"{author_str} ({year})" if author_str else ""

                abstract = paper.get("abstract", "") or ""

                sources.append(
                    SourceItem(
                        title=paper.get("title", ""),
                        url=paper.get("url", "") or f"https://api.semanticscholar.org/paper/{paper.get('paperId', '')}",
                        source_type="PAPER",
                        description=desc,
                        content_snippet=abstract[:500],
                        credibility=credibility,
                    )
                )

            logger.info(f"Semantic Scholar search '{query[:50]}': {len(sources)} results")
            return sources

        except Exception as e:
            logger.error(f"Semantic Scholar search failed for '{query[:50]}': {e}")
            return []
