"""
Google Fact Check Tools API client.

Searches for existing fact-checks on claims from reputable publishers.

API: https://developers.google.com/fact-check/tools/api
"""

from dataclasses import dataclass, field

import httpx

from app.config import settings

API_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"


@dataclass
class FactCheckSource:
    """A fact-check source."""

    publisher: str
    url: str
    rating: str
    title: str | None = None


@dataclass
class GoogleFactCheckResult:
    """Result from Google Fact Check API."""

    has_fact_check: bool
    matched_claim: str | None = None
    ratings: list[str] = field(default_factory=list)
    sources: list[FactCheckSource] = field(default_factory=list)
    error: str | None = None


async def search_fact_checks(
    query: str,
    api_key: str | None = None,
    language_code: str = "en",
    max_age_days: int | None = None,
    page_size: int = 5,
    timeout: float = 30.0,
) -> GoogleFactCheckResult:
    """
    Search for existing fact-checks on a claim.

    Args:
        query: Claim text to search
        api_key: Google API key (uses settings if not provided)
        language_code: BCP-47 language code (e.g., "en", "ko")
        max_age_days: Maximum age of results in days
        page_size: Number of results to return
        timeout: Request timeout in seconds

    Returns:
        GoogleFactCheckResult with matching fact-checks
    """
    api_key = api_key or settings.GOOGLE_API_KEY

    if not api_key:
        return GoogleFactCheckResult(
            has_fact_check=False,
            error="Google API key not configured",
        )

    params = {
        "key": api_key,
        "query": query[:500],  # Limit query length
        "languageCode": language_code,
        "pageSize": page_size,
    }

    if max_age_days:
        params["maxAgeDays"] = max_age_days

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(API_URL, params=params)
            response.raise_for_status()

            data = response.json()
            claims = data.get("claims", [])

            if not claims:
                return GoogleFactCheckResult(has_fact_check=False)

            # Process the first (most relevant) claim
            first_claim = claims[0]
            ratings = []
            sources = []

            for review in first_claim.get("claimReview", []):
                rating = review.get("textualRating", "Unknown")
                ratings.append(rating)

                publisher_info = review.get("publisher", {})
                sources.append(
                    FactCheckSource(
                        publisher=publisher_info.get("name", "Unknown"),
                        url=review.get("url", ""),
                        rating=rating,
                        title=review.get("title"),
                    )
                )

            return GoogleFactCheckResult(
                has_fact_check=True,
                matched_claim=first_claim.get("text"),
                ratings=ratings,
                sources=sources,
            )

    except httpx.TimeoutException:
        return GoogleFactCheckResult(
            has_fact_check=False,
            error="Google Fact Check API timeout",
        )
    except httpx.HTTPStatusError as e:
        return GoogleFactCheckResult(
            has_fact_check=False,
            error=f"Google Fact Check API error: {e.response.status_code}",
        )
    except Exception as e:
        return GoogleFactCheckResult(
            has_fact_check=False,
            error=f"Google Fact Check error: {str(e)}",
        )


def interpret_rating(rating: str) -> float:
    """
    Convert textual rating to numerical confidence score.

    Returns:
        0.0 = False/Fake
        0.5 = Mixed/Partly True
        1.0 = True/Verified
    """
    rating_lower = rating.lower()

    # False ratings
    if any(word in rating_lower for word in ["false", "fake", "pants on fire", "incorrect", "wrong"]):
        return 0.0

    # Mostly false
    if any(word in rating_lower for word in ["mostly false", "mostly wrong"]):
        return 0.2

    # Mixed/Half true
    if any(word in rating_lower for word in ["half true", "mixed", "partly", "partially"]):
        return 0.5

    # Mostly true
    if any(word in rating_lower for word in ["mostly true", "mostly correct"]):
        return 0.8

    # True ratings
    if any(word in rating_lower for word in ["true", "correct", "verified", "accurate"]):
        return 1.0

    # Unknown
    return 0.5
