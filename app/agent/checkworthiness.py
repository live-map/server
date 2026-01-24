"""
Check-worthiness 감지 모듈

목적: 연예, 추측, 일반 배경 콘텐츠 거부

Based on 2026 fact-checking research:
- Check-worthiness = "claims the general public would want to know the truth of"
- Filter out: entertainment, speculation, promotional, background content
"""

import re
from dataclasses import dataclass
from enum import Enum


class RejectionReason(Enum):
    ENTERTAINMENT = "entertainment"      # 연예/스포츠/라이프스타일
    SPECULATION = "speculation"          # 추측/의견/미래 예측
    BACKGROUND = "background"            # 일반 배경/역사
    PROMOTIONAL = "promotional"          # 광고/홍보
    HUMAN_INTEREST = "human_interest"    # 인물 특집/미담 기사
    LOCAL_INCIDENT = "local_incident"    # 로컬 사건 (교통사고, 지역 범죄 등)
    NONE = "none"                        # 거부 사유 없음


@dataclass
class CheckWorthinessResult:
    is_checkworthy: bool
    rejection_reason: RejectionReason
    confidence: float
    matched_patterns: list[str]


# 연예/스포츠 키워드
# Note: "interview" alone is too broad - must combine with celebrity context
ENTERTAINMENT_PATTERNS = [
    r"\b(actor|actress|celebrity|star|singer|musician|athlete)\b",
    r"\b(celebrity|star|actor|actress).*(interview|talks about|shares|reveals)\b",
    r"\b(interview|talks about|shares|reveals|opens up).*(celebrity|star|actor|actress)\b",
    r"\b(movie|film|album|concert|tour|premiere|red carpet)\b",
    r"\b(dating|relationship|married|divorced|breakup)\b",
    r"\b(fashion|style|outfit|looks|wearing)\b",
    r"\b(reality tv|talk show)\b",
    # Personal sharing language (celebrity interview style)
    r"\b(shared|reveals|opens up).*(insights?|thoughts|feelings|experience)\b",
    r"\b(personal growth|self-discovery|healing journey|lowest point)\b",
    r"\bduring (an |the )?interview\b",
]

# 추측/의견 키워드
SPECULATION_PATTERNS = [
    r"\b(might|could|may|possibly|potentially|rumor)\b",
    r"\b(speculates?|speculation|predicted|prediction)\b",
    r"\b(analysts? (say|believe|think|expect))\b",
    r"\b(sources? (say|claim|suggest))\b(?!.*confirmed)",
]

# 일반 배경 패턴
BACKGROUND_PATTERNS = [
    r"\b(since \d{4}|for decades?|for years?|historically)\b",
    r"\b(ongoing|continues to|has been|long-standing)\b",
    r"\b(context|background|overview|history of)\b",
]

# 홍보/광고 패턴
PROMOTIONAL_PATTERNS = [
    r"\b(sponsored|advertisement|ad|promo)\b",
    r"\b(buy now|order now|limited time|discount)\b",
    r"\b(subscribe|sign up|join now)\b",
]

# 인물 특집/미담 기사 패턴 (Human Interest)
# 사건이 아닌 개인의 이야기, 커뮤니티 선행 등
HUMAN_INTEREST_PATTERNS = [
    # 개인 활동 묘사
    r"\b(preparing for|prepares for|dedicated (him|her)self)\b",
    r"\b(his|her) (mission|journey|efforts?|commitment|dedication)\b",
    r"\b(has been|is) (actively )?(involved in|helping|supporting)\b",
    # 자선/커뮤니티 활동
    r"\b(fundraising|charity|humanitarian (efforts?|work))\b",
    r"\b(community donations?|local (businesses?|residents?))\b",
    r"\b(aid trip|relief (trip|mission|effort))\b",
    # 개인 인터뷰/감정 표현
    r"\b(expressed (his|her) gratitude|hopes? to (make|raise|inspire))\b",
    r"\b(privilege to help|inspired many|make a difference)\b",
    r"\b(in (a recent|an) interview|stated|expressed)\b",
    # 마일스톤/기록
    r"\b(milestone|final (trip|mission|journey)|20th|10th|first)\b",
    # 직업 + 지역 묘사 (개인 프로필)
    r"\b(local|Hambleton|a \w+ man|a \w+ woman)\b.*\b(driver|volunteer|worker)\b",
]

# ============================================
# 로컬 사건 패턴 (방어선 3)
# ============================================
LOCAL_INCIDENT_PATTERNS = [
    # Traffic/Road incidents
    r"\b(traffic|road|highway|street)\s+(accident|crash|collision|incident|closure)\b",
    r"\b(car|truck|vehicle|bus|lorry|laster)\s+(crash|accident|collision|wreck)\b",
    r"\b(slid|slipped|skidded|lost\s+control|veered|rutschen)\b",

    # Local authority mentions (without international context)
    r"\b(local|regional|city|town|county)\s+(police|authorities|fire|emergency)\b",
    r"\bpolizeiauto\b",  # German: police car

    # Minor incident indicators
    r"\b(no\s+(?:serious\s+)?injuries?|minor\s+injuries?|non.?fatal)\b",
    r"\b(weather.?related|icy|snow|rain|fog|glatteis).{0,30}(accident|crash|incident)\b",

    # German local news patterns
    r"\b(niedersachsen|bremen|bayern|nordrhein.?westfalen|hamburg|berlin).{0,30}(unfall|polizei)\b",
    r"\b(promenade|autobahn)\s+(unfall|accident|crash)\b",
]

# ============================================
# 국제적 중요성 지표 (방어선 4)
# 로컬 사건이라도 이 패턴이 있으면 통과
# ============================================
SIGNIFICANCE_INDICATORS = [
    # Mass casualties (10+) - both "47 killed" and "kills 47" formats
    r"\b(\d{2,}|dozens|hundreds|thousands)\s+(killed|dead|casualties|injured|died)\b",
    r"\b(kills?|killed)\s+(\d{2,}|dozens|hundreds|thousands)\b",
    r"\b(mass\s+casualty|multiple\s+fatalities|death\s+toll|body\s+count)\b",
    r"\b(massacre|mass\s+shooting|terror)\b",

    # International involvement
    r"\b(international|cross.?border|multiple\s+countries|foreign)\b",
    r"\b(embassy|consulate|diplomat|foreign\s+national)\b",
    r"\b(UN|NATO|EU|G7|G20)\s+(response|statement|meeting)\b",

    # Government/Official response
    r"\b(president|prime\s+minister|chancellor|minister)\s+(respond|statement|declare|condemn)\b",
    r"\b(state\s+of\s+emergency|martial\s+law|national\s+security)\b",
    r"\b(federal|national)\s+(response|investigation|alert)\b",

    # Critical infrastructure
    r"\b(airport|seaport|border).{0,20}(closed?|shutdown|evacuate)\b",
    r"\b(power\s+grid|nuclear|dam).{0,20}(attack|failure|breach|collapse)\b",
    r"\b(cyber.?attack|infrastructure\s+attack)\b",
]


def check_significance(text: str) -> tuple[bool, int, list[str]]:
    """
    Check if event has international significance.

    Args:
        text: Text to check

    Returns:
        (is_significant, indicator_count, matched_patterns)
    """
    matched = []
    for pattern in SIGNIFICANCE_INDICATORS:
        if re.search(pattern, text, re.IGNORECASE):
            matched.append(pattern)
    return len(matched) >= 1, len(matched), matched


def check_worthiness(
    text: str,
    entertainment_threshold: int = 2,
    speculation_threshold: int = 2,
    human_interest_threshold: int = 3,
    local_incident_threshold: int = 2,
) -> CheckWorthinessResult:
    """
    텍스트의 check-worthiness 평가

    Args:
        text: 평가할 텍스트
        entertainment_threshold: 연예 패턴 매칭 임계값
        speculation_threshold: 추측 패턴 매칭 임계값
        human_interest_threshold: 인물 특집/미담 패턴 매칭 임계값
        local_incident_threshold: 로컬 사건 패턴 매칭 임계값

    Returns:
        CheckWorthinessResult with is_checkworthy, rejection_reason, confidence
    """
    text_lower = text.lower()

    # 연예 패턴 체크
    entertainment_matches = []
    for pattern in ENTERTAINMENT_PATTERNS:
        if re.search(pattern, text_lower):
            entertainment_matches.append(f"entertainment:{pattern}")
    if len(entertainment_matches) >= entertainment_threshold:
        return CheckWorthinessResult(
            is_checkworthy=False,
            rejection_reason=RejectionReason.ENTERTAINMENT,
            confidence=0.9,
            matched_patterns=entertainment_matches
        )

    # 추측 패턴 체크
    speculation_matches = []
    for pattern in SPECULATION_PATTERNS:
        if re.search(pattern, text_lower):
            speculation_matches.append(f"speculation:{pattern}")
    if len(speculation_matches) >= speculation_threshold:
        return CheckWorthinessResult(
            is_checkworthy=False,
            rejection_reason=RejectionReason.SPECULATION,
            confidence=0.85,
            matched_patterns=speculation_matches
        )

    # 홍보 패턴 체크
    promotional_matches = []
    for pattern in PROMOTIONAL_PATTERNS:
        if re.search(pattern, text_lower):
            promotional_matches.append(f"promotional:{pattern}")
    if len(promotional_matches) >= 1:
        return CheckWorthinessResult(
            is_checkworthy=False,
            rejection_reason=RejectionReason.PROMOTIONAL,
            confidence=0.95,
            matched_patterns=promotional_matches
        )

    # 인물 특집/미담 패턴 체크 (Human Interest)
    human_interest_matches = []
    for pattern in HUMAN_INTEREST_PATTERNS:
        if re.search(pattern, text, re.I):  # case insensitive
            human_interest_matches.append(f"human_interest:{pattern}")
    if len(human_interest_matches) >= human_interest_threshold:
        return CheckWorthinessResult(
            is_checkworthy=False,
            rejection_reason=RejectionReason.HUMAN_INTEREST,
            confidence=0.85,
            matched_patterns=human_interest_matches
        )

    # ============================================
    # 로컬 사건 패턴 체크 (방어선 3) + Significance Override (방어선 4)
    # ============================================
    local_incident_matches = []
    for pattern in LOCAL_INCIDENT_PATTERNS:
        if re.search(pattern, text, re.I):  # case insensitive
            local_incident_matches.append(f"local_incident:{pattern}")

    if len(local_incident_matches) >= local_incident_threshold:
        # 로컬 사건 패턴 매칭됨 - significance 체크
        is_significant, sig_count, sig_patterns = check_significance(text)

        if is_significant:
            # Significance indicator가 있으면 통과 (대형 사고 등)
            # 로그용으로 패턴 정보만 반환
            return CheckWorthinessResult(
                is_checkworthy=True,
                rejection_reason=RejectionReason.NONE,
                confidence=0.8,
                matched_patterns=[
                    f"local_patterns:{len(local_incident_matches)}",
                    f"significance_override:{sig_count}",
                ]
            )
        else:
            # 로컬 사건이고 significance 없음 - 거부
            return CheckWorthinessResult(
                is_checkworthy=False,
                rejection_reason=RejectionReason.LOCAL_INCIDENT,
                confidence=0.85,
                matched_patterns=local_incident_matches
            )

    return CheckWorthinessResult(
        is_checkworthy=True,
        rejection_reason=RejectionReason.NONE,
        confidence=1.0,
        matched_patterns=[]
    )
