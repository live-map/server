"""
Stage 3 Pipeline: LLM verification.

Uses Mistral Small for deep analysis of claims that:
- Passed Stage 1 (has location, not duplicate, minimum quality)
- Passed Stage 2 without conclusive fact-check (confidence < 0.85)

Cost: ~$0.00014 per verification
"""

from dataclasses import dataclass, field

from app.services.verification.stage3 import mistral
from app.services.verification.stage3.mistral import Verdict


@dataclass
class Stage3Result:
    """Complete Stage 3 verification result."""

    # Verdict
    verdict: Verdict
    confidence: float
    reasoning: str

    # Details
    key_facts: list[str] = field(default_factory=list)
    sources_needed: list[str] = field(default_factory=list)

    # Metadata
    tokens_used: int = 0
    error: str | None = None

    # Final credibility score (0-100)
    credibility_score: int = 50


def calculate_credibility_score(verdict: Verdict, confidence: float) -> int:
    """
    Calculate final credibility score (0-100) from verdict and confidence.

    Mapping:
    - TRUE with high confidence → 80-100
    - PARTIALLY_TRUE → 40-70
    - UNVERIFIABLE → 30-50
    - FALSE with high confidence → 0-20
    """
    if verdict == Verdict.TRUE:
        return int(70 + confidence * 30)  # 70-100
    elif verdict == Verdict.PARTIALLY_TRUE:
        return int(40 + confidence * 30)  # 40-70
    elif verdict == Verdict.UNVERIFIABLE:
        return int(30 + confidence * 20)  # 30-50
    else:  # FALSE
        return int((1 - confidence) * 20)  # 0-20


async def run_stage3(
    text: str,
    context: str | None = None,
    api_key: str | None = None,
) -> Stage3Result:
    """
    Run Stage 3 LLM verification.

    Args:
        text: Text content to verify
        context: Optional context (location, source info, etc.)
        api_key: Optional Mistral API key

    Returns:
        Stage3Result with verdict and credibility score
    """
    result = await mistral.verify_claim(
        text=text,
        context=context,
        api_key=api_key,
    )

    credibility_score = calculate_credibility_score(result.verdict, result.confidence)

    return Stage3Result(
        verdict=result.verdict,
        confidence=result.confidence,
        reasoning=result.reasoning,
        key_facts=result.key_facts,
        sources_needed=result.sources_needed,
        tokens_used=result.tokens_used,
        error=result.error,
        credibility_score=credibility_score,
    )
