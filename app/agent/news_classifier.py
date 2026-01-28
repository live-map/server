"""
News Type Classifier - Distinguish between live events, data releases, and retrospective articles

Purpose:
- LIVE_EVENT: Currently happening events (include)
- DATA_RELEASE: Official reports/statistics released today about past periods (include with label)
- RETROSPECTIVE: Looking back at past events without new information (reject)
- UNKNOWN: Cannot determine type (include - conservative approach)

Key Decision:
- DATA_RELEASE articles ARE included as breaking news (with label)
- Only RETROSPECTIVE articles are rejected
"""

import re
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class NewsType(str, Enum):
    """News article type classification"""
    LIVE_EVENT = "live_event"           # Currently happening event
    DATA_RELEASE = "data_release"       # Official data/report released today
    RETROSPECTIVE = "retrospective"     # Looking back at past events
    UNKNOWN = "unknown"                 # Cannot determine


@dataclass
class ClassificationResult:
    """Result of news type classification"""
    news_type: NewsType
    confidence: float           # 0.0 to 1.0
    reason: str                 # Explanation
    is_publishable: bool        # True for LIVE_EVENT, DATA_RELEASE, UNKNOWN
    matched_patterns: list[str] # Patterns that matched


# ============================================
# Pattern Definitions
# ============================================

# DATA_RELEASE patterns - official data/reports released today
DATA_RELEASE_PATTERNS = {
    "en": [
        # Report releases
        r"\b(report|statistics|data|figures)\s+(released|published|shows?|reveals?)\b",
        r"\b(monthly|annual|quarterly|weekly)\s+(report|data|statistics|figures)\b",
        r"\breleased\s+(a\s+)?(report|data|statistics)\b",
        # Recorded/registered counts
        r"\b(recorded|reported|registered)\s+\d+\s+(deaths?|cases?|incidents?|victims?)\b",
        r"\b\d+\s+(deaths?|casualties|victims?)\s+(recorded|reported|registered)\b",
        # Time period data
        r"\b(in|during|for)\s+(january|february|march|april|may|june|july|august|september|october|november|december)\b",
        r"\b(last|previous)\s+(month|quarter|year)\b.*\d+",
        # Official announcements
        r"\bofficial\s+(data|figures|statistics|count)\b",
        r"\baccording\s+to\s+(official|government)\s+(data|report|statistics)\b",
    ],
    "es": [
        # Spanish report patterns
        r"\bcerr[oó]\s+con\s+\d+\b",                     # "cerró con 61"
        r"\bse\s+registr(aron|ó)\s+\d+\b",              # "se registraron 61"
        r"\b(mensual|anual|trimestral)\s+(informe|reporte|datos?)\b",
        r"\b(reporte|informe)\s+(publicado|divulgado)\b",
        r"\b(durante|en)\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b",
        r"\bseg[uú]n\s+(datos?|cifras|estad[ií]sticas)\s+oficial(es)?\b",
        # Period closings
        r"\b(balance|recuento)\s+(mensual|anual|del\s+mes)\b",
    ],
    "ko": [
        # Korean report patterns
        r"(발표|공개|집계).{0,10}(결과|통계|자료)",
        r"\d+[명건].*기록",
        r"(월|연|분기)\s*(보고서|통계|자료)",
        r"지난\s*(달|월|해|년).{0,20}\d+",
        r"공식\s*(발표|집계|통계)",
    ],
}

# RETROSPECTIVE patterns - looking back without new information
RETROSPECTIVE_PATTERNS = {
    "en": [
        # Looking back
        r"\blooking\s+back\b",
        r"\bin\s+retrospect\b",
        r"\breflecting\s+on\b",
        # Anniversaries
        r"\b(anniversary|commemoration|memorial)\s+(of|commemorat)",
        r"\b(anniversary)\s+(ceremony|event|celebration)",
        r"\byears?\s+ago\s+today\b",
        r"\bmarks?\s+the\s+\d+(st|nd|rd|th)?\s+anniversary\b",
        r"\b\d+\s+years?\s+since\b",
        # Remembering
        r"\bremember(ing)?\s+the\b",
        r"\bcommemorat(e|es|ing|ion)\b",
        # History pieces
        r"\bhistory\s+of\b.*\bevent\b",
        r"\bon\s+this\s+day\s+in\s+\d{4}\b",
        # Opinion/analysis of past
        r"\bwhat\s+we\s+learned\s+from\b",
        r"\blessons?\s+from\s+the\b",
        # P0 Fix: Additional patterns for commemoration/tribute articles
        r"\b(honors?|honouring|paying\s+tribute)\b",
        r"\bfallen\s+(soldiers?|troops?|heroes?)\b",
        r"\b(parade|celebration)\s+(highlights?|showcases?)\b",
        r"\b(Republic\s+Day|Independence\s+Day|Memorial\s+Day)\s+(parade|celebration|ceremony)\b",
        r"\b(pioneered|historic|landmark)\s+.{0,30}\b(tactics?|achievement|moment)\b",
        r"\btribute\s+to\b",
        r"\bpaid\s+(tribute|respects?)\b",
    ],
    "es": [
        # Spanish retrospective
        r"\bmirando\s+atr[aá]s\b",
        r"\ben\s+retrospectiva\b",
        r"\baniversario\s+de\b",
        r"\bhace\s+\d+\s+a[nñ]os\b",
        r"\bconmemora(ci[oó]n|r|ndo)\b",
        r"\brecordando\b",
    ],
    "ko": [
        # Korean retrospective
        r"회고",
        r"\d+주년",
        r"돌아보",
        r"기념(일|식|행사)",
        r"그때\s*그\s*사건",
    ],
}

# LIVE_EVENT patterns - currently happening
LIVE_EVENT_PATTERNS = {
    "en": [
        # Breaking indicators
        r"\bbreaking\b",
        r"\bjust\s+(now|in|happened)\b",
        r"\b(ongoing|developing|unfolding)\b",
        r"\blive\s+updates?\b",
        # Current action verbs
        r"\b(is|are)\s+(happening|occurring|taking\s+place)\b",
        r"\b(currently|now)\s+(happening|underway|ongoing)\b",
        # Emergency language
        r"\bemergency\s+(response|services|declared)\b",
        r"\bevacuation\s+(underway|ordered|in\s+progress)\b",
    ],
    "es": [
        # Spanish live
        r"\b[uú]ltima\s+hora\b",
        r"\bahora\s+mismo\b",
        r"\ben\s+vivo\b",
        r"\ben\s+curso\b",
        r"\bdesarroll[aá]ndose\b",
    ],
    "ko": [
        # Korean live
        r"속보",
        r"긴급",
        r"현재\s*진행",
        r"실시간",
        r"방금",
    ],
}

# Compile all patterns
_COMPILED_PATTERNS = {}

def _get_compiled_patterns():
    """Get or compile patterns lazily"""
    global _COMPILED_PATTERNS
    if not _COMPILED_PATTERNS:
        for news_type, lang_patterns in [
            ("data_release", DATA_RELEASE_PATTERNS),
            ("retrospective", RETROSPECTIVE_PATTERNS),
            ("live_event", LIVE_EVENT_PATTERNS),
        ]:
            _COMPILED_PATTERNS[news_type] = {}
            for lang, patterns in lang_patterns.items():
                _COMPILED_PATTERNS[news_type][lang] = [
                    re.compile(p, re.IGNORECASE) for p in patterns
                ]
    return _COMPILED_PATTERNS


def detect_language(text: str) -> str:
    """
    Simple language detection based on character patterns.

    Returns: 'en', 'es', or 'ko'
    """
    # Check for Korean characters
    if re.search(r'[\uAC00-\uD7A3]', text):
        return "ko"

    # Check for Spanish patterns
    spanish_indicators = [
        r'\b(el|la|los|las|un|una|unos|unas)\b',
        r'\b(que|de|en|con|por|para|del|al)\b',
        r'[áéíóúñ¿¡]',
        r'\b(se|fue|fueron|son|está|están)\b',
        r'\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b',
        r'\b(registr[oóa]|homicidios?|abusos?|cerr[oó])\b',
    ]
    spanish_score = sum(1 for p in spanish_indicators if re.search(p, text, re.IGNORECASE))
    if spanish_score >= 2:
        return "es"

    return "en"


def classify_news_type(
    title: str,
    content: str = "",
    current_date: datetime | None = None,
) -> ClassificationResult:
    """
    Classify news article type.

    Decision rules:
    - RETROSPECTIVE is the only type that gets rejected
    - DATA_RELEASE is included (with label)
    - LIVE_EVENT is included
    - UNKNOWN is included (conservative - don't reject if unsure)

    Args:
        title: Article title
        content: Article content (optional)
        current_date: Current date for context (optional)

    Returns:
        ClassificationResult with news type and publishability
    """
    if current_date is None:
        current_date = datetime.utcnow()

    text = f"{title} {content}".lower()
    lang = detect_language(text)
    compiled = _get_compiled_patterns()

    # Score each type
    scores = {
        NewsType.LIVE_EVENT: 0.0,
        NewsType.DATA_RELEASE: 0.0,
        NewsType.RETROSPECTIVE: 0.0,
    }
    matched_patterns = {
        NewsType.LIVE_EVENT: [],
        NewsType.DATA_RELEASE: [],
        NewsType.RETROSPECTIVE: [],
    }

    # Check patterns for detected language and English (as fallback)
    languages_to_check = [lang, "en"] if lang != "en" else ["en"]

    for news_type_str, type_patterns in compiled.items():
        news_type = NewsType(news_type_str)
        for check_lang in languages_to_check:
            if check_lang in type_patterns:
                for pattern in type_patterns[check_lang]:
                    match = pattern.search(text)
                    if match:
                        # Weight: more patterns = higher confidence
                        weight = 0.3 if news_type == NewsType.RETROSPECTIVE else 0.25
                        scores[news_type] += weight
                        matched_patterns[news_type].append(match.group(0))

    # Cap scores at 1.0
    for nt in scores:
        scores[nt] = min(scores[nt], 1.0)

    # Determine winning type
    max_score = max(scores.values())

    # Low confidence = UNKNOWN (publishable)
    if max_score < 0.25:
        return ClassificationResult(
            news_type=NewsType.UNKNOWN,
            confidence=0.0,
            reason="No clear type signals detected",
            is_publishable=True,
            matched_patterns=[],
        )

    # Get winning type
    winning_type = max(scores, key=scores.get)
    winning_patterns = matched_patterns[winning_type]

    # Build reason string
    if winning_type == NewsType.DATA_RELEASE:
        reason = f"DATA_RELEASE detected: {winning_patterns[:2]}"
    elif winning_type == NewsType.RETROSPECTIVE:
        reason = f"RETROSPECTIVE detected: {winning_patterns[:2]}"
    elif winning_type == NewsType.LIVE_EVENT:
        reason = f"LIVE_EVENT detected: {winning_patterns[:2]}"
    else:
        reason = "Classification uncertain"

    # Only RETROSPECTIVE is not publishable
    is_publishable = winning_type != NewsType.RETROSPECTIVE

    result = ClassificationResult(
        news_type=winning_type,
        confidence=scores[winning_type],
        reason=reason,
        is_publishable=is_publishable,
        matched_patterns=winning_patterns,
    )

    # Log for debugging
    if not is_publishable:
        logger.info(f"[NEWS-CLASSIFY] REJECT {winning_type.value}: {title[:50]}... | {reason}")
    elif winning_type == NewsType.DATA_RELEASE:
        logger.info(f"[NEWS-CLASSIFY] DATA_RELEASE (include with label): {title[:50]}...")

    return result
