"""
Claim Extraction Module (VeriScore Style)

Extracts verifiable factual claims from text using LLM.
Based on VeriScore and SAFE (Search-Augmented Factuality Evaluator) approaches.

Key Features:
- Atomic claim extraction (one fact per claim)
- Decontextualization (pronouns → proper nouns)
- Filters out opinions, predictions, and subjective statements
- Only extracts verifiable claims

References:
- VeriScore: https://github.com/Yixiao-Song/VeriScore
- SAFE: https://github.com/google-deepmind/long-form-factuality
"""

from __future__ import annotations

import logging
import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from .config import agent_settings

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================


class ExtractedClaim(BaseModel):
    """Individual extracted claim."""

    id: str = Field(description="Unique claim identifier")
    text: str = Field(description="Decontextualized claim text")
    original_span: str = Field(description="Original text span from input")
    claim_type: Literal["factual", "opinion", "prediction"] = Field(
        default="factual",
        description="Type of claim",
    )
    is_verifiable: bool = Field(
        default=True,
        description="Whether the claim can be verified against external sources",
    )


class ClaimExtractionResult(BaseModel):
    """Result of claim extraction."""

    claims: list[ExtractedClaim] = Field(default_factory=list)
    total_extracted: int = Field(default=0)
    verifiable_count: int = Field(default=0)
    filtered_count: int = Field(default=0)
    original_text: str = Field(default="")


# =============================================================================
# Prompts
# =============================================================================

CLAIM_EXTRACTION_SYSTEM_PROMPT = """You are a fact-checking assistant specialized in extracting verifiable claims from text.

Your task is to extract ONLY factual claims that can be verified against external sources.

## RULES

1. **Extract atomic claims**: Each claim should contain exactly ONE verifiable fact
2. **Decontextualize**: Replace all pronouns with the actual entities they refer to
   - "He said..." → "President Biden said..."
   - "The country..." → "Ukraine..."
3. **Include specifics**: Keep numbers, dates, names, and locations
4. **EXCLUDE these types**:
   - Opinions: "I think...", "It seems...", "arguably..."
   - Predictions: "will happen", "is expected to", "may..."
   - Hypotheticals: "if...", "would...", "could..."
   - Subjective: "best", "worst", "beautiful", "important"
   - Vague claims: claims without specific verifiable details

## EXAMPLES

INPUT: "The president announced yesterday that inflation reached 3.5% in December. He believes the economy is improving."

GOOD EXTRACTION:
- Claim 1: "The president announced on [date] that inflation reached 3.5% in December" (factual, verifiable)
- EXCLUDED: "He believes the economy is improving" (opinion, not verifiable)

INPUT: "Tesla stock dropped 15% after Elon Musk tweeted about selling shares. Analysts think it will recover."

GOOD EXTRACTION:
- Claim 1: "Tesla stock dropped 15% after Elon Musk tweeted about selling shares" (factual, verifiable)
- EXCLUDED: "Analysts think it will recover" (prediction, not verifiable)

## OUTPUT FORMAT

For each claim, output in this exact format:
CLAIM: [decontextualized claim text]
ORIGINAL: [original text span]
TYPE: factual|opinion|prediction
VERIFIABLE: yes|no

Only output claims that are TYPE: factual and VERIFIABLE: yes in the final list."""

CLAIM_EXTRACTION_USER_PROMPT = """Extract all verifiable factual claims from the following text.

TEXT:
{text}

Remember:
1. Make each claim atomic (one fact only)
2. Decontextualize (replace pronouns with actual names/entities)
3. Only include factual, verifiable claims
4. Exclude opinions, predictions, and subjective statements

Extract claims:"""


# =============================================================================
# Claim Extractor
# =============================================================================


class ClaimExtractor:
    """
    Extracts verifiable claims from text using LLM.

    Based on VeriScore methodology:
    1. Extract all potential claims
    2. Decontextualize (resolve pronouns)
    3. Filter to only verifiable factual claims
    """

    def __init__(
        self,
        model: str | None = None,
        temperature: float = 0.0,
    ):
        self.model = model or agent_settings.llm_model
        self.llm = ChatOpenAI(
            model=self.model,
            temperature=temperature,
            api_key=agent_settings.openai_api_key,
        )

    async def extract(self, text: str) -> ClaimExtractionResult:
        """
        Extract verifiable claims from text.

        Args:
            text: Input text to extract claims from

        Returns:
            ClaimExtractionResult with extracted claims
        """
        if not text or len(text.strip()) < 10:
            logger.warning("Input text too short for claim extraction")
            return ClaimExtractionResult(original_text=text)

        logger.info(
            "Extracting claims",
            extra={"text_length": len(text)},
        )

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=CLAIM_EXTRACTION_SYSTEM_PROMPT),
                HumanMessage(
                    content=CLAIM_EXTRACTION_USER_PROMPT.format(text=text)
                ),
            ])

            claims = self._parse_claims(response.content)
            verifiable_claims = [c for c in claims if c.is_verifiable]

            result = ClaimExtractionResult(
                claims=verifiable_claims,
                total_extracted=len(claims),
                verifiable_count=len(verifiable_claims),
                filtered_count=len(claims) - len(verifiable_claims),
                original_text=text,
            )

            logger.info(
                "Claim extraction complete",
                extra={
                    "total": result.total_extracted,
                    "verifiable": result.verifiable_count,
                    "filtered": result.filtered_count,
                },
            )

            return result

        except Exception as e:
            logger.error(f"Claim extraction failed: {e}")
            return ClaimExtractionResult(original_text=text)

    def _parse_claims(self, content: str) -> list[ExtractedClaim]:
        """Parse LLM response into structured claims."""
        claims: list[ExtractedClaim] = []
        current_claim: dict = {}
        claim_counter = 0

        for line in content.split("\n"):
            line = line.strip()

            if line.startswith("CLAIM:"):
                # Save previous claim if exists
                if current_claim.get("text"):
                    claim_counter += 1
                    claims.append(self._create_claim(current_claim, claim_counter))
                # Start new claim
                current_claim = {"text": line[6:].strip()}

            elif line.startswith("ORIGINAL:"):
                current_claim["original_span"] = line[9:].strip()

            elif line.startswith("TYPE:"):
                type_text = line[5:].strip().lower()
                if type_text in ("factual", "opinion", "prediction"):
                    current_claim["claim_type"] = type_text

            elif line.startswith("VERIFIABLE:"):
                verifiable_text = line[11:].strip().lower()
                current_claim["is_verifiable"] = verifiable_text == "yes"

        # Save last claim
        if current_claim.get("text"):
            claim_counter += 1
            claims.append(self._create_claim(current_claim, claim_counter))

        return claims

    def _create_claim(self, data: dict, index: int) -> ExtractedClaim:
        """Create ExtractedClaim from parsed data."""
        return ExtractedClaim(
            id=f"claim_{index:03d}",
            text=data.get("text", ""),
            original_span=data.get("original_span", data.get("text", "")),
            claim_type=data.get("claim_type", "factual"),
            is_verifiable=data.get("is_verifiable", True),
        )


# =============================================================================
# Utility Functions
# =============================================================================


async def extract_claims(text: str) -> list[ExtractedClaim]:
    """
    Convenience function to extract claims from text.

    Args:
        text: Input text

    Returns:
        List of verifiable claims
    """
    extractor = ClaimExtractor()
    result = await extractor.extract(text)
    return result.claims


def filter_verifiable_claims(claims: list[ExtractedClaim]) -> list[ExtractedClaim]:
    """Filter to only verifiable factual claims."""
    return [
        c for c in claims
        if c.is_verifiable and c.claim_type == "factual"
    ]


def decontextualize_claim(claim: str, context: dict[str, str]) -> str:
    """
    Replace pronouns with actual entities.

    Args:
        claim: Claim text with potential pronouns
        context: Mapping of pronouns to entities

    Returns:
        Decontextualized claim
    """
    result = claim
    for pronoun, entity in context.items():
        # Case-insensitive replacement
        pattern = re.compile(re.escape(pronoun), re.IGNORECASE)
        result = pattern.sub(entity, result)
    return result
