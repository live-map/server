"""
Mistral AI client for news verification.

Uses Mistral Small for cost-effective LLM-based fact-checking.
- Model: mistral-small-latest
- Pricing: ~$0.10/1M input, ~$0.30/1M output tokens
"""

import json
from dataclasses import dataclass
from enum import Enum

from mistralai import Mistral

from app.config import settings


# Singleton client instance
_mistral_client: Mistral | None = None


def get_mistral_client(api_key: str | None = None) -> Mistral | None:
    """Get or create the Mistral client singleton."""
    global _mistral_client
    key = api_key or settings.MISTRAL_API_KEY

    if not key:
        return None

    if _mistral_client is None:
        _mistral_client = Mistral(api_key=key)

    return _mistral_client


class Verdict(str, Enum):
    """Verification verdict."""

    TRUE = "TRUE"
    FALSE = "FALSE"
    PARTIALLY_TRUE = "PARTIALLY_TRUE"
    UNVERIFIABLE = "UNVERIFIABLE"


@dataclass
class MistralVerificationResult:
    """Result from Mistral verification."""

    verdict: Verdict
    confidence: float  # 0.0-1.0
    reasoning: str
    key_facts: list[str]
    sources_needed: list[str]
    tokens_used: int
    error: str | None = None


SYSTEM_PROMPT = """You are a professional fact-checker analyzing news claims about military conflicts and security events.

Your task is to verify claims and provide structured analysis.

Guidelines:
1. Be objective and avoid political bias
2. Focus on verifiable facts
3. Consider the source reliability
4. Note any missing context
5. Identify what would be needed to fully verify

Respond ONLY with valid JSON in this exact format:
{
  "verdict": "TRUE" | "FALSE" | "PARTIALLY_TRUE" | "UNVERIFIABLE",
  "confidence": 0.0 to 1.0,
  "reasoning": "Brief explanation of your verdict",
  "key_facts": ["List of verified facts relevant to the claim"],
  "sources_needed": ["List of sources that would help verify this claim"]
}"""


async def verify_claim(
    text: str,
    context: str | None = None,
    api_key: str | None = None,
    model: str = "mistral-small-latest",
    temperature: float = 0.1,
    max_tokens: int = 500,
) -> MistralVerificationResult:
    """
    Verify a news claim using Mistral LLM.

    Args:
        text: The claim/news text to verify
        context: Optional additional context (location, source, etc.)
        api_key: Mistral API key (uses settings if not provided)
        model: Model to use (default: mistral-small-latest)
        temperature: Generation temperature (lower = more consistent)
        max_tokens: Maximum tokens for response

    Returns:
        MistralVerificationResult with verdict and analysis
    """
    client = get_mistral_client(api_key)

    if not client:
        return MistralVerificationResult(
            verdict=Verdict.UNVERIFIABLE,
            confidence=0.0,
            reasoning="Mistral API key not configured",
            key_facts=[],
            sources_needed=[],
            tokens_used=0,
            error="Mistral API key not configured",
        )

    # Build user message
    user_message = f"Verify this claim:\n\n{text}"
    if context:
        user_message += f"\n\nAdditional context:\n{context}"

    try:

        response = await client.chat.complete_async(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )

        # Parse response
        content = response.choices[0].message.content
        tokens_used = response.usage.total_tokens if response.usage else 0

        try:
            data = json.loads(content)
            return MistralVerificationResult(
                verdict=Verdict(data.get("verdict", "UNVERIFIABLE")),
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", ""),
                key_facts=data.get("key_facts", []),
                sources_needed=data.get("sources_needed", []),
                tokens_used=tokens_used,
            )
        except (json.JSONDecodeError, ValueError) as e:
            return MistralVerificationResult(
                verdict=Verdict.UNVERIFIABLE,
                confidence=0.5,
                reasoning=content,  # Return raw content as reasoning
                key_facts=[],
                sources_needed=[],
                tokens_used=tokens_used,
                error=f"Failed to parse response: {str(e)}",
            )

    except Exception as e:
        return MistralVerificationResult(
            verdict=Verdict.UNVERIFIABLE,
            confidence=0.0,
            reasoning="",
            key_facts=[],
            sources_needed=[],
            tokens_used=0,
            error=f"Mistral API error: {str(e)}",
        )
