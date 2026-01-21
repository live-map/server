"""
Specificity 감지 모듈

목적: 구체적 날짜/장소/숫자 없는 일반 배경 기사 거부

Criteria:
- Recent date (within 7 days)
- Specific location (city/region names)
- Specific numbers (casualties, amounts, times)
"""

import re
from dataclasses import dataclass
from datetime import datetime




@dataclass
class SpecificityResult:
    is_specific: bool
    has_recent_date: bool       # 최근 7일 이내 날짜
    has_specific_location: bool  # 도시/지역명
    has_specific_numbers: bool   # 구체적 숫자 (사상자, 금액 등)
    score: float                 # 0-1 점수
    details: dict


# 최근 날짜 패턴 (2026년 1월 기준)
RECENT_DATE_PATTERNS = [
    r"\b(January|Jan\.?) (1[4-9]|2[0-9]|3[01]),? 2026\b",
    r"\b(February|Feb\.?) \d{1,2},? 2026\b",
    r"\b(today|yesterday|this morning|this week|hours? ago)\b",
    r"\b202[6]-0[12]-\d{2}\b",
    r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b",
]

# 모호한 시간 표현 (거부 대상)
VAGUE_TIME_PATTERNS = [
    r"\bsince \d{4}\b",
    r"\bfor (decades?|years?|months?)\b",
    r"\b(ongoing|continues?|long-standing)\b",
    r"\bhistorically\b",
]

# 구체적 장소 (수도, 주요 도시)
SPECIFIC_LOCATIONS = [
    # Ukraine/Russia
    r"\b(Kyiv|Moscow|Beijing|Washington|London|Paris|Berlin)\b",
    r"\b(Kharkiv|Mariupol|Odesa|Odessa|Donetsk|Luhansk)\b",
    r"\b(Crimea|Zaporizhzhia|Kherson|Bakhmut|Avdiivka)\b",
    # Middle East
    r"\b(Gaza|Tel Aviv|Jerusalem|Ramallah|Beirut|Damascus)\b",
    r"\b(Tehran|Baghdad|Riyadh|Sanaa|Aden)\b",
    # Asia
    r"\b(Taipei|Seoul|Pyongyang|Tokyo|Manila|Jakarta)\b",
    # Africa
    r"\b(Khartoum|Nairobi|Lagos|Cairo|Addis Ababa)\b",
    # Europe
    r"\b(Warsaw|Prague|Budapest|Vienna|Brussels|Geneva)\b",
    # Americas
    r"\b(Mexico City|Bogota|Caracas|Havana|Buenos Aires)\b",
]

# 모호한 장소 (거부 대상)
VAGUE_LOCATIONS = [
    r"\b(in the region|in the area|various regions?)\b",
    r"\b(across the country|throughout the nation)\b",
    r"\b(border areas?|frontlines?)\b",
    r"\b(somewhere|elsewhere|nearby)\b",
]

# 구체적 숫자 패턴
SPECIFIC_NUMBER_PATTERNS = [
    r"\b\d{1,3}(,\d{3})* (killed|dead|wounded|injured|casualties)\b",
    r"\b\d+ (people|soldiers?|civilians?|troops?|fighters?)\b",
    r"\$\d{1,3}(,\d{3})*(\.\d+)? (million|billion)?\b",
    r"\b\d{1,2}:\d{2} (AM|PM|UTC|GMT|local time)\b",
    r"\bat least \d+\b",
    r"\b(approximately|about|around) \d+\b",
]


def check_specificity(text: str, min_score: float = 0.4) -> SpecificityResult:
    """
    텍스트의 specificity 평가

    Args:
        text: 평가할 텍스트
        min_score: 최소 점수 임계값 (default: 0.4)

    Returns:
        SpecificityResult with is_specific, score, and details
    """
    text_lower = text.lower()

    # 최근 날짜 체크
    has_recent_date = any(re.search(p, text, re.I) for p in RECENT_DATE_PATTERNS)
    has_vague_time = any(re.search(p, text_lower) for p in VAGUE_TIME_PATTERNS)

    # 구체적 장소 체크
    has_specific_location = any(re.search(p, text, re.I) for p in SPECIFIC_LOCATIONS)
    has_vague_location = any(re.search(p, text_lower) for p in VAGUE_LOCATIONS)

    # 구체적 숫자 체크
    has_specific_numbers = any(re.search(p, text, re.I) for p in SPECIFIC_NUMBER_PATTERNS)

    # 점수 계산
    score = 0.0
    if has_recent_date:
        score += 0.4
    if has_specific_location:
        score += 0.3
    if has_specific_numbers:
        score += 0.3

    # 모호한 표현이 있으면 감점
    if has_vague_time and not has_recent_date:
        score -= 0.3
    if has_vague_location and not has_specific_location:
        score -= 0.2

    score = max(0.0, min(1.0, score))

    # 임계값 이상이어야 구체적
    is_specific = score >= min_score

    return SpecificityResult(
        is_specific=is_specific,
        has_recent_date=has_recent_date,
        has_specific_location=has_specific_location,
        has_specific_numbers=has_specific_numbers,
        score=score,
        details={
            "has_vague_time": has_vague_time,
            "has_vague_location": has_vague_location,
        }
    )
