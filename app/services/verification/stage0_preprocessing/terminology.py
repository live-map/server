"""
Military terminology standardization.

Normalizes military abbreviations and slang to standard terms
for better NER and search matching.
"""

import re
from dataclasses import dataclass


@dataclass
class TerminologyMatch:
    """A matched and normalized term."""

    original: str
    normalized: str
    category: str  # UNIT, WEAPON, LOCATION, ACTION, etc.


@dataclass
class TerminologyResult:
    """Result of terminology extraction."""

    matches: list[TerminologyMatch]
    normalized_text: str
    has_military_content: bool


# Military terminology dictionary
# Format: {pattern: (normalized_form, category)}
MILITARY_TERMS: dict[str, tuple[str, str]] = {
    # Units
    r"\bBTG\b": ("Battalion Tactical Group", "UNIT"),
    r"\bBMP\b": ("Infantry Fighting Vehicle", "WEAPON"),
    r"\bBTR\b": ("Armored Personnel Carrier", "WEAPON"),
    r"\bT-?72\b": ("T-72 Tank", "WEAPON"),
    r"\bT-?80\b": ("T-80 Tank", "WEAPON"),
    r"\bT-?90\b": ("T-90 Tank", "WEAPON"),
    r"\bMi-?24\b": ("Mi-24 Helicopter", "WEAPON"),
    r"\bKa-?52\b": ("Ka-52 Helicopter", "WEAPON"),
    r"\bSu-?25\b": ("Su-25 Aircraft", "WEAPON"),
    r"\bSu-?34\b": ("Su-34 Aircraft", "WEAPON"),
    r"\bMiG-?29\b": ("MiG-29 Aircraft", "WEAPON"),
    r"\bHIMARS\b": ("HIMARS Rocket System", "WEAPON"),
    r"\bMLRS\b": ("Multiple Launch Rocket System", "WEAPON"),
    r"\bATGM\b": ("Anti-Tank Guided Missile", "WEAPON"),
    r"\bMANPADS?\b": ("Man-Portable Air-Defense System", "WEAPON"),
    r"\bUAV\b": ("Unmanned Aerial Vehicle", "WEAPON"),
    r"\bUCAV\b": ("Unmanned Combat Aerial Vehicle", "WEAPON"),
    r"\bFPV\b": ("First-Person View Drone", "WEAPON"),
    r"\bIFV\b": ("Infantry Fighting Vehicle", "WEAPON"),
    r"\bAPC\b": ("Armored Personnel Carrier", "WEAPON"),
    r"\bMBT\b": ("Main Battle Tank", "WEAPON"),
    r"\bSPG\b": ("Self-Propelled Gun", "WEAPON"),
    r"\bSPH\b": ("Self-Propelled Howitzer", "WEAPON"),
    r"\bAFU\b": ("Armed Forces of Ukraine", "UNIT"),
    r"\bZSU\b": ("Armed Forces of Ukraine", "UNIT"),
    r"\bVSU\b": ("Armed Forces of Ukraine", "UNIT"),
    r"\bRuAF\b": ("Russian Air Force", "UNIT"),
    r"\bVKS\b": ("Russian Aerospace Forces", "UNIT"),
    r"\bWagner\b": ("Wagner Group", "UNIT"),
    r"\bPMC\b": ("Private Military Company", "UNIT"),
    r"\bDPR\b": ("Donetsk People's Republic", "LOCATION"),
    r"\bLPR\b": ("Luhansk People's Republic", "LOCATION"),
    r"\bLNR\b": ("Luhansk People's Republic", "LOCATION"),
    r"\bDNR\b": ("Donetsk People's Republic", "LOCATION"),

    # Actions
    r"\bKIA\b": ("Killed in Action", "ACTION"),
    r"\bWIA\b": ("Wounded in Action", "ACTION"),
    r"\bMIA\b": ("Missing in Action", "ACTION"),
    r"\bPOW\b": ("Prisoner of War", "ACTION"),
    r"\bCAS\b": ("Close Air Support", "ACTION"),
    r"\bISR\b": ("Intelligence, Surveillance, Reconnaissance", "ACTION"),
    r"\bEW\b": ("Electronic Warfare", "ACTION"),
    r"\bAD\b": ("Air Defense", "ACTION"),
    r"\bAAD\b": ("Anti-Air Defense", "ACTION"),
    r"\bFOB\b": ("Forward Operating Base", "LOCATION"),
    r"\bLOC\b": ("Line of Contact", "LOCATION"),
    r"\bFLOT\b": ("Forward Line of Own Troops", "LOCATION"),

    # Common abbreviations in conflict reporting
    r"\binfantry\b": ("Infantry", "UNIT"),
    r"\bartillery\b": ("Artillery", "WEAPON"),
    r"\bcasualties?\b": ("Casualties", "ACTION"),
    r"\breinforcements?\b": ("Reinforcements", "ACTION"),
    r"\bcounter-?offensive\b": ("Counter-Offensive", "ACTION"),
    r"\badvance[ds]?\b": ("Advance", "ACTION"),
    r"\bretreat[eds]?\b": ("Retreat", "ACTION"),
    r"\bwithdraw[als]?\b": ("Withdrawal", "ACTION"),
    r"\bshelling\b": ("Shelling", "ACTION"),
    r"\bbombard(?:ment|ing)?\b": ("Bombardment", "ACTION"),
    r"\bstrike[s]?\b": ("Strike", "ACTION"),
    r"\braid[s]?\b": ("Raid", "ACTION"),
}

# Additional patterns for conflict-specific locations
CONFLICT_LOCATIONS: dict[str, str] = {
    # Ukraine
    "Bakhmut": "Bakhmut",
    "Avdiivka": "Avdiivka",
    "Mariupol": "Mariupol",
    "Kherson": "Kherson",
    "Zaporizhzhia": "Zaporizhzhia",
    "Donetsk": "Donetsk",
    "Luhansk": "Luhansk",
    "Kharkiv": "Kharkiv",
    "Kyiv": "Kyiv",
    "Kiev": "Kyiv",  # Normalize Russian spelling
    "Odesa": "Odesa",
    "Odessa": "Odesa",  # Normalize Russian spelling
    "Crimea": "Crimea",
    "Donbas": "Donbas",
    "Donbass": "Donbas",

    # Middle East
    "Gaza": "Gaza",
    "Tel Aviv": "Tel Aviv",
    "Jerusalem": "Jerusalem",
    "West Bank": "West Bank",
    "Rafah": "Rafah",
    "Khan Younis": "Khan Younis",
}


def extract_and_normalize_terminology(text: str) -> TerminologyResult:
    """
    Extract military terms and normalize them.

    Args:
        text: Text to analyze

    Returns:
        TerminologyResult with matches and normalized text
    """
    matches: list[TerminologyMatch] = []
    normalized = text

    # Check military terms
    for pattern, (normalized_form, category) in MILITARY_TERMS.items():
        regex = re.compile(pattern, re.IGNORECASE)
        for match in regex.finditer(text):
            original = match.group(0)
            matches.append(
                TerminologyMatch(
                    original=original,
                    normalized=normalized_form,
                    category=category,
                )
            )

    # Normalize location names
    for original, normalized_form in CONFLICT_LOCATIONS.items():
        if original.lower() != normalized_form.lower():
            pattern = re.compile(rf"\b{re.escape(original)}\b", re.IGNORECASE)
            if pattern.search(text):
                normalized = pattern.sub(normalized_form, normalized)
                matches.append(
                    TerminologyMatch(
                        original=original,
                        normalized=normalized_form,
                        category="LOCATION",
                    )
                )

    # Determine if content is military-related
    military_categories = {"UNIT", "WEAPON", "ACTION"}
    has_military = any(m.category in military_categories for m in matches)

    return TerminologyResult(
        matches=matches,
        normalized_text=normalized,
        has_military_content=has_military,
    )


def is_military_content(text: str, threshold: int = 2) -> bool:
    """
    Quick check if text contains military content.

    Args:
        text: Text to check
        threshold: Minimum number of military terms required

    Returns:
        True if text appears to be military-related
    """
    result = extract_and_normalize_terminology(text)
    military_matches = [m for m in result.matches if m.category in {"UNIT", "WEAPON", "ACTION"}]
    return len(military_matches) >= threshold
