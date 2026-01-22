"""
ACLED Conflict Data Trigger

Armed Conflict Location & Event Data from academic research.

Features:
- Research-based data (Tier-2, 0.85 confidence)
- Global conflict and protest tracking
- Event type categorization
- Fatality tracking

Reference: https://acleddata.com/
"""

import hashlib
import logging
import time
from datetime import datetime, timedelta
from typing import Any

import httpx

from .base import BaseTrigger, TriggerEvent, TriggerSource

logger = logging.getLogger(__name__)

# ACLED API (requires free registration for API key)
ACLED_API_BASE = "https://api.acleddata.com/acled/read"

# Hash expiry
HASH_EXPIRY_SECONDS = 86400

# ACLED event types
EVENT_TYPES = {
    "battles": "Armed clash between two organized armed groups",
    "explosions_remote_violence": "Explosive devices, shelling, air strikes",
    "violence_against_civilians": "Violence specifically targeting civilians",
    "protests": "Non-violent demonstrations",
    "riots": "Violent demonstrations with mob violence",
    "strategic_developments": "Non-violent strategic activities",
}


class ACLEDTrigger(BaseTrigger):
    """
    ACLED Conflict Data Trigger

    Tier-2 research source with 0.85 confidence.
    Monitors for conflicts, protests, and violence events.
    """

    def __init__(
        self,
        api_key: str,
        email: str,
        keywords: list[str] | None = None,
        event_types: list[str] | None = None,
        min_fatalities: int = 0,
        countries: list[str] | None = None,
        max_age_days: int = 7,
    ):
        super().__init__(keywords or ["conflict", "protest", "violence"])
        self.api_key = api_key
        self.email = email
        self.event_types = event_types or [
            "Battles",
            "Explosions/Remote violence",
            "Violence against civilians",
            "Riots",
        ]
        self.min_fatalities = min_fatalities
        self.countries = countries
        self.max_age_days = max_age_days
        self.seen_hashes: dict[str, float] = {}

    @property
    def source_type(self) -> TriggerSource:
        return TriggerSource.ACLED

    @property
    def source_name(self) -> str:
        return "ACLED"

    async def initialize(self) -> bool:
        """Validate ACLED API credentials"""
        if not self.api_key or not self.email:
            logger.warning("ACLED API credentials not configured")
            return False

        self.is_initialized = True
        logger.info("ACLED trigger initialized")
        return True

    async def scan(self) -> list[TriggerEvent]:
        """
        Query ACLED for recent conflict events
        """
        self.last_scan = datetime.utcnow()
        events: list[TriggerEvent] = []
        current_time = time.time()

        if not self.api_key:
            logger.warning("ACLED API key not set, skipping scan")
            return events

        # Calculate date range
        start_date = (datetime.utcnow() - timedelta(days=self.max_age_days)).strftime("%Y-%m-%d")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                params = {
                    "key": self.api_key,
                    "email": self.email,
                    "event_date": start_date,
                    "event_date_where": ">=",
                    "limit": 100,
                }

                # Filter by event types
                if self.event_types:
                    params["event_type"] = ":OR:".join(self.event_types)

                # Filter by countries
                if self.countries:
                    params["country"] = ":OR:".join(self.countries)

                response = await client.get(
                    ACLED_API_BASE,
                    params=params,
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()

                data = response.json()
                records = data.get("data", [])

                for record in records:
                    event = self._parse_event(record, current_time)
                    if event:
                        events.append(event)

                # Cleanup expired hashes
                self._cleanup_expired_hashes(current_time)

                logger.info(f"ACLED scan: {len(events)} conflict events found")

        except Exception as e:
            logger.error(f"ACLED scan error: {e}")

        return events

    def _parse_event(
        self, record: dict[str, Any], current_time: float
    ) -> TriggerEvent | None:
        """Parse an ACLED event record"""
        try:
            event_id = record.get("data_id", "")
            event_date = record.get("event_date", "")
            event_type = record.get("event_type", "")
            sub_event_type = record.get("sub_event_type", "")
            actor1 = record.get("actor1", "")
            actor2 = record.get("actor2", "")
            country = record.get("country", "")
            location = record.get("location", "")
            fatalities = int(record.get("fatalities", 0) or 0)
            notes = record.get("notes", "")

            # Filter by fatalities
            if fatalities < self.min_fatalities:
                return None

            # Deduplication
            content_hash = hashlib.md5(f"{event_id}".encode()).hexdigest()
            if content_hash in self.seen_hashes:
                return None
            self.seen_hashes[content_hash] = current_time

            # Parse timestamp
            try:
                detected_at = datetime.strptime(event_date, "%Y-%m-%d")
            except (ValueError, AttributeError):
                detected_at = datetime.utcnow()

            # Build title
            title_parts = [event_type]
            if sub_event_type:
                title_parts.append(f"({sub_event_type})")
            title_parts.append(f"in {location}, {country}")
            if fatalities > 0:
                title_parts.append(f"[{fatalities} fatalities]")
            title = " ".join(title_parts)

            # Build content
            content_parts = [
                f"Event: {event_type} - {sub_event_type}",
                f"Location: {location}, {country}",
                f"Date: {event_date}",
            ]
            if actor1:
                content_parts.append(f"Actor 1: {actor1}")
            if actor2:
                content_parts.append(f"Actor 2: {actor2}")
            if fatalities > 0:
                content_parts.append(f"Fatalities: {fatalities}")
            if notes:
                content_parts.append(f"\nDetails: {notes[:500]}")

            content = "\n".join(content_parts)

            # Match keywords
            full_text = f"{title} {notes}"
            matched = self._matches_keywords(full_text)
            if not matched:
                matched = [event_type.lower()]

            return TriggerEvent(
                title=title,
                source=TriggerSource.ACLED,
                source_name="ACLED",
                url=f"https://acleddata.com/data-export-tool/",
                detected_at=detected_at,
                content=content,
                language="en",
                country=country,
                keywords_matched=matched,
                engagement={
                    "fatalities": fatalities,
                    "event_type": event_type,
                },
                raw_data={
                    "data_id": event_id,
                    "event_date": event_date,
                    "event_type": event_type,
                    "sub_event_type": sub_event_type,
                    "actor1": actor1,
                    "actor2": actor2,
                    "country": country,
                    "location": location,
                    "latitude": record.get("latitude"),
                    "longitude": record.get("longitude"),
                    "fatalities": fatalities,
                    "notes": notes,
                    "source": record.get("source"),
                    "source_scale": record.get("source_scale"),
                },
            )

        except Exception as e:
            logger.error(f"Error parsing ACLED event: {e}")
            return None

    def _cleanup_expired_hashes(self, current_time: float) -> None:
        """Remove expired hashes"""
        expired = [
            h for h, ts in self.seen_hashes.items()
            if current_time - ts > HASH_EXPIRY_SECONDS
        ]
        for h in expired:
            del self.seen_hashes[h]

    async def close(self):
        """Cleanup resources"""
        self.seen_hashes.clear()
