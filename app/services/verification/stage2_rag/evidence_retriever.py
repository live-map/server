"""
Evidence retriever using SearXNG.

Searches news and web for evidence related to a claim.
"""

import logging
from datetime import datetime

import httpx

from app.config import settings
from app.services.verification.stage2_rag.models import Evidence

logger = logging.getLogger(__name__)


class EvidenceRetriever:
    """Retrieve evidence from SearXNG for claim verification."""

    # Trusted news sources for higher relevance scoring
    TRUSTED_DOMAINS = [
        "reuters.com",
        "apnews.com",
        "afp.com",
        "bbc.com",
        "bbc.co.uk",
        "nytimes.com",
        "theguardian.com",
        "washingtonpost.com",
        "aljazeera.com",
        "france24.com",
        "dw.com",
        "wikipedia.org",
    ]

    def __init__(self, searxng_url: str | None = None):
        self.searxng_url = searxng_url or getattr(
            settings, "SEARXNG_URL", "http://localhost:8888"
        )

    def _is_trusted_source(self, url: str) -> bool:
        """Check if URL is from a trusted source."""
        return any(domain in url.lower() for domain in self.TRUSTED_DOMAINS)

    def _calculate_relevance(self, result: dict, is_trusted: bool) -> float:
        """Calculate relevance score for a search result."""
        score = 0.5

        # Boost for trusted sources
        if is_trusted:
            score += 0.3

        # Boost for recent content
        if result.get("publishedDate"):
            score += 0.1

        # Boost based on search engine score if available
        if result.get("score"):
            score += min(result["score"] / 10, 0.1)

        return min(score, 1.0)

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
            is_trusted = self._is_trusted_source(url)
            relevance = self._calculate_relevance(result, is_trusted)

            evidence = Evidence(
                text=result.get("content", ""),
                source=result.get("engine", "unknown"),
                url=url,
                title=result.get("title", ""),
                published_date=self._parse_date(result.get("publishedDate")),
                relevance_score=relevance,
                is_trusted_source=is_trusted,
            )
            evidences.append(evidence)

        # Sort by relevance (trusted sources first)
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
