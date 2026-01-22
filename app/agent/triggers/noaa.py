"""
NOAA Weather Alert Trigger

Real-time weather alerts from the National Oceanic and Atmospheric Administration.

Features:
- Official government data (Tier-1, 0.99 confidence)
- Severe weather warnings
- Hurricane, tornado, flood alerts
- US-focused with global awareness

Reference: https://api.weather.gov/
"""

import hashlib
import logging
import time
from datetime import datetime
from typing import Any

import httpx

from .base import BaseTrigger, TriggerEvent, TriggerSource

logger = logging.getLogger(__name__)

# NOAA Weather API
NOAA_API_BASE = "https://api.weather.gov"
NOAA_ALERTS_URL = f"{NOAA_API_BASE}/alerts/active"

# Hash expiry
HASH_EXPIRY_SECONDS = 86400

# Severe alert types to monitor
SEVERE_ALERT_TYPES = [
    "Tsunami Warning",
    "Tornado Warning",
    "Extreme Wind Warning",
    "Hurricane Warning",
    "Hurricane Watch",
    "Typhoon Warning",
    "Storm Surge Warning",
    "Severe Thunderstorm Warning",
    "Flash Flood Warning",
    "Flood Warning",
    "Blizzard Warning",
    "Ice Storm Warning",
    "Earthquake Warning",
    "Volcano Warning",
    "Avalanche Warning",
    "Fire Weather Watch",
    "Red Flag Warning",
    "Extreme Fire Danger",
]


class NOAATrigger(BaseTrigger):
    """
    NOAA Weather Alert Trigger

    Tier-1 government source with 0.99 confidence.
    Monitors for severe weather events.
    """

    def __init__(
        self,
        keywords: list[str] | None = None,
        severity: list[str] | None = None,  # Extreme, Severe, Moderate, Minor
        urgency: list[str] | None = None,   # Immediate, Expected, Future
        status: str = "actual",  # actual, exercise, test
    ):
        super().__init__(keywords or ["weather", "storm", "hurricane"])
        self.severity = severity or ["Extreme", "Severe"]
        self.urgency = urgency or ["Immediate", "Expected"]
        self.status = status
        self.seen_hashes: dict[str, float] = {}

    @property
    def source_type(self) -> TriggerSource:
        return TriggerSource.NOAA

    @property
    def source_name(self) -> str:
        return "NOAA Weather"

    async def initialize(self) -> bool:
        """NOAA API requires no authentication"""
        self.is_initialized = True
        logger.info("NOAA Weather trigger initialized")
        return True

    async def scan(self) -> list[TriggerEvent]:
        """
        Query NOAA for active weather alerts
        """
        self.last_scan = datetime.utcnow()
        events: list[TriggerEvent] = []
        current_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                params = {
                    "status": self.status,
                    "message_type": "alert",
                }

                response = await client.get(
                    NOAA_ALERTS_URL,
                    params=params,
                    headers={
                        "Accept": "application/geo+json",
                        "User-Agent": "LiveMap/1.0 (Weather Alert Monitor)",
                    },
                )
                response.raise_for_status()

                data = response.json()
                features = data.get("features", [])

                for feature in features:
                    event = self._parse_alert(feature, current_time)
                    if event:
                        events.append(event)

                # Cleanup expired hashes
                self._cleanup_expired_hashes(current_time)

                logger.info(f"NOAA scan: {len(events)} severe alerts found")

        except Exception as e:
            logger.error(f"NOAA scan error: {e}")

        return events

    def _parse_alert(
        self, feature: dict[str, Any], current_time: float
    ) -> TriggerEvent | None:
        """Parse a GeoJSON weather alert feature"""
        try:
            props = feature.get("properties", {})

            alert_id = props.get("id", "")
            event_type = props.get("event", "")
            headline = props.get("headline", "")
            description = props.get("description", "")
            severity = props.get("severity", "")
            urgency = props.get("urgency", "")
            certainty = props.get("certainty", "")
            effective = props.get("effective", "")
            expires = props.get("expires", "")
            area_desc = props.get("areaDesc", "")
            sender = props.get("senderName", "")

            # Filter by severity and urgency
            if severity not in self.severity:
                return None
            if urgency not in self.urgency:
                return None

            # Filter by event type (focus on severe)
            is_severe = any(
                severe.lower() in event_type.lower()
                for severe in SEVERE_ALERT_TYPES
            )
            if not is_severe and severity not in ["Extreme", "Severe"]:
                return None

            # Deduplication
            content_hash = hashlib.md5(f"{alert_id}".encode()).hexdigest()
            if content_hash in self.seen_hashes:
                return None
            self.seen_hashes[content_hash] = current_time

            # Parse timestamp
            try:
                detected_at = datetime.fromisoformat(effective.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                detected_at = datetime.utcnow()

            # Build title
            title = headline if headline else f"{event_type} - {area_desc}"

            # Truncate description
            content = description[:1000] + "..." if len(description) > 1000 else description

            # Build URL
            url = f"https://alerts.weather.gov/cap/wwacapget.php?x={alert_id}"

            return TriggerEvent(
                title=title,
                source=TriggerSource.NOAA,
                source_name="NOAA",
                url=url,
                detected_at=detected_at,
                content=content,
                language="en",
                country="US",
                keywords_matched=[event_type.lower(), severity.lower()],
                engagement={
                    "severity": severity,
                    "urgency": urgency,
                    "certainty": certainty,
                },
                raw_data={
                    "id": alert_id,
                    "event": event_type,
                    "severity": severity,
                    "urgency": urgency,
                    "certainty": certainty,
                    "effective": effective,
                    "expires": expires,
                    "area": area_desc,
                    "sender": sender,
                    "instruction": props.get("instruction", ""),
                },
            )

        except Exception as e:
            logger.error(f"Error parsing NOAA alert: {e}")
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
