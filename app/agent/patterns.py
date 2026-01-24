"""
Centralized Pattern Definitions (P2)

This module consolidates all regex patterns and keyword lists used across the
news scanner pipeline. Centralizing patterns provides:
1. Single source of truth for pattern definitions
2. Easier maintenance and updates
3. Reduced duplication
4. Better testing coverage

Pattern Categories:
- Event Verification: Patterns for identifying non-events
- Checkworthiness: Patterns for filtering unwanted content
- Category: Patterns for event classification
- Importance: Patterns from Goldstein Scale
- Date Extraction: Patterns for date parsing
- Specificity: Patterns for content specificity
"""

import re
from typing import Pattern

# =============================================================================
# EVENT VERIFICATION PATTERNS
# =============================================================================
# Patterns that indicate content is NOT a breaking news event

NOT_EVENT_PATTERNS = [
    # Scheduled events (not breaking news)
    r"\b(?:will be held|is scheduled|upcoming|planned for|set to begin)\b",
    r"\b(?:next week|next month|this weekend|later this year)\b",
    r"\b(?:annual|yearly|monthly|weekly) (?:event|meeting|conference)\b",

    # Historical/retrospective content
    r"\b(?:years ago|decade ago|century ago|in \d{4})\b",
    r"\b(?:historically|in history|looking back|anniversary of)\b",
    r"\b(?:remembering|commemorating|memorial|tribute to)\b",

    # Entertainment content
    r"\b(?:movie|film|tv show|series|album|song|concert|tour)\b",
    r"\b(?:actor|actress|celebrity|singer|musician|artist|performer)\b",
    r"\b(?:premiere|release date|streaming|netflix|disney|hbo)\b",

    # Sports content (non-breaking)
    r"\b(?:scored|goals|assists|batting|pitching|touchdown|home run)\b",
    r"\b(?:championship|tournament|playoffs|league|division|standings)\b",
    r"\b(?:coach|manager|roster|draft|trade|contract|salary)\b",

    # Weather (routine)
    r"\b(?:weather forecast|temperature|sunny|cloudy|chance of rain)\b",
    r"\b(?:high of \d+|low of \d+|humidity|precipitation)\b",

    # Opinion/analysis (not news)
    r"\b(?:opinion|editorial|column|commentary|analysis|review)\b",
    r"\b(?:should|could|might|may|perhaps|possibly|probably)\b",
    r"\b(?:expert says|analyst|pundit|critic)\b",

    # Lifestyle/human interest
    r"\b(?:tips for|how to|guide to|best ways to|secrets to)\b",
    r"\b(?:recipe|cooking|fashion|beauty|wellness|lifestyle)\b",
    r"\b(?:inspiring story|heartwarming|feel-good|amazing)\b",
]

# Compiled patterns for performance
COMPILED_NOT_EVENT_PATTERNS = [
    re.compile(pattern, re.IGNORECASE) for pattern in NOT_EVENT_PATTERNS
]


# =============================================================================
# CHECKWORTHINESS PATTERNS
# =============================================================================

ENTERTAINMENT_PATTERNS = [
    r"\b(?:movie|film|tv show|series|album|song|concert)\b",
    r"\b(?:celebrity|actor|actress|singer|musician|artist)\b",
    r"\b(?:grammy|oscar|emmy|golden globe|awards? show)\b",
    r"\b(?:box office|streaming|netflix|disney|premiere)\b",
    r"\b(?:reality tv|talk show|interview|podcast)\b",
]

SPECULATION_PATTERNS = [
    r"\b(?:could|might|may|possibly|potentially|perhaps)\b.*(?:war|conflict|attack|crisis)",
    r"\b(?:fears?|worries?|concerns?) (?:of|about|over|that)\b",
    r"\b(?:threatens?|risks?|warns?) (?:of|about)?\b",
    r"\b(?:what if|scenario|hypothetical|speculation)\b",
]

BACKGROUND_PATTERNS = [
    r"\b(?:history of|background|context|explainer|analysis)\b",
    r"\b(?:timeline of|overview of|guide to|understanding)\b",
    r"\b(?:origins of|roots of|evolution of)\b",
]

PROMOTIONAL_PATTERNS = [
    r"\b(?:buy now|order now|subscribe|sign up|discount|sale)\b",
    r"\b(?:sponsored|advertisement|promoted|partner content)\b",
    r"\b(?:click here|learn more|find out|discover how)\b",
]

HUMAN_INTEREST_PATTERNS = [
    r"\b(?:inspiring|heartwarming|touching|remarkable|incredible)\b",
    r"\b(?:meet the|profile of|story of|journey of)\b",
    r"\b(?:local hero|community|volunteer|charity)\b",
]

LOCAL_INCIDENT_PATTERNS = [
    # Traffic/minor accidents
    r"\b(?:car crash|traffic accident|vehicle collision|fender bender)\b(?!.*(?:mass casualty|multiple|killed|dead|terrorist))",
    r"\b(?:road closure|traffic jam|delays? on|highway closed)\b",
    r"\b(?:icy road|slippery|glatteis|black ice)\b(?!.*(?:mass|multiple|killed))",

    # Minor local incidents
    r"\b(?:house fire|apartment fire|structure fire)\b(?!.*(?:arson|terrorism|mass|killed))",
    r"\b(?:power outage|utility|water main|gas leak)\b(?!.*(?:explosion|attack))",
    r"\b(?:shoplifting|petty theft|vandalism|graffiti)\b",
]

SPORTS_NEWS_PATTERNS = [
    # Sports results
    r"\b(?:won|defeated|beat|lost to|draws? with)\b.*(?:match|game|set|round)",
    r"\b(?:scored|goals?|points?|runs?|touchdowns?|home runs?)\b",
    r"\b(?:championship|tournament|playoffs?|finals?|league)\b",

    # Sports activities
    r"\b(?:cyclist|cycling|bicycle|bike race|velodrome|tour de)\b",
    r"\b(?:rally|dakar|wrc|formula|f1|motorsport|racing|grand prix)\b",
    r"\b(?:triumphs?|wins?|defeats?|victory|victories|champion)\b",
    r"\b(?:athlete|player|coach|team|squad|roster)\b",

    # Sports events
    r"\b(?:tennis|golf|cricket|rugby|boxing|mma|ufc|wrestling)\b",
    r"\b(?:premier league|la liga|serie a|bundesliga|champions league)\b",
    r"\b(?:nba|nfl|mlb|nhl|mls|fifa|uefa|olympics)\b",
]

LOCAL_CRIME_PATTERNS = [
    # Individual crimes (not mass/terrorism)
    r"\b(?:murder|homicide|killing|manslaughter)\b(?!.*(?:mass|serial|terrorist|war crime))",
    r"\b(?:robbery|burglary|theft|stolen|assault|battery)\b(?!.*(?:armed forces|military))",
    r"\b(?:child abuse|child neglect|domestic violence|abuse)\b",
    r"\b(?:arraigned|sentenced|convicted|plea|bail|court appearance)\b",
    r"\b(?:suspect|perpetrator|victim|witness)\b(?!.*(?:war|conflict|attack|terrorist))",
    r"\b(?:police arrested|police charged|police investigate)\b(?!.*(?:protest|riot|terror))",
]

# Compile all checkworthiness patterns
COMPILED_ENTERTAINMENT_PATTERNS = [re.compile(p, re.IGNORECASE) for p in ENTERTAINMENT_PATTERNS]
COMPILED_SPECULATION_PATTERNS = [re.compile(p, re.IGNORECASE) for p in SPECULATION_PATTERNS]
COMPILED_BACKGROUND_PATTERNS = [re.compile(p, re.IGNORECASE) for p in BACKGROUND_PATTERNS]
COMPILED_PROMOTIONAL_PATTERNS = [re.compile(p, re.IGNORECASE) for p in PROMOTIONAL_PATTERNS]
COMPILED_HUMAN_INTEREST_PATTERNS = [re.compile(p, re.IGNORECASE) for p in HUMAN_INTEREST_PATTERNS]
COMPILED_LOCAL_INCIDENT_PATTERNS = [re.compile(p, re.IGNORECASE) for p in LOCAL_INCIDENT_PATTERNS]
COMPILED_SPORTS_PATTERNS = [re.compile(p, re.IGNORECASE) for p in SPORTS_NEWS_PATTERNS]
COMPILED_LOCAL_CRIME_PATTERNS = [re.compile(p, re.IGNORECASE) for p in LOCAL_CRIME_PATTERNS]


# =============================================================================
# CATEGORY CLASSIFICATION PATTERNS
# =============================================================================

# Exclusion patterns - if these match, don't classify as international affairs
CATEGORY_EXCLUSION_PATTERNS = {
    "sports": SPORTS_NEWS_PATTERNS,
    "crime": LOCAL_CRIME_PATTERNS,
    "entertainment": ENTERTAINMENT_PATTERNS,
}

# International affairs keywords for category classification
INTERNATIONAL_AFFAIRS_KEYWORDS = {
    "war": [
        "war", "warfare", "invasion", "invade", "invaded",
        "airstrike", "air strike", "missile", "bombing", "bombed",
        "troops", "offensive", "military operation", "combat",
        "shelling", "artillery", "drone strike",
    ],
    "conflict": [
        "conflict", "clash", "clashes", "fighting",
        "battle", "skirmish", "ceasefire", "cease-fire",
        "hostilities", "armed conflict", "gunfire",
        "border tension", "territorial dispute",
    ],
    "politics": [
        "summit", "sanctions", "election", "elections",
        "president", "prime minister", "parliament",
        "government", "regime", "administration",
        "foreign minister", "state department", "foreign policy",
        "bilateral", "vote", "legislation",
    ],
    "security": [
        "nuclear", "cyberattack", "cyber attack",
        "espionage", "intelligence", "spy", "spying",
        "security threat", "national security",
        "hacking", "breach", "surveillance",
    ],
    "military": [
        "military", "army", "navy", "air force",
        "defense", "defence", "weapons", "deployment",
        "troops", "soldiers", "forces", "base", "bases",
        "warship", "fighter jet", "tank", "submarine",
    ],
    "terrorism": [
        "terrorist", "terrorism", "terror attack",
        "suicide bomb", "bombing", "explosion",
        "isis", "al-qaeda", "hamas", "hezbollah",
        "insurgent", "extremist", "militant",
    ],
    "diplomacy": [
        "diplomatic", "embassy", "ambassador",
        "treaty", "accord", "agreement", "talks",
        "negotiation", "summit", "bilateral",
        "un", "united nations", "nato", "eu",
    ],
    "protest": [
        "protest", "demonstration", "rally",
        "riot", "civil unrest", "uprising",
        "strike", "walkout", "march",
        "protesters", "demonstrators",
    ],
}


# =============================================================================
# DATE EXTRACTION PATTERNS
# =============================================================================

URL_DATE_PATTERNS = [
    # /2024/01/15/ or /2024-01-15/
    r"/(\d{4})[/-](\d{1,2})[/-](\d{1,2})/",
    # /20240115/ (compact)
    r"/(\d{4})(\d{2})(\d{2})/",
    # /2024/jan/15/ or /2024/january/15/
    r"/(\d{4})/(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*/(\d{1,2})/",
    # date=2024-01-15 or published=2024-01-15
    r"(?:date|published|time)=(\d{4})-(\d{1,2})-(\d{1,2})",
]

CONTENT_DATE_PATTERNS = [
    # January 15, 2024 or Jan 15, 2024
    r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2}),?\s+(\d{4})\b",
    # 15 January 2024
    r"\b(\d{1,2})\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{4})\b",
    # 2024-01-15
    r"\b(\d{4})-(\d{2})-(\d{2})\b",
]

# Past year detection
PAST_YEAR_PATTERN = r"\b(20[0-2][0-9])\b"  # 2000-2029


# =============================================================================
# SPECIFICITY PATTERNS
# =============================================================================

RECENT_DATE_PATTERNS = [
    r"\b(?:today|yesterday|this morning|this afternoon|this evening)\b",
    r"\b(?:hours? ago|minutes? ago)\b",
    r"\b(?:on (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b",
]

VAGUE_TIME_PATTERNS = [
    r"\b(?:recently|sometime|at some point|in recent days)\b",
    r"\b(?:reportedly|allegedly|according to sources)\b",
    r"\b(?:may have|might have|could have|possibly)\b",
]

SPECIFIC_NUMBER_PATTERNS = [
    r"\b\d+(?:,\d{3})*\s*(?:people|soldiers|troops|casualties|killed|injured|wounded|dead|missing)\b",
    r"\b(?:at least|more than|approximately|about|nearly|over)\s+\d+\b",
    r"\$\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:million|billion|trillion)?\b",
    r"\b\d+(?:\.\d+)?\s*(?:percent|%|kilometres?|kilometers?|miles?|km)\b",
]

# Compile specificity patterns
COMPILED_RECENT_DATE_PATTERNS = [re.compile(p, re.IGNORECASE) for p in RECENT_DATE_PATTERNS]
COMPILED_VAGUE_TIME_PATTERNS = [re.compile(p, re.IGNORECASE) for p in VAGUE_TIME_PATTERNS]
COMPILED_SPECIFIC_NUMBER_PATTERNS = [re.compile(p, re.IGNORECASE) for p in SPECIFIC_NUMBER_PATTERNS]


# =============================================================================
# BREAKING NEWS PATTERNS
# =============================================================================

BREAKING_KEYWORDS = [
    "breaking",
    "just in",
    "urgent",
    "flash",
    "developing",
    "alert",
    "live",
    "happening now",
]

BREAKING_TITLE_PATTERNS = [
    r"^BREAKING:",
    r"^JUST IN:",
    r"^URGENT:",
    r"^FLASH:",
    r"^DEVELOPING:",
    r"^ALERT:",
    r"^LIVE:",
]

COMPILED_BREAKING_PATTERNS = [re.compile(p, re.IGNORECASE) for p in BREAKING_TITLE_PATTERNS]


# =============================================================================
# SIGNIFICANCE INDICATORS
# =============================================================================
# Patterns that indicate international significance even in local incidents

SIGNIFICANCE_INDICATORS = [
    r"\b(?:international|foreign|diplomatic)\b",
    r"\b(?:government|military|official|state)\b",
    r"\b(?:mass|multiple|dozens|hundreds|thousands)\b",
    r"\b(?:terrorist|terror|extremist|militant)\b",
    r"\b(?:war|conflict|crisis|emergency)\b",
    r"\b(?:president|prime minister|minister|ambassador)\b",
]

COMPILED_SIGNIFICANCE_PATTERNS = [re.compile(p, re.IGNORECASE) for p in SIGNIFICANCE_INDICATORS]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def matches_any_pattern(text: str, patterns: list[Pattern]) -> bool:
    """Check if text matches any pattern in the list."""
    for pattern in patterns:
        if pattern.search(text):
            return True
    return False


def get_matching_patterns(text: str, patterns: list[Pattern]) -> list[str]:
    """Get list of patterns that matched the text."""
    matches = []
    for pattern in patterns:
        if pattern.search(text):
            matches.append(pattern.pattern)
    return matches


def count_pattern_matches(text: str, patterns: list[Pattern]) -> int:
    """Count how many patterns match the text."""
    count = 0
    for pattern in patterns:
        if pattern.search(text):
            count += 1
    return count


def is_international_affair(text: str) -> tuple[bool, str | None]:
    """
    Check if text relates to international affairs.

    Returns:
        Tuple of (is_international, category)
    """
    text_lower = text.lower()

    # First check exclusions
    for category, patterns in CATEGORY_EXCLUSION_PATTERNS.items():
        compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
        if matches_any_pattern(text, compiled):
            return False, category

    # Then check international keywords
    for category, keywords in INTERNATIONAL_AFFAIRS_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return True, category

    return False, None
