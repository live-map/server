"""
Fact Check node — Google Fact Check API로 주장을 검증합니다.
"""

import asyncio
import logging

from app.services.research.config import FACT_CHECK_MAX_RESULTS
from app.services.research.state import ResearchState
from app.services.research.tools.fact_check_client import FactCheckClient

logger = logging.getLogger(__name__)


async def fact_check_node(state: ResearchState) -> dict:
    """모든 팩트체크 주장을 병렬로 검증합니다."""
    claims = state.get("fact_check_claims", [])
    if not claims:
        logger.info("[FactCheck] No claims to check, skipping")
        return {"fact_check_results": []}

    logger.info("[FactCheck] Checking %d claims", len(claims))

    client = FactCheckClient()
    tasks = [client.search(claim, max_results=FACT_CHECK_MAX_RESULTS) for claim in claims]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_results: list[dict] = []
    for result in results:
        if isinstance(result, Exception):
            logger.error("[FactCheck] Claim check failed: %s", result)
            continue
        all_results.extend(result)

    logger.info("[FactCheck] Found %d fact check entries", len(all_results))
    return {"fact_check_results": all_results}
