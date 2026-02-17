"""
Async Google Fact Check Tools API wrapper.

Google Fact Check API는 주요 팩트체크 기관의
검증 결과를 검색할 수 있는 무료 API입니다.
"""

import logging

import httpx

from app.services.research.config import ai_settings

logger = logging.getLogger(__name__)

FACT_CHECK_API = "https://factchecktools.googleapis.com/v1alpha1/claims:search"


class FactCheckClient:
    """Google Fact Check API 래퍼."""

    async def search(
        self,
        query: str,
        max_results: int = 5,
        language_code: str = "ko",
    ) -> list[dict]:
        """팩트체크 결과를 검색합니다."""
        if not ai_settings.GOOGLE_FACT_CHECK_API_KEY:
            logger.debug("Google Fact Check API key not configured, skipping")
            return []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    FACT_CHECK_API,
                    params={
                        "key": ai_settings.GOOGLE_FACT_CHECK_API_KEY,
                        "query": query,
                        "pageSize": max_results,
                        "languageCode": language_code,
                    },
                )
                response.raise_for_status()
                data = response.json()

            results: list[dict] = []
            for claim in data.get("claims", []):
                reviews = claim.get("claimReview", [])
                review = reviews[0] if reviews else {}

                results.append({
                    "claim_text": claim.get("text", ""),
                    "claimant": claim.get("claimant", ""),
                    "rating": review.get("textualRating", ""),
                    "publisher": review.get("publisher", {}).get("name", ""),
                    "url": review.get("url", ""),
                    "title": review.get("title", ""),
                })

            logger.info("Fact Check search '%s': %d results", query[:50], len(results))
            return results

        except Exception as e:
            logger.error("Fact Check search failed for '%s': %s", query[:50], e)
            return []
