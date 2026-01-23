"""
이벤트 검증기 - 하이브리드 방식

Stage 1: 규칙 기반 필터 (70% 제거, $0)
Stage 2: LLM 기반 검증 (30%만 검증, $0.001/건)

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
    r"\bwhy .{1,50} (is|are|isn't|not)\b",
    r"\bhow .{1,50} (can|could|should|will)\b",
    r"\bwhat .{1,50} (means|tells|shows)\b",
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
# Stage 2: LLM 기반 검증
# ============================================

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
    LLM 기반 2차 검증

    Args:
        text: 검증할 텍스트
        llm: LangChain ChatOpenAI 인스턴스

    Returns:
        (이벤트 여부, 사유)
    """
    # 텍스트 길이 제한 (토큰 절약)
    truncated_text = text[:500]
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = EVENT_VERIFY_PROMPT.format(text=truncated_text, today=today)

    try:
        response = await llm.ainvoke(prompt)
        content = response.content.strip()

        # 응답 파싱
        lines = content.split("\n")
        verdict_line = ""
        for line in lines:
            if "VERDICT:" in line.upper():
                verdict_line = line
                break

        # PASS = 통과, REJECT = 거부
        is_event = "PASS" in verdict_line.upper()

        # REASON 추출
        reason = "N/A"
        for line in lines:
            if "REASON:" in line.upper():
                reason = line.split(":", 1)[-1].strip()
                break

        return is_event, reason

    except Exception as e:
        logger.warning(f"LLM verification error: {e}")
        # 에러 시 통과 (false positive보다 false negative가 나음)
        return True, f"LLM_ERROR: {str(e)[:50]}"


async def verify_event_hybrid(
    text: str,
    llm: "ChatOpenAI | None" = None,
    use_llm: bool = True
) -> tuple[bool, str]:
    """
    하이브리드 이벤트 검증

    1단계: 규칙 기반 (빠름, 무료)
    2단계: LLM (정밀, 비용) - 선택적

    Args:
        text: 검증할 텍스트 (title + content)
        llm: LangChain ChatOpenAI 인스턴스 (None이면 규칙만 적용)
        use_llm: LLM 검증 활성화 여부

    Returns:
        (이벤트 여부, 사유)
    """
    # Stage 1: 규칙 기반 필터
    passed_rules, rejection_reason = is_likely_real_event(text)

    if not passed_rules:
        logger.debug(f"[GATE0-RULES] Rejected: {rejection_reason}")
        return False, rejection_reason

    # Stage 2: LLM 검증 (규칙 통과한 것만)
    if use_llm and llm:
        is_event, reason = await verify_event_with_llm(text, llm)
        if not is_event:
            logger.debug(f"[GATE0-LLM] Rejected: {reason}")
            return False, f"LLM: {reason}"
        return True, f"PASSED: {reason}"

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
    ("TikTok deal between China and White House finalized", True),  # NEW: "deal" 패턴 수정 테스트
    ("Anti-ICE protest erupts at federal building", True),  # NEW: protest 테스트

    # 거부해야 함 (이벤트 아님)
    ("New war movie 'Invasion' releases this Friday", False),
    ("Call of Duty: Modern Warfare gets new update", False),
    ("In 1945, World War II ended with Japan's surrender", False),
    ("If Russia invades, NATO might respond with force", False),
    ("World Cup final: France defeats Argentina 3-2", False),
    ("My review of the new documentary about war", False),
    ("Game of Thrones season 8 episode 3 battle scene", False),
    ("50% off sale on military-style jackets", False),
    ("손흥민이 토트넘에서 해트트릭 기록", False),  # NEW: 한국어 스포츠 테스트
    ("Why the Ukraine war is changing global politics", False),  # NEW: 분석 기사 테스트
]


async def run_tests(llm: "ChatOpenAI | None" = None):
    """테스트 케이스 실행"""
    print("\n" + "=" * 70)
    print("EVENT VERIFIER TEST")
    print("=" * 70)

    passed = 0
    failed = 0

    for text, expected in TEST_CASES:
        is_event, reason = await verify_event_hybrid(text, llm, use_llm=llm is not None)

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
    asyncio.run(run_tests())
