"""
Coordinate extractor for social media content.

Extracts geographic coordinates from various formats:
- Decimal degrees (48.8566, 2.3522)
- DMS (48°51'24"N 2°21'07"E)
- MGRS (31UDQ1234567890)
- UTM (31N 448251 5411932)
- Google Maps links
"""

import re
from dataclasses import dataclass
from typing import Literal


@dataclass
class ExtractedCoordinate:
    """An extracted coordinate with metadata."""

    latitude: float
    longitude: float
    format: Literal["DECIMAL", "DMS", "MGRS", "UTM", "MAPS_LINK"]
    original_text: str
    confidence: float  # 0.0-1.0


@dataclass
class CoordinateExtractionResult:
    """Result of coordinate extraction."""

    coordinates: list[ExtractedCoordinate]
    has_coordinates: bool
    primary_coordinate: ExtractedCoordinate | None  # Highest confidence


# Regex patterns for coordinate formats
DECIMAL_PATTERN = re.compile(
    r"(-?\d{1,3}\.?\d*)[°\s,]+(-?\d{1,3}\.?\d*)",
    re.UNICODE,
)

DMS_PATTERN = re.compile(
    r"(\d{1,3})[°]\s*(\d{1,2})['\u2032]\s*(\d{1,2}(?:\.\d+)?)[\"″\u2033]?\s*([NS])\s*"
    r"(\d{1,3})[°]\s*(\d{1,2})['\u2032]\s*(\d{1,2}(?:\.\d+)?)[\"″\u2033]?\s*([EW])",
    re.UNICODE | re.IGNORECASE,
)

# MGRS: Grid zone (e.g., 31U) + 100km square (e.g., DQ) + easting/northing
MGRS_PATTERN = re.compile(
    r"\b(\d{1,2}[C-X])([A-HJ-NP-Z]{2})(\d{2,10})\b",
    re.IGNORECASE,
)

# UTM: Zone + hemisphere + easting + northing
UTM_PATTERN = re.compile(
    r"\b(\d{1,2})([NS])\s+(\d{6,7})\s+(\d{6,7})\b",
    re.IGNORECASE,
)

# Google Maps link
MAPS_LINK_PATTERN = re.compile(
    r"(?:google\.com/maps|maps\.google\.com|goo\.gl/maps)[^\s]*[@/](-?\d+\.?\d*),(-?\d+\.?\d*)",
    re.UNICODE,
)

# Simple lat/lng pair (common in social media)
SIMPLE_LATLONG_PATTERN = re.compile(
    r"(?:lat|latitude)[:\s]*(-?\d{1,2}\.?\d+)[,\s]+(?:lon|lng|longitude)[:\s]*(-?\d{1,3}\.?\d+)",
    re.IGNORECASE,
)


def dms_to_decimal(degrees: float, minutes: float, seconds: float, direction: str) -> float:
    """Convert DMS to decimal degrees."""
    decimal = degrees + minutes / 60 + seconds / 3600
    if direction.upper() in ("S", "W"):
        decimal = -decimal
    return decimal


def is_valid_coordinate(lat: float, lng: float) -> bool:
    """Check if coordinate is valid."""
    return -90 <= lat <= 90 and -180 <= lng <= 180


def extract_coordinates(text: str) -> CoordinateExtractionResult:
    """
    Extract geographic coordinates from text.

    Args:
        text: Text to search for coordinates

    Returns:
        CoordinateExtractionResult with all found coordinates
    """
    coordinates: list[ExtractedCoordinate] = []

    # Try Google Maps links first (highest confidence)
    for match in MAPS_LINK_PATTERN.finditer(text):
        lat, lng = float(match.group(1)), float(match.group(2))
        if is_valid_coordinate(lat, lng):
            coordinates.append(
                ExtractedCoordinate(
                    latitude=lat,
                    longitude=lng,
                    format="MAPS_LINK",
                    original_text=match.group(0),
                    confidence=0.95,
                )
            )

    # Try simple lat/lng pattern
    for match in SIMPLE_LATLONG_PATTERN.finditer(text):
        lat, lng = float(match.group(1)), float(match.group(2))
        if is_valid_coordinate(lat, lng):
            coordinates.append(
                ExtractedCoordinate(
                    latitude=lat,
                    longitude=lng,
                    format="DECIMAL",
                    original_text=match.group(0),
                    confidence=0.90,
                )
            )

    # Try DMS format
    for match in DMS_PATTERN.finditer(text):
        lat_d, lat_m, lat_s, lat_dir = match.groups()[:4]
        lng_d, lng_m, lng_s, lng_dir = match.groups()[4:]

        lat = dms_to_decimal(float(lat_d), float(lat_m), float(lat_s), lat_dir)
        lng = dms_to_decimal(float(lng_d), float(lng_m), float(lng_s), lng_dir)

        if is_valid_coordinate(lat, lng):
            coordinates.append(
                ExtractedCoordinate(
                    latitude=lat,
                    longitude=lng,
                    format="DMS",
                    original_text=match.group(0),
                    confidence=0.85,
                )
            )

    # Try decimal format (lower confidence due to false positives)
    for match in DECIMAL_PATTERN.finditer(text):
        try:
            lat, lng = float(match.group(1)), float(match.group(2))
            # Additional validation for decimal - must look like coordinates
            if is_valid_coordinate(lat, lng):
                # Filter out likely non-coordinates (e.g., dates, times)
                if abs(lat) > 10 and abs(lng) > 10:  # Not too close to 0,0
                    # Check if not already found
                    already_found = any(
                        abs(c.latitude - lat) < 0.0001 and abs(c.longitude - lng) < 0.0001
                        for c in coordinates
                    )
                    if not already_found:
                        coordinates.append(
                            ExtractedCoordinate(
                                latitude=lat,
                                longitude=lng,
                                format="DECIMAL",
                                original_text=match.group(0),
                                confidence=0.60,
                            )
                        )
        except (ValueError, IndexError):
            continue

    # Sort by confidence
    coordinates.sort(key=lambda c: c.confidence, reverse=True)

    return CoordinateExtractionResult(
        coordinates=coordinates,
        has_coordinates=len(coordinates) > 0,
        primary_coordinate=coordinates[0] if coordinates else None,
    )


def mgrs_to_latlong(mgrs: str) -> tuple[float, float] | None:
    """
    Convert MGRS to lat/long.

    Note: This is a simplified conversion. For production,
    use a proper MGRS library like mgrs or pyproj.
    """
    # TODO: Implement proper MGRS conversion
    # For now, return None and log for manual review
    return None


def utm_to_latlong(zone: int, hemisphere: str, easting: float, northing: float) -> tuple[float, float] | None:
    """
    Convert UTM to lat/long.

    Note: This is a simplified conversion. For production,
    use a proper UTM library like utm or pyproj.
    """
    # TODO: Implement proper UTM conversion
    # For now, return None and log for manual review
    return None
