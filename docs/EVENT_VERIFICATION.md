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

## 2. 3단계 하이브리드 솔루션

### 개요

```
수집된 이벤트 (168개)
    ↓
[Stage 1: 규칙 기반 필터] - $0, ~1ms
- NOT_EVENT_PATTERNS 매칭
- 다국어 스포츠 패턴 (한/아/중)
    ↓ (~50개 통과, 70% 제거)
[Stage 2: Zero-shot 분류] - $0, ~50ms
- BART-large-MNLI 로컬 모델
- 확신도 ≥ 0.8 → 바로 결정
- 확신도 < 0.8 → Stage 3으로
    ↓ (~40개 통과 또는 LLM 전달)
[Stage 3: LLM 검증] - $0.001/건, ~300ms
- Edge cases만 처리
- PASS/REJECT + REASON
    ↓
검증된 이벤트 (~35개)
```

### 2.1 Stage 1: 규칙 기반 필터

**목적**: 명확한 패턴으로 70%를 빠르게 제거

#### NOT_EVENT_PATTERNS 목록

```python
NOT_EVENT_PATTERNS = [
    # 엔터테인먼트
    r"\b(movie|film|tv show|series|drama|actor|actress|celebrity)\b",
    r"\b(box office|premiere|trailer|sequel|franchise|streaming)\b",
    r"\b(grammy|oscar|emmy|golden globe|award show)\b",

    # 게임
    r"\b(video game|gaming|esports|playstation|xbox|nintendo|steam)\b",
    r"\b(call of duty|battlefield|fortnite|minecraft|league of legends)\b",
    r"\b(game update|patch notes|dlc|expansion pack)\b",

    # 역사/과거
    r"\b(in \d{4}|years ago|historically|last century|decades ago)\b",
    r"\b(world war (i|ii|1|2)|civil war|cold war)\s+(?!fears|concerns|tensions)",
    r"\b(anniversary of|commemorat|memorial)\b",

    # 추측/가정
    r"\b(if .* would|could potentially|might happen|hypothetically)\b",
    r"\bif .* (might|could|may) ",
    r"\b(what if|scenario|simulation|thought experiment)\b",
    r"\b(prediction|forecast|speculation)\b",

    # 리뷰/의견/분석
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

    # 광고/프로모션
    r"\b(sale|discount|buy now|limited time|sponsored|ad)\b",
    r"\b(promo code|coupon|offer expires|flash sale|limited offer)\b",

    # 소설/픽션
    r"\b(novel|fiction|story|tale|book review)\b",
    r"\b(chapter|episode|season \d+)\b",
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

    for pattern in COMPILED_PATTERNS:
        match = pattern.search(text_lower)
        if match:
            return False, f"NOT_EVENT: pattern matched '{match.group()}'"

    return True, None
```

### 2.2 Stage 2: Zero-shot 분류

**목적**: 규칙 필터 통과 후, LLM 호출 전 로컬 모델로 분류

#### 모델: facebook/bart-large-mnli

- **Zero-shot classification** 기능 제공
- 로컬에서 실행 (API 비용 $0)
- 처리 시간: ~50ms/건

#### 분류 레이블 (CAMEO/ACLED 기반)

```python
# 국제 정세 레이블 (통과)
INTERNATIONAL_AFFAIRS_LABELS = [
    "military conflict",
    "diplomatic relations",
    "political crisis",
    "terrorism",
    "humanitarian crisis",
    "international sanctions",
    "protest and civil unrest",
]

# 비국제 정세 레이블 (거부)
REJECT_LABELS = [
    "sports",
    "entertainment",
    "local news",
    "opinion and analysis",
    "advertisement",
]
```

#### 신뢰도 임계값

```python
ZERO_SHOT_HIGH_CONFIDENCE = 0.8  # 이 이상이면 바로 결정
ZERO_SHOT_LOW_CONFIDENCE = 0.5   # 이 이하면 LLM 검증
```

| 확신도 | 동작 |
|--------|------|
| ≥ 0.8 | 바로 결정 (PASS 또는 REJECT) |
| 0.5-0.8 | LLM으로 전달 |
| < 0.5 | LLM으로 전달 |

### 2.3 Stage 3: LLM 검증

**목적**: Zero-shot이 불확실한 Edge cases만 LLM으로 정밀 검증

#### 프롬프트 설계 (PASS/REJECT 형식)

```python
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
- Single country domestic politics
- Sports (any language)
- Entertainment, celebrities
- Opinion/analysis articles
- Local crime, accidents

## Input
Text: {text}

## Output (exactly this format)
VERDICT: PASS or REJECT
REASON: brief explanation"""
```

#### 판단 기준

| 기준 | PASS | REJECT |
|------|------|--------|
| 범위 | 2개국 이상 관련 | 단일 국가 국내 문제 |
| 시제 | 현재/최근 | 과거/미래 가정 |
| 맥락 | 실제 세계 | 가상 세계 (영화, 게임) |
| 출처 | 뉴스 기사 인용 | 개인 의견, 리뷰 |

### 2.4 비용 효율성 (3단계 파이프라인)

| 단계 | 처리량 | 비용 | 시간 |
|------|--------|------|------|
| Stage 1 (규칙) | 168 → 50개 (70% 제거) | $0 | ~1ms |
| Stage 2 (Zero-shot) | 50 → 15개 LLM 전달 (70% 결정) | $0 | ~50ms |
| Stage 3 (LLM) | 15 → 10개 통과 | $0.015/스캔 | ~300ms |
| **총 비용** | | **$1.44/일** | |

**비교 (LLM만 사용 시)**:
- 168개 × $0.001 = $0.168/스캔
- $16.13/일 (11배 비용 절감!)

---

## 3. 구현 상세

### 3.1 event_verifier.py 구조

```python
"""
이벤트 검증기 - 3단계 하이브리드 방식
Stage 1: 규칙 기반 필터 (70% 제거, $0)
Stage 2: Zero-shot 분류 (local model, 확신도 높으면 결정)
Stage 3: LLM 기반 검증 (edge cases만, $0.001/건)
"""

async def verify_event_hybrid(
    text: str,
    llm: "ChatOpenAI | None" = None,
    use_llm: bool = True,
    use_zero_shot: bool = True
) -> tuple[bool, str]:
    """
    하이브리드 이벤트 검증 (3단계)
    """
    # Stage 1: 규칙 기반 필터
    passed_rules, rejection_reason = is_likely_real_event(text)
    if not passed_rules:
        return False, rejection_reason

    # Stage 2: Zero-shot 분류 (선택적)
    if use_zero_shot:
        is_intl, confidence, label = classify_with_zero_shot(text)
        if is_intl is not None and confidence >= ZERO_SHOT_HIGH_CONFIDENCE:
            if is_intl:
                return True, f"ZERO_SHOT: {label} ({confidence:.2f})"
            else:
                return False, f"ZERO_SHOT_REJECT: {label} ({confidence:.2f})"

    # Stage 3: LLM 검증 (불확실한 경우만)
    if use_llm and llm:
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

        is_event, reason = await verify_event_hybrid(
            text,
            self.llm if agent_settings.event_verification_use_llm else None,
            use_llm=agent_settings.event_verification_use_llm,
            use_zero_shot=agent_settings.event_verification_use_zero_shot
        )

        if is_event:
            verified_events.append(item)
        else:
            logger.info(f"[GATE0-REJECT] {reason}: {event.title[:50]}...")

    publishable_events = verified_events
```

### 3.3 config.py 설정

```python
class AgentSettings(BaseSettings):
    # 이벤트 검증 설정
    event_verification_enabled: bool = True
    event_verification_use_llm: bool = True
    event_verification_use_zero_shot: bool = True  # Zero-shot 분류 활성화
```

---

## 4. 테스트 케이스

### 통과해야 하는 케이스 (PASS)

| 입력 | 예상 결과 | 사유 |
|------|----------|------|
| "Iran attacks US bases in Iraq, 3 soldiers injured" | PASS | 실제 군사 이벤트 |
| "North Korea fires ballistic missile toward Sea of Japan" | PASS | 실제 미사일 발사 |
| "Protesters clash with police in Paris over pension reform" | PASS | 국제적 시위 |
| "Putin and Xi meet in Beijing for summit talks" | PASS | 실제 정상회담 |
| "TikTok deal between China and White House finalized" | PASS | 미-중 무역/기술 협상 |
| "Anti-ICE protest erupts at federal building" | PASS | 시위 이벤트 |

### 거부해야 하는 케이스 (REJECT)

| 입력 | 예상 결과 | 처리 단계 |
|------|----------|----------|
| "New war movie 'Invasion' releases this Friday" | REJECT | Stage 1 (영화 패턴) |
| "Call of Duty: Modern Warfare gets new update" | REJECT | Stage 1 (게임 패턴) |
| "In 1945, World War II ended with Japan's surrender" | REJECT | Stage 1 (역사 패턴) |
| "If Russia invades, NATO might respond with..." | REJECT | Stage 1 (추측 패턴) |
| "World Cup final: France defeats Argentina" | REJECT | Stage 1 (스포츠 패턴) |
| "손흥민이 토트넘에서 해트트릭 기록" | REJECT | Stage 1 (한국어 스포츠) |
| "Why the Ukraine war is changing global politics" | REJECT | Stage 1 (분석 기사) |

### 엣지 케이스 (Stage 2 또는 3에서 처리)

| 입력 | 예상 결과 | 처리 단계 |
|------|----------|----------|
| "Olympics security breach: intruder arrested" | PASS | Stage 2/3 (LLM) |
| "Game-changing sanctions imposed on Russia" | PASS | Stage 2/3 (LLM) |
| "World War III fears grow as tensions rise" | PASS | Stage 2/3 (LLM) |

---

## 5. 로그 출력 예시

```
10:06:47 | INFO | [GATE0-RULES] Rejected: NOT_EVENT: pattern 'movie' matched
10:06:47 | INFO | [GATE0-RULES] Rejected: NOT_EVENT: pattern 'game' matched
10:06:47 | INFO | [GATE0-ZEROSHOT] Passed: military conflict (0.87)
10:06:48 | INFO | [GATE0-ZEROSHOT] Rejected: sports (0.92)
10:06:48 | INFO | [GATE0-ZEROSHOT] Uncertain: protest and civil unrest (0.65), forwarding to LLM
10:06:49 | INFO | [GATE0-LLM] Passed: International protest with diplomatic implications
10:06:49 | INFO | Event verification: 35/168 passed (79% filtered)
```

---

## 6. 성능 지표

| 지표 | 목표 | Stage 1 | Stage 2 | Stage 3 |
|------|------|---------|---------|---------|
| Latency | < 500ms | ~1ms | ~50ms | ~300ms |
| Cost/event | 최소화 | $0 | $0 | $0.001 |
| Accuracy | > 90% | ~85% | ~90% | ~95% |
| Filter Rate | 높을수록 좋음 | ~70% | ~70% of remaining | ~10% |

### 전체 파이프라인

| 지표 | 목표 | 현재 |
|------|------|------|
| True Positive Rate | > 95% | 측정 필요 |
| False Positive Rate | < 5% | 측정 필요 |
| 총 처리 시간 | < 500ms | ~350ms |
| LLM 비용 절감 | > 80% | ~90% |

---

## 7. 에러 처리

### Stage별 Graceful Degradation

```python
# Stage 2 실패 시 → Stage 3로 (Zero-shot 모델 로딩 실패)
try:
    from app.agent.zero_shot_classifier import get_zero_shot_classifier
    classifier = get_zero_shot_classifier()
except ImportError:
    logger.warning("Zero-shot classifier not available, skipping")
    # LLM으로 바로 전달

# Stage 3 실패 시 → 거부 (보수적 접근)
except Exception as e:
    logger.error(f"LLM verification error: {e}")
    return False, f"LLM_ERROR: verification failed"
```

---

## 변경 이력

| 날짜 | 변경 내용 |
|------|----------|
| 2025-01-23 | 초기 문서 작성 (2단계 파이프라인) |
| 2025-01-23 | 3단계 파이프라인으로 업데이트 (Zero-shot 추가) |

---

*관련 문서:*
- [ADR-004: Hybrid Event Verification](./adr/ADR-004-hybrid-verification.md)
- [Zero-shot Classification](./ZERO_SHOT_CLASSIFICATION.md)
