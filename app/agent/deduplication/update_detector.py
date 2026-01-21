"""
Update Detector for news events.

Determines if new information about an existing event warrants a new article.

Update types:
- NEW_DEVELOPMENT: New actions, reactions, statements
- CASUALTY_UPDATE: Changes in casualty/damage numbers
- STATUS_CHANGE: Ceasefire, escalation, resolution
- GEOGRAPHIC_EXPANSION: Event spreads to new locations
- DUPLICATE: No new significant information

Uses LLM-based comparison when facts differ significantly.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.agent.config import agent_settings

if TYPE_CHECKING:
    from app.models.event import Event

logger = logging.getLogger(__name__)


class UpdateType(str, Enum):
    """Type of update for follow-up articles."""

    NEW_DEVELOPMENT = "new_development"
    CASUALTY_UPDATE = "casualty_update"
    STATUS_CHANGE = "status_change"
    GEOGRAPHIC_EXPANSION = "geographic_expansion"
    DUPLICATE = "duplicate"


@dataclass
class UpdateCheckResult:
    """Result of update detection check."""

    is_update: bool
    update_type: UpdateType
    reason: str
    new_facts: list[str] = field(default_factory=list)
    confidence: float = 0.0

    @property
    def should_generate_article(self) -> bool:
        """Whether this update warrants a new article."""
        return self.is_update and self.update_type != UpdateType.DUPLICATE


UPDATE_DETECTION_PROMPT = """You are a news editor analyzing whether new information about an event warrants a follow-up article.

## EXISTING EVENT
Title: {existing_title}
Key Facts:
{existing_facts}

## NEW INFORMATION
{new_text}

## TASK
Determine if the new information contains SIGNIFICANT UPDATES that warrant a new article.

Significant updates include:
1. NEW_DEVELOPMENT - New actions, reactions, official statements, decisions
2. CASUALTY_UPDATE - Changes in casualty/damage numbers (>10% change or new category)
3. STATUS_CHANGE - Ceasefire, escalation, de-escalation, resolution
4. GEOGRAPHIC_EXPANSION - Event spreads to new locations

NOT significant (DUPLICATE):
- Same information rephrased
- Minor clarifications
- Information already covered
- Speculation without new facts

## OUTPUT FORMAT (JSON only)
{{
    "update_type": "new_development|casualty_update|status_change|geographic_expansion|duplicate",
    "is_update": true/false,
    "reason": "Brief explanation",
    "new_facts": ["list", "of", "new", "facts"],
    "confidence": 0.0-1.0
}}

Respond with JSON only:"""


class UpdateDetector:
    """
    Detects if new information warrants a follow-up article.

    Uses:
    1. Fast hash comparison for exact duplicates
    2. LLM-based analysis for semantic comparison
    """

    def __init__(
        self,
        model: str | None = None,
        temperature: float = 0.1,
        llm_timeout: float = 30.0,
    ):
        self.model = model or agent_settings.llm_model
        self.llm_timeout = llm_timeout
        self.llm = ChatOpenAI(
            model=self.model,
            temperature=temperature,
            api_key=agent_settings.openai_api_key,
        )

    async def check_for_update(
        self,
        existing_event: "Event",
        new_text: str,
        new_facts: list[str] | None = None,
    ) -> UpdateCheckResult:
        """
        Check if new information warrants an update article.

        Args:
            existing_event: The existing event in database
            new_text: New event text/description
            new_facts: Pre-extracted facts (optional)

        Returns:
            UpdateCheckResult with decision and details
        """
        # Layer 1: Hash comparison for exact duplicates
        if new_facts:
            new_fact_hash = self._generate_fact_hash(new_facts)
            if new_fact_hash == existing_event.fact_hash:
                logger.info("Exact fact hash match - duplicate")
                return UpdateCheckResult(
                    is_update=False,
                    update_type=UpdateType.DUPLICATE,
                    reason="Identical facts to existing event",
                    confidence=1.0,
                )

        # Layer 2: LLM-based analysis
        try:
            result = await self._llm_update_check(existing_event, new_text)
            return result
        except Exception as e:
            logger.error(f"LLM update check failed: {e}")
            # Fallback: assume it's an update if LLM fails
            return UpdateCheckResult(
                is_update=True,
                update_type=UpdateType.NEW_DEVELOPMENT,
                reason=f"LLM check failed, defaulting to update: {e}",
                confidence=0.5,
            )

    async def _llm_update_check(
        self,
        existing_event: "Event",
        new_text: str,
    ) -> UpdateCheckResult:
        """Use LLM to determine if new information is significant."""
        # Parse existing facts
        existing_facts = []
        if existing_event.key_facts:
            try:
                existing_facts = json.loads(existing_event.key_facts)
            except json.JSONDecodeError:
                existing_facts = [existing_event.key_facts]

        existing_facts_str = "\n".join([f"- {f}" for f in existing_facts]) or "No facts recorded"

        prompt = UPDATE_DETECTION_PROMPT.format(
            existing_title=existing_event.canonical_title,
            existing_facts=existing_facts_str,
            new_text=new_text[:2000],  # Limit length
        )

        try:
            response = await asyncio.wait_for(
                self.llm.ainvoke([
                    SystemMessage(content="You are a news editor. Respond with JSON only."),
                    HumanMessage(content=prompt),
                ]),
                timeout=self.llm_timeout,
            )

            # Parse response
            result = self._parse_response(response.content)
            return result

        except asyncio.TimeoutError:
            logger.error(f"LLM timeout after {self.llm_timeout}s")
            raise

    def _parse_response(self, content: str) -> UpdateCheckResult:
        """Parse LLM JSON response."""
        try:
            # Clean response (remove markdown code blocks if present)
            content = content.strip()
            if content.startswith("```"):
                content = re.sub(r'^```\w*\n?', '', content)
                content = re.sub(r'\n?```$', '', content)

            data = json.loads(content)

            update_type_str = data.get("update_type", "duplicate").lower()
            try:
                update_type = UpdateType(update_type_str)
            except ValueError:
                update_type = UpdateType.DUPLICATE

            return UpdateCheckResult(
                is_update=data.get("is_update", False),
                update_type=update_type,
                reason=data.get("reason", "No reason provided"),
                new_facts=data.get("new_facts", []),
                confidence=float(data.get("confidence", 0.5)),
            )

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            # Default to duplicate if parsing fails
            return UpdateCheckResult(
                is_update=False,
                update_type=UpdateType.DUPLICATE,
                reason=f"Failed to parse response: {content[:100]}",
                confidence=0.3,
            )

    def _generate_fact_hash(self, facts: list[str]) -> str:
        """Generate hash from list of facts."""
        normalized_facts = sorted([
            re.sub(r'\s+', ' ', f.lower().strip())
            for f in facts
        ])
        combined = '|'.join(normalized_facts)
        return hashlib.sha256(combined.encode('utf-8')).hexdigest()

    def extract_key_facts(self, claims: list[dict]) -> list[str]:
        """
        Extract key facts from verified claims.

        Args:
            claims: List of claim dicts with 'text' field

        Returns:
            List of fact strings
        """
        facts = []
        for claim in claims:
            text = claim.get("text", "").strip()
            if text and len(text) > 10:
                facts.append(text)
        return facts[:20]  # Limit to 20 facts

    def extract_key_entities(self, claims: list[dict]) -> dict[str, list[str]]:
        """
        Extract key entities from claims.

        Returns dict with:
        - people: List of person names
        - places: List of locations
        - organizations: List of org names
        """
        entities = {
            "people": [],
            "places": [],
            "organizations": [],
        }

        for claim in claims:
            # Extract from claim entities if available
            claim_entities = claim.get("entities", {})
            if isinstance(claim_entities, dict):
                for key in ["people", "places", "organizations"]:
                    if key in claim_entities:
                        entities[key].extend(claim_entities[key])

        # Deduplicate
        for key in entities:
            entities[key] = list(set(entities[key]))[:20]

        return entities
