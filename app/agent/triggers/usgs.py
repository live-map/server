"""
USGS Earthquake API Trigger

Real-time earthquake monitoring from the US Geological Survey.

Features:
- Official government data (Tier-1, 0.99 confidence)
- Real-time earthquake alerts
- Magnitude and location filtering
- GeoJSON format

Reference: https://earthquake.usgs.gov/fdsnws/event/1/
"""

import hashlib
import logging
import time
from datetime import datetime, timedelta
from typing import Any

import httpx

from .base import BaseTrigger, TriggerEvent, TriggerSource

logger = logging.getLogger(__name__)

# USGS Earthquake API
USGS_API_BASE = "https://earthquake.usgs.gov/fdsnws/event/1"
USGS_QUERY_URL = f"{USGS_API_BASE}/query"

# Hash expiry
HASH_EXPIRY_SECONDS = 86400


class USGSTrigger(BaseTrigger):
    """
    USGS Earthquake Trigger

    Tier-1 government source with 0.99 confidence.
    Monitors for significant earthquakes worldwide.
    """

    def __init__(
        self,
        keywords: list[str] | None = None,
        min_magnitude: float = 5.0,  # Significant earthquakes
        max_age_hours: int = 24,
        alert_level: str | None = None,  # green, yellow, orange, red
    ):
        super().__init__(keywords or ["earthquake"])
        self.min_magnitude = min_magnitude
        self.max_age_hours = max_age_hours
        self.alert_level = alert_level
        self.seen_hashes: dict[str, float] = {}

    @property
    def source_type(self) -> TriggerSource:
        return TriggerSource.USGS

    @property
    def source_name(self) -> str:
        return "USGS Earthquake"

    async def initialize(self) -> bool:
        """USGS API requires no authentication"""
        self.is_initialized = True
        logger.info("USGS Earthquake trigger initialized")
        return True

    async def scan(self) -> list[TriggerEvent]:
        """
        Query USGS for recent significant earthquakes
        """
        self.last_scan = datetime.utcnow()
        events: list[TriggerEvent] = []
        current_time = time.time()

        # Calculate time range
        start_time = datetime.utcnow() - timedelta(hours=self.max_age_hours)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                params = {
                    "format": "geojson",
                    "starttime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "minmagnitude": str(self.min_magnitude),
                    "orderby": "time",
                }

                if self.alert_level:
                    params["alertlevel"] = self.alert_level

                response = await client.get(USGS_QUERY_URL, params=params)
                response.raise_for_status()

                data = response.json()
                features = data.get("features", [])

                for feature in features:
                    event = self._parse_earthquake(feature, current_time)
                    if event:
                        events.append(event)

                # Cleanup expired hashes
                self._cleanup_expired_hashes(current_time)

                logger.info(f"USGS scan: {len(events)} earthquakes found (M{self.min_magnitude}+)")

        except Exception as e:
            logger.error(f"USGS scan error: {e}")

        return events

    def _parse_earthquake(
        self, feature: dict[str, Any], current_time: float
    ) -> TriggerEvent | None:
        """Parse a GeoJSON earthquake feature"""
        try:
            props = feature.get("properties", {})
            geometry = feature.get("geometry", {})
            coords = geometry.get("coordinates", [0, 0, 0])

            eq_id = feature.get("id", "")
            magnitude = props.get("mag", 0)
            place = props.get("place", "Unknown location")
            time_ms = props.get("time", 0)
            url = props.get("url", "")
            alert = props.get("alert", "")
            tsunami = props.get("tsunami", 0)
            felt = props.get("felt", 0)

            # Deduplication
            content_hash = hashlib.md5(f"{eq_id}".encode()).hexdigest()
            if content_hash in self.seen_hashes:
                return None
            self.seen_hashes[content_hash] = current_time

            # Parse timestamp
            try:
                detected_at = datetime.utcfromtimestamp(time_ms / 1000)
            except (ValueError, OSError):
                detected_at = datetime.utcnow()

            # Build title
            title = f"M{magnitude:.1f} Earthquake - {place}"
            if tsunami:
                title += " [TSUNAMI WARNING]"

            # Build content
            content_parts = [
                f"Magnitude: {magnitude:.1f}",
                f"Location: {place}",
                f"Depth: {coords[2]:.1f} km",
                f"Coordinates: {coords[1]:.4f}, {coords[0]:.4f}",
            ]
            if alert:
                content_parts.append(f"Alert Level: {alert.upper()}")
            if felt:
                content_parts.append(f"Felt reports: {felt}")
            if tsunami:
                content_parts.append("TSUNAMI WARNING ISSUED")

            content = "\n".join(content_parts)

            return TriggerEvent(
                title=title,
                source=TriggerSource.USGS,
                source_name="USGS",
                url=url,
                detected_at=detected_at,
                content=content,
                language="en",
                country=self._extract_country(place),
                keywords_matched=["earthquake", f"M{magnitude:.0f}"],
                engagement={
                    "magnitude": magnitude,
                    "alert_level": alert,
                    "tsunami": bool(tsunami),
                    "felt_reports": felt,
                },
                raw_data={
                    "id": eq_id,
                    "magnitude": magnitude,
                    "place": place,
                    "depth_km": coords[2],
                    "latitude": coords[1],
                    "longitude": coords[0],
                    "alert": alert,
                    "tsunami": tsunami,
                    "felt": felt,
                    "sig": props.get("sig", 0),  # Significance score
                    "nst": props.get("nst", 0),  # Stations used
                },
            )

        except Exception as e:
            logger.error(f"Error parsing earthquake: {e}")
            return None

    def _extract_country(self, place: str) -> str:
        """Extract country from place string"""
        # USGS format: "X km NW of City, Country"
        if ", " in place:
            return place.split(", ")[-1]
        return ""

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
