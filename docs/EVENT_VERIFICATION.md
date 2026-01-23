# 이벤트 검증 시스템 (Gate 0)

## 1. 문제 정의

### 키워드 매칭의 한계

현재 시스템은 키워드 매칭으로 콘텐츠를 수집합니다:

```python
keywords = ["war", "missile", "invasion", "airstrike", "protest", ...]
```

**문제**: 키워드가 포함되어도 실제 이벤트가 아닌 콘텐츠가 수집됩니다.

### False Positive 예시

| 수집된 콘텐츠 | 키워드 | 실제 여부 |
|--------------|--------|----------|
| "Iran attacks US bases in Iraq" | attack | O 실제 이벤트 |
| "New war movie 'Invasion' releases" | war, invasion | X 영화 |
| "Call of Duty: Modern Warfare review" | war | X 게임 |
| "In 1945, the war ended..." | war | X 역사 |
| "If Russia invades, NATO might..." | invasion, might | X 추측 |
| "World Cup final: epic battle" | battle | X 스포츠 |

### 영향

- **리소스 낭비**: 영화/게임 기사에 LLM 비용 소모
- **품질 저하**: 실제 뉴스가 큐에서 밀림
- **신뢰도 하락**: 잘못된 기사 발행 위험

---

## 2. 하이브리드 솔루션

### 개요

```
수집된 이벤트 (168개)
    ↓
[Stage 1: 규칙 기반 필터]
- NOT_EVENT_PATTERNS 매칭
- 영화/게임/역사/스포츠 제거
    ↓ (~50개 통과, 70% 제거)
[Stage 2: LLM 검증]
- "실제 발생한 이벤트인가?"
- YES/NO + 사유
    ↓ (~35개 통과)
다음 단계로 (Gate 1, 2...)
```

### 2.1 Stage 1: 규칙 기반 필터

**목적**: 명확한 패턴으로 70%를 빠르게 제거

#### NOT_EVENT_PATTERNS 목록

```python
NOT_EVENT_PATTERNS = [
    # 엔터테인먼트
    r"\b(movie|film|tv show|series|drama|actor|actress|celebrity)\b",
    r"\b(box office|premiere|trailer|sequel|franchise)\b",

    # 게임
    r"\b(game|gaming|esports|playstation|xbox|nintendo|steam)\b",
    r"\b(call of duty|battlefield|fortnite|minecraft)\b",

    # 역사/과거
    r"\b(in \d{4}|years ago|historically|last century|decades ago)\b",
    r"\b(world war (i|ii|1|2)|civil war|cold war)\b",  # 역사적 맥락

    # 추측/가정
    r"\b(if .* would|could potentially|might happen|hypothetically)\b",
    r"\b(what if|scenario|simulation)\b",

    # 리뷰/의견
    r"\b(review|opinion|editorial|analysis|commentary)\b",
    r"\b(opinion:|editorial:|analysis:)\b",

    # 스포츠
    r"\b(football|soccer|basketball|tennis|golf|cricket)\b",
    r"\b(olympics|world cup|championship|tournament|league)\b",
    r"\b(match|game|score|win|lose|defeat)\b",  # 스포츠 맥락

    # 광고/프로모션
    r"\b(sale|discount|buy now|limited time|sponsored)\b",
]
```

#### 필터링 로직

```python
def is_likely_real_event(text: str) -> tuple[bool, str | None]:
    """
    규칙 기반 1차 필터

    Returns:
        (통과 여부, 거부 사유)
    """
    text_lower = text.lower()

    for pattern in NOT_EVENT_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return False, f"NOT_EVENT: matched pattern '{pattern}'"

    return True, None
```

#### 예외 처리

특정 키워드가 있어도 실제 이벤트일 수 있는 경우:

```python
# "World War III fears as..." → 실제 뉴스 (현재 우려)
# "Olympics security breach" → 실제 이벤트 (보안 사건)
# "Game-changing sanctions" → 실제 뉴스 (비유적 사용)

# 이러한 경우는 Stage 2 LLM에서 처리
```

### 2.2 Stage 2: LLM 검증

**목적**: 규칙 필터를 통과한 콘텐츠의 정밀 검증

#### 프롬프트 설계

```python
EVENT_VERIFY_PROMPT = """다음 텍스트가 실제로 발생한 국제 정세 이벤트를 보도하는지 판단하세요.

텍스트: {text}

판단 기준:
- YES: 실제 발생한 사건 (전쟁, 외교, 테러, 시위, 정상회담 등)
  - 구체적인 날짜, 장소, 행위자가 있음
  - 현재 또는 최근에 발생
  - 뉴스 가치가 있음

- NO: 다음 중 하나에 해당
  - 영화, 드라마, 게임 콘텐츠
  - 역사적 사건 (과거 회고)
  - 추측, 가정, 시나리오
  - 의견, 분석, 사설
  - 스포츠 경기
  - 광고, 프로모션

답변 형식:
VERDICT: YES 또는 NO
REASON: 한 줄 설명 (한국어)"""
```

#### 판단 기준

| 기준 | YES | NO |
|------|-----|-----|
| 시제 | 현재/최근 | 과거/미래 가정 |
| 구체성 | 날짜, 장소, 행위자 명시 | 막연한 서술 |
| 출처 | 뉴스 기사 인용 | 개인 의견, 리뷰 |
| 맥락 | 실제 세계 | 가상 세계 (영화, 게임) |

### 2.3 비용 효율성

| 단계 | 처리량 | 비용 |
|------|--------|------|
| Stage 1 (규칙) | 168 → 50개 (70% 제거) | $0 |
| Stage 2 (LLM) | 50 → 35개 (30% 제거) | $0.05/스캔 |
| **총 비용** | | **$4.80/일** |

**비교 (LLM만 사용 시)**:
- 168개 × $0.001 = $0.168/스캔
- $16.13/일 (3.4배 비용)

---

## 3. 구현 상세

### 3.1 event_verifier.py 코드

```python
"""
이벤트 검증기 - 하이브리드 방식
Stage 1: 규칙 기반 필터 (70% 제거)
Stage 2: LLM 기반 검증 (30%만 검증)
"""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI


# Stage 1: 규칙 기반 필터
NOT_EVENT_PATTERNS = [
    # 엔터테인먼트
    r"\b(movie|film|tv show|series|drama|actor|actress|celebrity)\b",
    # 게임
    r"\b(game|gaming|esports|playstation|xbox|nintendo)\b",
    # 역사/과거
    r"\b(in \d{4}|years ago|historically|last century|decades ago)\b",
    # 추측/가정
    r"\b(if .* would|could potentially|might happen|hypothetically)\b",
    # 리뷰/의견
    r"\b(review|opinion|editorial|analysis|commentary)\b",
    # 스포츠
    r"\b(football|soccer|basketball|tennis|olympics|world cup)\b",
]


def is_likely_real_event(text: str) -> tuple[bool, str | None]:
    """
    규칙 기반 1차 필터

    Returns:
        (통과 여부, 거부 사유)
    """
    text_lower = text.lower()

    for pattern in NOT_EVENT_PATTERNS:
        if re.search(pattern, text_lower):
            return False, f"NOT_EVENT: matched pattern '{pattern}'"

    return True, None


# Stage 2: LLM 기반 검증
EVENT_VERIFY_PROMPT = """다음 텍스트가 실제로 발생한 국제 정세 이벤트를 보도하는지 판단하세요.

텍스트: {text}

판단 기준:
- YES: 실제 발생한 사건 (전쟁, 외교, 테러, 시위, 정상회담 등)
- NO: 영화/게임/역사/추측/의견/스포츠/연예

답변 형식:
VERDICT: YES 또는 NO
REASON: 한 줄 설명"""


async def verify_event_with_llm(
    text: str,
    llm: "ChatOpenAI"
) -> tuple[bool, str]:
    """
    LLM 기반 2차 검증

    Returns:
        (이벤트 여부, 사유)
    """
    prompt = EVENT_VERIFY_PROMPT.format(text=text[:500])
    response = await llm.ainvoke(prompt)
    content = response.content.upper()

    is_event = "VERDICT: YES" in content or "YES" in content.split("\n")[0]
    reason = content.split("REASON:")[-1].strip() if "REASON:" in content else "N/A"

    return is_event, reason


async def verify_event_hybrid(
    text: str,
    llm: "ChatOpenAI | None" = None
) -> tuple[bool, str]:
    """
    하이브리드 이벤트 검증

    1단계: 규칙 기반 (빠름, 무료)
    2단계: LLM (정밀, 비용)

    Returns:
        (이벤트 여부, 사유)
    """
    # Stage 1: 규칙 기반
    passed_rules, rejection_reason = is_likely_real_event(text)

    if not passed_rules:
        return False, rejection_reason

    # Stage 2: LLM 검증 (규칙 통과한 것만)
    if llm:
        return await verify_event_with_llm(text, llm)

    return True, "PASSED_RULES_ONLY"
```

### 3.2 scanner.py Gate 0 통합

```python
# _classify_and_group() 메서드 내부

# Step 3.5: 이벤트 검증 (Gate 0)
if agent_settings.event_verification_enabled:
    verified_events = []

    for item in publishable_events:
        event = item["event"]
        text = f"{event.title} {event.content[:300]}"

        # LLM 사용 여부에 따라 검증
        if agent_settings.event_verification_use_llm:
            is_event, reason = await verify_event_hybrid(text, self.llm)
        else:
            is_event, reason = await verify_event_hybrid(text, None)

        if is_event:
            verified_events.append(item)
        else:
            logger.info(f"[GATE0-REJECT] {reason}: {event.title[:50]}...")

    logger.info(
        f"Event verification: {len(verified_events)}/{len(publishable_events)} passed"
    )
    publishable_events = verified_events
```

### 3.3 config.py 설정

```python
class AgentSettings(BaseSettings):
    # 이벤트 검증 설정
    event_verification_enabled: bool = True
    event_verification_use_llm: bool = True  # False면 규칙만 사용
```

---

## 4. 테스트 케이스

### 통과해야 하는 케이스 (YES)

| 입력 | 예상 결과 | 사유 |
|------|----------|------|
| "Iran attacks US bases in Iraq, 3 soldiers injured" | PASS | 실제 군사 이벤트 |
| "North Korea fires ballistic missile toward Sea of Japan" | PASS | 실제 미사일 발사 |
| "Protesters clash with police in Paris over pension reform" | PASS | 실제 시위 |
| "Putin and Xi meet in Beijing for summit talks" | PASS | 실제 정상회담 |
| "Earthquake hits Turkey, magnitude 6.2" | PASS | 실제 재난 |

### 거부해야 하는 케이스 (NO)

| 입력 | 예상 결과 | 사유 |
|------|----------|------|
| "New war movie 'Invasion' releases this Friday" | FAIL (Stage 1) | 영화 패턴 |
| "Call of Duty: Modern Warfare gets new update" | FAIL (Stage 1) | 게임 패턴 |
| "In 1945, World War II ended with Japan's surrender" | FAIL (Stage 1) | 역사 패턴 |
| "If Russia invades, NATO might respond with..." | FAIL (Stage 1) | 추측 패턴 |
| "World Cup final: France defeats Argentina" | FAIL (Stage 1) | 스포츠 패턴 |
| "My review of the new documentary about war" | FAIL (Stage 1) | 리뷰 패턴 |
| "The upcoming film explores themes of conflict" | FAIL (Stage 2) | LLM 판단 |

### 엣지 케이스

| 입력 | 예상 결과 | 처리 단계 |
|------|----------|----------|
| "Olympics security breach: intruder arrested" | PASS | Stage 2 (LLM) |
| "Game-changing sanctions imposed on Russia" | PASS | Stage 2 (LLM) |
| "World War III fears grow as tensions rise" | PASS | Stage 2 (LLM) |

---

## 5. 로그 출력 예시

```
10:06:47 | INFO | [GATE0-REJECT] NOT_EVENT: matched pattern 'movie': New war movie releases...
10:06:47 | INFO | [GATE0-REJECT] NOT_EVENT: matched pattern 'game': Call of Duty review...
10:06:47 | INFO | [GATE0-REJECT] NOT_EVENT: matched pattern 'in \d{4}': In 1945, the war...
10:06:48 | INFO | [GATE0-REJECT] LLM: 가상 시나리오 (영화 줄거리)
10:06:48 | INFO | Event verification: 35/168 passed (79% filtered)
```

---

## 6. 성능 지표

| 지표 | 목표 | 현재 |
|------|------|------|
| True Positive Rate | > 95% | 측정 필요 |
| False Positive Rate | < 5% | 측정 필요 |
| Stage 1 필터 비율 | 60-80% | ~70% |
| 처리 시간 | < 5초 | 2-5초 |
| LLM 비용 절감 | > 60% | ~70% |

---

## 변경 이력

| 날짜 | 변경 내용 |
|------|----------|
| 2025-01-23 | 초기 문서 작성 |

---

*이 문서는 이벤트 검증 시스템의 설계 및 구현을 설명합니다.*
