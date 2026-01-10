"""
ClaimBuster API client for check-worthiness scoring.

Scores claims on a 0-1 scale:
- 0.0-0.3: Low check-worthiness (opinions, greetings)
- 0.3-0.6: Moderate check-worthiness
- 0.6-1.0: High check-worthiness (factual claims)

API: https://idir.uta.edu/claimbuster/
"""

from dataclasses import dataclass

import httpx

from app.config import settings

API_URL = "https://idir.uta.edu/claimbuster/api/v2/score/text/"
CHECK_WORTHY_THRESHOLD = 0.5


@dataclass
class ClaimBusterResult:
    """Result from ClaimBuster API."""

    score: float  # 0.0-1.0
    is_check_worthy: bool
    error: str | None = None


async def score_claim(
    text: str,
    api_key: str | None = None,
    timeout: float = 30.0,
) -> ClaimBusterResult:
    """
    Score a claim for check-worthiness using ClaimBuster API.

    Args:
        text: Claim text to analyze
        api_key: ClaimBuster API key (optional, uses settings if not provided)
        timeout: Request timeout in seconds

    Returns:
        ClaimBusterResult with score
    """
    api_key = api_key or getattr(settings, "CLAIMBUSTER_API_KEY", "")

    if not api_key:
        return ClaimBusterResult(
            score=0.5,  # Neutral score when API unavailable
            is_check_worthy=True,
            error="ClaimBuster API key not configured",
        )

    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    payload = {"input_text": text[:2000]}  # Limit text length

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(API_URL, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])

            if results:
                score = results[0].get("score", 0.5)
                return ClaimBusterResult(
                    score=score,
                    is_check_worthy=score >= CHECK_WORTHY_THRESHOLD,
                )

            return ClaimBusterResult(
                score=0.5,
                is_check_worthy=True,
                error="No results from ClaimBuster",
            )

    except httpx.TimeoutException:
        return ClaimBusterResult(
            score=0.5,
            is_check_worthy=True,
            error="ClaimBuster API timeout",
        )
    except httpx.HTTPStatusError as e:
        return ClaimBusterResult(
            score=0.5,
            is_check_worthy=True,
            error=f"ClaimBuster API error: {e.response.status_code}",
        )
    except Exception as e:
        return ClaimBusterResult(
            score=0.5,
            is_check_worthy=True,
            error=f"ClaimBuster error: {str(e)}",
        )
