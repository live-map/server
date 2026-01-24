"""
이벤트 검증기 - 하이브리드 방식

Stage 1: 규칙 기반 필터 (70% 제거, $0)
Stage 2: Zero-shot 분류 (local model, 확신도 높으면 결정)
Stage 3: LLM 기반 검증 (edge cases만, $0.001/건)

목적:
- 키워드 매칭으로 수집된 콘텐츠 중 실제 이벤트만 통과
- False Positive 제거: 영화, 게임, 역사, 추측, 스포츠 등
"""

import re
import logging
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


# ============================================
# Stage 1: 규칙 기반 필터
# ============================================

# 이벤트가 아닌 콘텐츠 패턴
NOT_EVENT_PATTERNS = [
    # 엔터테인먼트
    r"\b(movie|film|tv show|series|drama|actor|actress|celebrity)\b",
    r"\b(box office|premiere|trailer|sequel|franchise|streaming)\b",
    r"\b(grammy|oscar|emmy|golden globe|award show)\b",

    # 게임
    r"\b(video game|gaming|esports|playstation|xbox|nintendo|steam)\b",
    r"\b(call of duty|battlefield|fortnite|minecraft|league of legends)\b",
    r"\b(game update|patch notes|dlc|expansion pack)\b",

    # 역사/과거 이벤트
    r"\b(in \d{4}|years ago|historically|last century|decades ago)\b",
    r"\b(world war (i|ii|1|2)|civil war|cold war)\s+(?!fears|concerns|tensions)",
    r"\b(anniversary of|commemorat|memorial)\b",

    # 추측/가정/시나리오
    r"\b(if .* would|could potentially|might happen|hypothetically)\b",
    r"\bif .* (might|could|may) ",  # "If X, Y might/could/may..."
    r"\b(what if|scenario|simulation|thought experiment)\b",
    r"\b(prediction|forecast|speculation)\b",

    # 리뷰/의견/분석 (개선)
    r"\b(review|opinion|editorial|commentary)\b",
    r"\b(my thoughts on|i think|in my opinion)\b",
    r"\bwhy \S{1,50} (is|are|isn't|not)\b",
    r"\bhow \S{1,50} (can|could|should|will)\b",
    r"\bwhat \S{1,50} (means|tells|shows)\b",
    r"\b(explained|breakdown|deep dive|explainer)\b",

    # 스포츠 (영어)
    r"\b(football|soccer|basketball|baseball|tennis|golf|cricket|rugby)\b",
    r"\b(olympics|world cup|championship|tournament|league|playoffs)\b",
    r"\b(match|game score|win|lose|defeat|victory)\s+(?!military|war)",
    r"\b(nba|nfl|mlb|nhl|fifa|uefa)\b",

    # 스포츠 (다국어 - 한국어)
    r"(레알 마드리드|바르셀로나|맨체스터|리버풀|첼시|아스널|토트넘)",
    r"(손흥민|황희찬|이강인|김민재)",
    r"(프리미어리그|라리가|분데스리가|세리에A|K리그)",

    # 스포츠 (다국어 - 아랍어)
    r"(ريال مدريد|برشلونة|مانشستر|ليفربول)",

    # 스포츠 (다국어 - 중국어)
    r"(皇马|巴萨|曼联|利物浦|拜仁|切尔西)",

    # 광고/프로모션 (수정됨 - "deal" 제거)
    r"\b(sale|discount|buy now|limited time|sponsored|ad)\b",
    r"\b(promo code|coupon|offer expires|flash sale|limited offer)\b",

    # 소설/픽션
    r"\b(novel|fiction|story|tale|book review)\b",
    r"\b(chapter|episode|season \d+)\b",

    # ============================================
    # 스포츠 확장 패턴 (P0 개선)
    # ============================================
    # 사이클/자전거 경기
    r"\b(cyclist|cycling|bicycle race|bike race|peloton|velodrome)\b",
    r"\b(tour de france|giro|vuelta|classic|stage race)\b",
    r"\b(sprint|time trial|breakaway|gruppetto)\b",

    # 모터스포츠/랠리
    r"\b(rally|rallying|dakar|wrc|formula|f1|motorsport|racing)\b",
    r"\b(grand prix|pole position|podium finish|pit stop)\b",
    r"\b(driver|racer|team principal|constructor)\b",

    # 일반 스포츠 결과/승리 패턴
    r"\b(triumphs?|wins?|defeats?|loses?|victory|victories)\b(?!.*(?:military|war|battle|forces))",
    r"\b(champion|championship|title|trophy|medal|gold|silver|bronze)\b",
    r"\b(final|semi.?final|quarter.?final|round of|group stage)\b",
    r"\b(score|scored|scoring|goal|assist|save)\b(?!.*(?:military|war))",
    r"\b(athlete|player|coach|manager|captain|striker|goalkeeper)\b",
    r"\b(team|squad|roster|lineup|starting eleven)\b(?!.*(?:military|special ops))",

    # 리그/대회 이름
    r"\b(premier league|la liga|serie a|bundesliga|ligue 1)\b",
    r"\b(champions league|europa league|world series|super bowl)\b",
    r"\b(australian open|us open|wimbledon|french open|masters)\b",

    # ============================================
    # 범죄 뉴스 패턴 (로컬 범죄 필터링)
    # ============================================
    # 살인/폭력 (국제적 맥락 없음)
    r"\b(murder|homicide|killing|manslaughter)\b(?!.*(?:war crime|genocide|mass|terror))",
    r"\b(stabbing|stabbed|knifing|knifed)\b(?!.*(?:terror|mass))",
    r"\b(shooting|shot|gunman)\b(?!.*(?:military|war|terror|mass|school))",
    r"\b(assault|assaulted|battery|beaten|beat)\b(?!.*(?:military|police brutality))",

    # 절도/강도 (로컬)
    r"\b(robbery|robbed|burglary|burglar|theft|thief|stolen)\b(?!.*(?:bank heist|art theft))",
    r"\b(shoplifting|pickpocket|mugging|mugged|carjacking)\b",

    # 마약/음주 관련 범죄
    r"\b(drug bust|drug arrest|dui|dwi|drunk driving)\b",
    r"\b(possession|trafficking)\b(?!.*(?:weapon|nuclear|arms))",

    # 아동 범죄 (로컬)
    r"\b(child abuse|child neglect|custody dispute|juvenile)\b",
    r"\b(foster care|social services|cps|child protective)\b",

    # 법원/재판 (로컬)
    r"\b(arraigned|arraignment|bail|bond hearing|plea)\b",
    r"\b(sentenced|sentencing|parole|probation)\b(?!.*(?:war crime|tribunal|international))",
    r"\b(misdemeanor|felony|conviction|convicted)\b(?!.*(?:war crime|corruption|political))",

    # ============================================
    # 로컬 뉴스 / 교통사고 (방어선 1)
    # ============================================
    # Traffic accidents (not internationally significant)
    r"\b(traffic accident|car crash|road accident|vehicle collision|car accident)\b",
    r"\b(traffic jam|road closure|roadblock|traffic congestion)\b",
    r"\b(fender bender|minor accident|single.?vehicle)\b",
    r"\b(slip|slide|slid|skid|skidded).{0,20}(road|street|highway|promenade)\b",
    r"\b(icy road|icy conditions|black ice|winter driving)\b",
    r"\bno\s+(serious\s+)?injuries?\s+reported\b",

    # German local news patterns
    r"\b(rutschen|unfall|autobahn.?unfall|verkehrsunfall|glatteis)\b",
    r"\b(niedersachsen|bremen|bayern|nordrhein.?westfalen).{0,30}(unfall|polizei)\b",

    # Local authority mentions (without international context)
    r"\b(local police|local authorities|regional police|city police)\b",
    r"\b(local incident|local crime|petty crime|street crime)\b",
]

# 컴파일된 패턴 (성능 최적화)
COMPILED_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in NOT_EVENT_PATTERNS]


def is_likely_real_event(text: str) -> tuple[bool, str | None]:
    """
    규칙 기반 1차 필터

    Args:
        text: 검증할 텍스트 (title + content)

    Returns:
        (통과 여부, 거부 사유)
    """
    text_lower = text.lower()

    for i, pattern in enumerate(COMPILED_PATTERNS):
        match = pattern.search(text_lower)
        if match:
            return False, f"NOT_EVENT: pattern '{NOT_EVENT_PATTERNS[i]}' matched '{match.group()}'"

    return True, None


# ============================================
# Stage 2: Zero-shot 분류
# ============================================

def classify_with_zero_shot(text: str) -> tuple[bool | None, float, str]:
    """
    Zero-shot 분류기로 텍스트 분류

    Args:
        text: 분류할 텍스트

    Returns:
        (is_international, confidence, label)
        - is_international: 국제 정세 여부 (None이면 불확실)
        - confidence: 신뢰도
        - label: 분류 레이블
    """
    try:
        from app.agent.zero_shot_classifier import get_zero_shot_classifier
        classifier = get_zero_shot_classifier()
        return classifier.classify(text)
    except ImportError:
        logger.warning("Zero-shot classifier not available, skipping")
        return None, 0.0, "UNAVAILABLE"
    except Exception as e:
        logger.warning(f"Zero-shot classification error: {e}")
        return None, 0.0, f"ERROR: {e}"


# ============================================
# Stage 3: LLM 기반 검증
# ============================================


def _sanitize_text_for_llm(text: str) -> str:
    """
    Sanitize text before sending to LLM to mitigate prompt injection.

    - Remove potential injection patterns (VERDICT:, REASON:)
    - Remove control characters
    - Normalize whitespace
    """
    import re

    # Remove potential injection patterns (case-insensitive)
    sanitized = re.sub(r'\b(VERDICT|REASON|OUTPUT|PASS|REJECT)\s*:', '[REMOVED]:', text, flags=re.IGNORECASE)

    # Remove control characters except newlines and tabs
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', sanitized)

    # Normalize excessive whitespace
    sanitized = re.sub(r'\s{3,}', '  ', sanitized)

    return sanitized


EVENT_VERIFY_PROMPT = """Today's date: {today}

## Task
Determine if this text reports an INTERNATIONAL AFFAIRS event.

## Definition
International affairs = events involving 2+ countries OR global security implications.

## Classification

PASS if ANY of these:
- Military conflict between nations
- Diplomatic meeting/negotiation between countries
- International sanctions, treaties, agreements
- UN/NATO/international organization actions
- Cross-border humanitarian crisis
- Terrorism with international implications
- Protests with international significance

REJECT if ANY of these:
- Single country domestic politics (US immigration court, local elections)
- Sports (any language)
- Entertainment, celebrities
- Opinion/analysis articles
- Local crime, accidents

## Examples

Input: "Putin meets Trump envoys as Kremlin says Ukraine settlement hinges on territory"
Output: PASS - Russia-US diplomatic meeting about Ukraine - 3 countries involved

Input: "Judge warns Trump administration on immigration status"
Output: REJECT - US domestic legal matter - single country

Input: "TikTok deal between China and White House finalized"
Output: PASS - US-China trade/tech deal - 2 countries

## Input
Text: {text}

## Output (exactly this format)
VERDICT: PASS or REJECT
REASON: brief explanation"""


async def verify_event_with_llm(
    text: str,
    llm: "ChatOpenAI"
) -> tuple[bool, str]:
    """
    LLM 기반 검증

    Args:
        text: 검증할 텍스트
        llm: LangChain ChatOpenAI 인스턴스

    Returns:
        (이벤트 여부, 사유)
    """
    # 텍스트 길이 제한 및 sanitize (토큰 절약 + 보안)
    truncated_text = _sanitize_text_for_llm(text[:500])
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = EVENT_VERIFY_PROMPT.format(text=truncated_text, today=today)

    try:
        response = await llm.ainvoke(prompt)
        content = response.content.strip()

        # 응답 파싱 - LLM 응답에서만 VERDICT 찾기 (첫 번째만 사용)
        lines = content.split("\n")
        verdict_line = ""
        reason = "N/A"
        verdict_found = False

        for line in lines:
            line_upper = line.upper().strip()
            # 첫 번째 VERDICT만 사용 (prompt injection 방지)
            if not verdict_found and "VERDICT:" in line_upper:
                verdict_line = line
                verdict_found = True
            # REASON도 첫 번째만 사용
            elif "REASON:" in line_upper and reason == "N/A":
                reason = line.split(":", 1)[-1].strip()[:100]  # 길이 제한

        # PASS = 통과, REJECT = 거부
        is_event = "PASS" in verdict_line.upper() and "REJECT" not in verdict_line.upper()

        return is_event, reason

    except Exception as e:
        logger.error(f"LLM verification error: {e}")
        # 에러 시 거부 (보수적 접근 - false negative보다 안전)
        return False, f"LLM_ERROR: verification failed - {str(e)[:30]}"


# ============================================
# 하이브리드 검증 파이프라인
# ============================================

# Zero-shot 신뢰도 임계값
ZERO_SHOT_HIGH_CONFIDENCE = 0.8  # 이 이상이면 바로 결정
ZERO_SHOT_LOW_CONFIDENCE = 0.5   # 이 이하면 LLM 검증

# 낮은 신뢰도로도 거부할 레이블 (방어선 2)
# "local news"는 0.15 이상이면 거부 (더 적극적인 필터링)
REJECT_LABELS_STRICT = {
    "local news": 0.15,
    "local incident": 0.15,
    "traffic news": 0.20,
}


async def verify_event_hybrid(
    text: str,
    llm: "ChatOpenAI | None" = None,
    use_llm: bool = True,
    use_zero_shot: bool = True
) -> tuple[bool, str]:
    """
    하이브리드 이벤트 검증 (3단계)

    1단계: 규칙 기반 (빠름, 무료)
    2단계: Zero-shot 분류 (로컬 모델, 확신도 높으면 결정)
    3단계: LLM (정밀, 비용) - 불확실한 경우만

    Args:
        text: 검증할 텍스트 (title + content)
        llm: LangChain ChatOpenAI 인스턴스 (None이면 규칙만 적용)
        use_llm: LLM 검증 활성화 여부
        use_zero_shot: Zero-shot 분류 활성화 여부

    Returns:
        (이벤트 여부, 사유)
    """
    # Stage 1: 규칙 기반 필터
    passed_rules, rejection_reason = is_likely_real_event(text)

    if not passed_rules:
        logger.debug(f"[GATE0-RULES] Rejected: {rejection_reason}")
        return False, rejection_reason

    # Stage 2: Zero-shot 분류 (선택적)
    if use_zero_shot:
        is_intl, confidence, label = classify_with_zero_shot(text)

        # 방어선 2: "local news" 등 특정 레이블은 낮은 신뢰도로도 거부
        label_lower = label.lower() if label else ""
        for reject_label, min_confidence in REJECT_LABELS_STRICT.items():
            if reject_label in label_lower and confidence >= min_confidence:
                logger.debug(
                    f"[GATE0-ZEROSHOT] Strict reject: {label} ({confidence:.2f}) "
                    f"[threshold={min_confidence}]"
                )
                return False, f"ZERO_SHOT_STRICT_REJECT: {label} ({confidence:.2f})"

        if is_intl is not None and confidence >= ZERO_SHOT_HIGH_CONFIDENCE:
            # 확신도 높으면 바로 결정
            if is_intl:
                logger.debug(f"[GATE0-ZEROSHOT] Passed: {label} ({confidence:.2f})")
                return True, f"ZERO_SHOT: {label} ({confidence:.2f})"
            else:
                logger.debug(f"[GATE0-ZEROSHOT] Rejected: {label} ({confidence:.2f})")
                return False, f"ZERO_SHOT_REJECT: {label} ({confidence:.2f})"

        # 중간 확신도는 LLM으로 넘김
        if is_intl is not None:
            logger.debug(f"[GATE0-ZEROSHOT] Uncertain: {label} ({confidence:.2f}), forwarding to LLM")

    # Stage 3: LLM 검증 (불확실한 경우만)
    if use_llm and llm:
        is_event, reason = await verify_event_with_llm(text, llm)
        if not is_event:
            logger.debug(f"[GATE0-LLM] Rejected: {reason}")
            return False, f"LLM: {reason}"
        return True, f"LLM_PASSED: {reason}"

    return True, "PASSED_RULES_ONLY"


# ============================================
# 테스트 케이스
# ============================================

TEST_CASES = [
    # 통과해야 함 (실제 이벤트)
    ("Iran attacks US bases in Iraq, 3 soldiers injured", True),
    ("North Korea fires ballistic missile toward Sea of Japan", True),
    ("Protesters clash with police in Paris over pension reform", True),
    ("Putin and Xi meet in Beijing for summit talks", True),
    ("M6.2 earthquake hits Turkey, 15 dead", True),
    ("Israeli forces conduct airstrike on Gaza", True),
    ("TikTok deal between China and White House finalized", True),  # "deal" 패턴 수정 테스트
    ("Anti-ICE protest erupts at federal building", True),  # protest 테스트

    # 거부해야 함 (이벤트 아님)
    ("New war movie 'Invasion' releases this Friday", False),
    ("Call of Duty: Modern Warfare gets new update", False),
    ("In 1945, World War II ended with Japan's surrender", False),
    ("If Russia invades, NATO might respond with force", False),
    ("World Cup final: France defeats Argentina 3-2", False),
    ("My review of the new documentary about war", False),
    ("Game of Thrones season 8 episode 3 battle scene", False),
    ("50% off sale on military-style jackets", False),
    ("손흥민이 토트넘에서 해트트릭 기록", False),  # 한국어 스포츠 테스트
    ("Why the Ukraine war is changing global politics", False),  # 분석 기사 테스트
]


async def run_tests(llm: "ChatOpenAI | None" = None, use_zero_shot: bool = False):
    """테스트 케이스 실행"""
    print("\n" + "=" * 70)
    print("EVENT VERIFIER TEST")
    print(f"Zero-shot: {'ON' if use_zero_shot else 'OFF'}, LLM: {'ON' if llm else 'OFF'}")
    print("=" * 70)

    passed = 0
    failed = 0

    for text, expected in TEST_CASES:
        is_event, reason = await verify_event_hybrid(
            text, llm, use_llm=llm is not None, use_zero_shot=use_zero_shot
        )

        if is_event == expected:
            status = "PASS"
            passed += 1
        else:
            status = "FAIL"
            failed += 1

        print(f"\n[{status}] Expected: {expected}, Got: {is_event}")
        print(f"  Text: {text[:60]}...")
        print(f"  Reason: {reason}")

    print(f"\n{'=' * 70}")
    print(f"Results: {passed}/{passed + failed} passed ({passed / (passed + failed) * 100:.1f}%)")
    print("=" * 70)


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_tests(use_zero_shot=False))
