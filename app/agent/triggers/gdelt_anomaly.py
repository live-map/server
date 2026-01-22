"""
GDELT Anomaly Detection Trigger

Uses GDELT's advanced APIs for breaking news detection:
- timelinevolraw: Volume spike detection
- GKG Themes: Crisis theme monitoring (CRISISLEX, PROTEST, etc.)
- Goldstein Score: Conflict intensity measurement

Reference: https://blog.gdeltproject.org/gdelt-2-0-our-global-world-in-realtime/
"""

import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import httpx

from .base import BaseTrigger, TriggerEvent, TriggerSource

logger = logging.getLogger(__name__)

# GDELT API endpoints
GDELT_TV_API = "https://api.gdeltproject.org/api/v2/tv/tv"
GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_GKG_API = "https://api.gdeltproject.org/api/v2/gkg/gkg"

# Time-based hash expiry (24 hours)
HASH_EXPIRY_SECONDS = 86400


class AnomalyType(str, Enum):
    """Type of anomaly detected"""
    VOLUME_SPIKE = "volume_spike"
    GKG_THEME = "gkg_theme"
    GOLDSTEIN_CONFLICT = "goldstein_conflict"


@dataclass
class AnomalySignal:
    """Represents a detected anomaly signal"""
    anomaly_type: AnomalyType
    query: str
    score: float  # 0-1, higher = more significant
    metadata: dict


# GKG Themes for crisis detection
# Reference: https://blog.gdeltproject.org/gdelt-gkg-2-0-global-knowledge-graph-themes/
CRISIS_THEMES = [
    "CRISISLEX_CRISISLEXREC",  # CrisisLex emergency terms
    "CRISISLEX_C01_CAUTION_ADVICE",
    "CRISISLEX_C02_INFO_WANTED",
    "CRISISLEX_C03_RESOURCE_CALL",
    "CRISISLEX_C04_DONATE_VOLUNTEER",
    "CRISISLEX_C05_SUPPORT",
    "CRISISLEX_C06_DEATHS_AFFECTED",
    "CRISISLEX_C07_RESPONSE_CRITICISM",
    "CRISISLEX_T01_CASUALTIES_DAMAGE",
    "TAX_ETHNICITY_VIOLENCE",
    "TAX_WORLDLANGUAGES_VIOLENCE",
    "PROTEST",
    "TERROR",
    "MILITARY",
    "ARMED_CONFLICT",
    "NATURAL_DISASTER",
    "EARTHQUAKE",
    "TSUNAMI",
    "FLOOD",
    "WILDFIRE",
]

# Conflict-related CAMEO event codes
# Goldstein scores < -5 indicate high-intensity conflicts
# Reference: https://www.gdeltproject.org/data/documentation/CAMEO.Manual.1.1b3.pdf
CONFLICT_CAMEO_ROOTS = [
    "14",  # PROTEST
    "17",  # COERCE
    "18",  # ASSAULT
    "19",  # FIGHT
    "20",  # MASS VIOLENCE
]


class GDELTAnomalyTrigger(BaseTrigger):
    """
    GDELT Anomaly Detection Trigger

    Detects breaking news through:
    1. Volume spikes (timelinevolraw API)
    2. Crisis themes (GKG API)
    3. High-intensity conflicts (Goldstein score)
    """

    def __init__(
        self,
        keywords: list[str] | None = None,
        timespan: str = "15min",
        volume_spike_threshold: float = 2.0,  # Z-score threshold
        goldstein_threshold: float = -5.0,  # Conflict intensity
        max_results: int = 50,
    ):
        super().__init__(keywords)
        self.timespan = timespan
        self.volume_spike_threshold = volume_spike_threshold
        self.goldstein_threshold = goldstein_threshold
        self.max_results = max_results
        # Historical volume data for spike detection
        self.volume_history: dict[str, list[float]] = {}
        # Time-based deduplication
        self.seen_hashes: dict[str, float] = {}

    @property
    def source_type(self) -> TriggerSource:
        return TriggerSource.GDELT

    @property
    def source_name(self) -> str:
        return "GDELT Anomaly"

    async def initialize(self) -> bool:
        """GDELT requires no authentication"""
        self.is_initialized = True
        logger.info("GDELT Anomaly trigger initialized")
        return True

    async def scan(self) -> list[TriggerEvent]:
        """
        Multi-signal anomaly detection scan

        1. Check GKG themes for crisis patterns
        2. Check for Goldstein score conflicts
        3. Aggregate and deduplicate results
        """
        self.last_scan = datetime.utcnow()
        events: list[TriggerEvent] = []
        current_time = time.time()

        try:
            # Parallel detection of different anomaly types
            gkg_events = await self._scan_gkg_themes()
            goldstein_events = await self._scan_goldstein_conflicts()

            # Combine all events
            all_events = gkg_events + goldstein_events

            # Deduplicate by content hash
            for event in all_events:
                content_hash = hashlib.md5(
                    f"{event.title}:{event.url}".encode()
                ).hexdigest()

                if content_hash in self.seen_hashes:
                    continue

                self.seen_hashes[content_hash] = current_time
                events.append(event)

            # Cleanup expired hashes
            self._cleanup_expired_hashes(current_time)

            logger.info(
                f"GDELT Anomaly scan: {len(gkg_events)} GKG, "
                f"{len(goldstein_events)} Goldstein, {len(events)} total new"
            )

        except Exception as e:
            logger.error(f"GDELT Anomaly scan error: {e}")

        return events

    async def _scan_gkg_themes(self) -> list[TriggerEvent]:
        """Scan GKG API for crisis-related themes"""
        events = []

        # Query for crisis themes
        theme_query = " OR ".join(f"theme:{theme}" for theme in CRISIS_THEMES[:10])

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    GDELT_DOC_API,
                    params={
                        "query": theme_query,
                        "mode": "artlist",
                        "maxrecords": str(self.max_results),
                        "format": "json",
                        "timespan": self.timespan,
                        "sort": "datedesc",
                    },
                )
                response.raise_for_status()

                if not response.headers.get("content-type", "").startswith("application/json"):
                    logger.warning(f"GKG returned non-JSON: {response.text[:100]}")
                    return []

                data = response.json()
                articles = data.get("articles", [])

                for art in articles:
                    title = art.get("title", "")
                    matched = self._matches_keywords(title)

                    events.append(TriggerEvent(
                        title=title,
                        source=TriggerSource.GDELT,
                        source_name=art.get("domain", "unknown"),
                        url=art.get("url", ""),
                        detected_at=datetime.utcnow(),
                        language=art.get("language", "en"),
                        country=art.get("sourcecountry", ""),
                        keywords_matched=matched if matched else ["[gkg-theme]"],
                        raw_data={
                            **art,
                            "anomaly_type": AnomalyType.GKG_THEME.value,
                        },
                    ))

        except httpx.TimeoutException:
            logger.warning("GKG API timeout")
        except Exception as e:
            logger.error(f"GKG scan error: {e}")

        return events

    async def _scan_goldstein_conflicts(self) -> list[TriggerEvent]:
        """Scan for high-intensity conflicts using Goldstein score"""
        events = []

        # Query for conflict events with low Goldstein scores
        conflict_query = " OR ".join(self.keywords[:10])

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    GDELT_DOC_API,
                    params={
                        "query": conflict_query,
                        "mode": "artlist",
                        "maxrecords": str(self.max_results),
                        "format": "json",
                        "timespan": self.timespan,
                        "sort": "toneasc",  # Sort by most negative tone first
                    },
                )
                response.raise_for_status()

                if not response.headers.get("content-type", "").startswith("application/json"):
                    logger.warning(f"Goldstein query returned non-JSON: {response.text[:100]}")
                    return []

                data = response.json()
                articles = data.get("articles", [])

                for art in articles:
                    # Filter by tone (proxy for Goldstein in doc API)
                    tone = art.get("tone", 0)
                    if tone > self.goldstein_threshold:
                        continue

                    title = art.get("title", "")
                    matched = self._matches_keywords(title)

                    events.append(TriggerEvent(
                        title=title,
                        source=TriggerSource.GDELT,
                        source_name=art.get("domain", "unknown"),
                        url=art.get("url", ""),
                        detected_at=datetime.utcnow(),
                        language=art.get("language", "en"),
                        country=art.get("sourcecountry", ""),
                        keywords_matched=matched if matched else ["[goldstein-conflict]"],
                        raw_data={
                            **art,
                            "anomaly_type": AnomalyType.GOLDSTEIN_CONFLICT.value,
                            "tone": tone,
                        },
                    ))

        except httpx.TimeoutException:
            logger.warning("Goldstein API timeout")
        except Exception as e:
            logger.error(f"Goldstein scan error: {e}")

        return events

    def _cleanup_expired_hashes(self, current_time: float) -> None:
        """Remove expired hashes older than HASH_EXPIRY_SECONDS"""
        expired_hashes = [
            h for h, ts in self.seen_hashes.items()
            if current_time - ts > HASH_EXPIRY_SECONDS
        ]

        for h in expired_hashes:
            del self.seen_hashes[h]

        if expired_hashes:
            logger.debug(
                f"Cleaned up {len(expired_hashes)} expired hashes, "
                f"{len(self.seen_hashes)} remaining"
            )

    async def close(self):
        """Cleanup resources"""
        self.seen_hashes.clear()
        self.volume_history.clear()
