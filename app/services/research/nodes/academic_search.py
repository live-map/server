"""
Academic Search node — Semantic Scholar로 학술 논문을 검색합니다.
"""

import asyncio
import logging

from app.services.research.state import ResearchState, SourceItem
from app.services.research.tools.semantic_scholar import SemanticScholarClient

logger = logging.getLogger(__name__)


async def academic_search_node(state: ResearchState) -> dict:
    """학술 검색 쿼리를 순차 실행합니다 (rate limit 방지)."""
    queries = state.get("academic_queries", [])
    if not queries:
        logger.info("[AcademicSearch] No academic queries, skipping")
        return {"academic_sources": []}

    logger.info("[AcademicSearch] Searching %d queries (sequential)", len(queries))

    client = SemanticScholarClient()
    all_sources: list[SourceItem] = []
    seen_urls: set[str] = set()

    for i, query in enumerate(queries):
        try:
            results = await client.search(query, max_results=3)
            for source in results:
                if source["url"] not in seen_urls:
                    seen_urls.add(source["url"])
                    all_sources.append(source)
        except Exception as e:
            logger.error("[AcademicSearch] Query failed: %s", e)

        # rate limit 방지: 쿼리 간 1초 대기
        if i < len(queries) - 1:
            await asyncio.sleep(1)

    logger.info("[AcademicSearch] Collected %d unique papers", len(all_sources))
    return {"academic_sources": all_sources}
