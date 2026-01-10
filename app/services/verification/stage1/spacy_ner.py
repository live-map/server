"""
spaCy NER for location extraction.

Extracts GPE (geo-political entities) and LOC (locations) from text.
"""

from dataclasses import dataclass

import spacy
from spacy.language import Language


@dataclass
class LocationEntity:
    """Extracted location entity."""

    text: str
    label: str  # GPE or LOC
    start: int
    end: int


@dataclass
class NERResult:
    """Result of NER extraction."""

    locations: list[LocationEntity]
    has_location: bool
    raw_entities: list[dict]


# Global model instance (loaded via lifespan)
_nlp: Language | None = None


def load_model() -> Language:
    """Load spaCy model. Called during app lifespan startup."""
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_lg")
    return _nlp


def get_model() -> Language:
    """Get the loaded spaCy model."""
    if _nlp is None:
        raise RuntimeError("spaCy model not loaded. Call load_model() first.")
    return _nlp


def extract_locations(text: str) -> NERResult:
    """
    Extract location entities from text.

    Args:
        text: Input text to analyze

    Returns:
        NERResult with extracted locations
    """
    nlp = get_model()
    doc = nlp(text)

    locations: list[LocationEntity] = []
    raw_entities: list[dict] = []

    for ent in doc.ents:
        raw_entities.append(
            {"text": ent.text, "label": ent.label_, "start": ent.start_char, "end": ent.end_char}
        )

        # GPE: Countries, cities, states
        # LOC: Non-GPE locations (mountains, water bodies, etc.)
        if ent.label_ in ("GPE", "LOC"):
            locations.append(
                LocationEntity(text=ent.text, label=ent.label_, start=ent.start_char, end=ent.end_char)
            )

    return NERResult(locations=locations, has_location=len(locations) > 0, raw_entities=raw_entities)
