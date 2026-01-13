"""
Stage 0: Preprocessing pipeline for social media content.

Orchestrates text normalization, coordinate extraction,
terminology standardization, and repost detection.
"""

import json
import time
from dataclasses import asdict, dataclass

from app.services.verification.stage0_preprocessing.coordinate_extractor import (
    CoordinateExtractionResult,
    extract_coordinates,
)
from app.services.verification.stage0_preprocessing.normalizer import (
    NormalizationResult,
    is_mostly_hashtags,
    normalize_text,
)
from app.services.verification.stage0_preprocessing.repost_detector import (
    RepostDetectionResult,
    detect_repost,
)
from app.services.verification.stage0_preprocessing.terminology import (
    TerminologyResult,
    extract_and_normalize_terminology,
)


@dataclass
class Stage0Result:
    """Result of Stage 0 preprocessing."""

    # Processing status
    completed: bool
    processing_time_ms: int

    # Normalized text (for subsequent stages)
    original_text: str
    normalized_text: str
    text_length: int

    # Extracted metadata
    hashtags: list[str]
    mentions: list[str]
    urls: list[str]

    # Coordinate extraction
    has_coordinates: bool
    coordinates_json: str | None  # JSON serialized
    primary_latitude: float | None
    primary_longitude: float | None

    # Terminology
    has_military_content: bool
    terminology_json: str | None  # JSON serialized

    # Repost detection
    is_repost: bool
    repost_type: str | None
    original_source: str | None
    original_source_id: str | None
    repost_confidence: float

    # Quality flags
    is_mostly_hashtags: bool
    is_too_short: bool  # < 20 chars after normalization
    has_emojis: bool

    # For database storage
    def to_db_fields(self) -> dict:
        """Convert to fields for Feed model."""
        return {
            "stage0_completed": self.completed,
            "normalized_text": self.normalized_text,
            "extracted_coordinates": self.coordinates_json,
            "detected_terminology": self.terminology_json,
            "is_repost": self.is_repost,
            "original_source_id": self.original_source_id,
        }


def run_stage0(
    text: str,
    platform: str | None = None,
    min_text_length: int = 20,
) -> Stage0Result:
    """
    Run Stage 0 preprocessing pipeline.

    Args:
        text: Raw text from social media
        platform: Source platform (TELEGRAM, X) if known
        min_text_length: Minimum text length after normalization

    Returns:
        Stage0Result with all preprocessing results
    """
    start_time = time.time()

    # Step 1: Normalize text
    norm_result: NormalizationResult = normalize_text(text, keep_hashtags=True, keep_emojis=False)

    # Step 2: Extract coordinates
    coord_result: CoordinateExtractionResult = extract_coordinates(text)

    # Step 3: Detect repost
    repost_result: RepostDetectionResult = detect_repost(text, platform)

    # Step 4: Extract and normalize terminology
    term_result: TerminologyResult = extract_and_normalize_terminology(norm_result.normalized_text)

    # Serialize complex results to JSON
    coordinates_json = None
    if coord_result.coordinates:
        coordinates_json = json.dumps(
            [
                {
                    "lat": c.latitude,
                    "lng": c.longitude,
                    "format": c.format,
                    "confidence": c.confidence,
                }
                for c in coord_result.coordinates
            ]
        )

    terminology_json = None
    if term_result.matches:
        terminology_json = json.dumps(
            [
                {
                    "original": m.original,
                    "normalized": m.normalized,
                    "category": m.category,
                }
                for m in term_result.matches
            ]
        )

    # Quality checks
    mostly_hashtags = is_mostly_hashtags(text)
    too_short = len(norm_result.normalized_text) < min_text_length

    processing_time_ms = int((time.time() - start_time) * 1000)

    return Stage0Result(
        completed=True,
        processing_time_ms=processing_time_ms,
        # Text
        original_text=text,
        normalized_text=term_result.normalized_text,  # Use terminology-normalized text
        text_length=len(norm_result.normalized_text),
        # Extracted metadata
        hashtags=norm_result.extracted_hashtags,
        mentions=norm_result.extracted_mentions,
        urls=norm_result.extracted_urls,
        # Coordinates
        has_coordinates=coord_result.has_coordinates,
        coordinates_json=coordinates_json,
        primary_latitude=coord_result.primary_coordinate.latitude if coord_result.primary_coordinate else None,
        primary_longitude=coord_result.primary_coordinate.longitude if coord_result.primary_coordinate else None,
        # Terminology
        has_military_content=term_result.has_military_content,
        terminology_json=terminology_json,
        # Repost
        is_repost=repost_result.is_repost,
        repost_type=repost_result.repost_type,
        original_source=repost_result.original_source,
        original_source_id=repost_result.original_source_id,
        repost_confidence=repost_result.confidence,
        # Quality flags
        is_mostly_hashtags=mostly_hashtags,
        is_too_short=too_short,
        has_emojis=norm_result.has_emojis,
    )


async def run_stage0_async(
    text: str,
    platform: str | None = None,
    min_text_length: int = 20,
) -> Stage0Result:
    """
    Async wrapper for Stage 0 preprocessing.

    Stage 0 is CPU-bound, so this just wraps the sync function.
    For production, consider using run_in_threadpool.
    """
    return run_stage0(text, platform, min_text_length)
