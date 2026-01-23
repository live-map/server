# ADR-004: Hybrid Event Verification (v2)

## Status
Accepted (v2 - Updated 2025-01-23)

> **History**: 원래 ADR-004는 2단계 시스템(Rules -> LLM)을 설명했습니다. 이 v2는 Stage 2로 Zero-shot 분류를 추가합니다.

## Context

키워드 기반 뉴스 수집에는 근본적인 문제가 있습니다: **높은 거짓 양성률**. "attack", "missile", "war"와 같은 키워드를 검색할 때 다음과 같은 것들이 수집됩니다:
- 영화 리뷰 ("새로운 전쟁 영화 개봉")
- 비디오 게임 업데이트 ("콜 오브 듀티 공격 모드")
- 역사적 콘텐츠 ("1945년에 전쟁이 끝났다")
- 추측 ("러시아가 공격하면 NATO가...")
- 스포츠 ("프랑스가 아르헨티나의 수비를 공격")

초기 추정에 따르면 수집된 콘텐츠의 60-70%가 실제 뉴스 이벤트가 아니었습니다.

다음을 유지하면서 비이벤트를 필터링하는 효율적인 방법이 필요했습니다:
1. 비용을 낮게 유지
2. 높은 정확도 유지
3. 지연 시간 최소화

## Decision

**하이브리드 3단계 검증 시스템**을 구현합니다:

### Stage 1: Rule-Based Filter (Free, Fast)

명백한 비이벤트를 거부하기 위한 패턴 매칭:

```python
NOT_EVENT_PATTERNS = [
    # Entertainment
    r"\b(movie|film|tv show|series|drama|actor|actress)\b",
    r"\b(box office|premiere|trailer|sequel|franchise)\b",

    # Games
    r"\b(video game|gaming|esports|playstation|xbox)\b",
    r"\b(call of duty|fortnite|minecraft)\b",

    # History
    r"\b(in \d{4}|years ago|historically|decades ago)\b",
    r"\b(world war (i|ii|1|2))\s+(?!fears|concerns|tensions)",

    # Hypothetical
    r"\b(if .* would|could potentially|might happen)\b",
    r"\b(what if|scenario|simulation|prediction)\b",

    # Sports (English + Multilingual)
    r"\b(football|soccer|basketball|baseball|tennis)\b",
    r"\b(world cup|championship|tournament|playoffs)\b",
    r"(손흥민|황희찬|이강인)",  # Korean sports figures
    r"(皇马|巴萨|曼联)",  # Chinese sports teams
    r"(ريال مدريد|برشلونة)",  # Arabic sports teams
    # ...
]
```

**예상 필터링**: 비이벤트의 ~70%

### Stage 2: Zero-shot Classification (Free, Fast)

**v2의 새로운 기능**: LLM 전에 분류를 위한 로컬 ML 모델.

```python
# Using facebook/bart-large-mnli
from transformers import pipeline

classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

# Classification labels (CAMEO/ACLED based)
INTERNATIONAL_AFFAIRS_LABELS = [
    "military conflict",
    "diplomatic relations",
    "political crisis",
    "terrorism",
    "humanitarian crisis",
    "international sanctions",
    "protest and civil unrest",
]

REJECT_LABELS = [
    "sports",
    "entertainment",
    "local news",
    "opinion and analysis",
    "advertisement",
]
```

**신뢰도 임계값**:
- >= 0.8: 즉시 결정 (PASS 또는 REJECT)
- < 0.8: LLM으로 전달 (Stage 3)

**예상 결과**: 남은 이벤트의 ~70%가 LLM 없이 결정됨

### Stage 3: LLM Verification (Paid, Accurate)

Zero-shot이 불확실한 이벤트에 대해 LLM을 사용하여 검증합니다:

```python
PROMPT = """Today's date: {today}

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

REJECT if ANY of these:
- Single country domestic politics
- Sports (any language)
- Entertainment, celebrities
- Opinion/analysis articles

Text: {text}

## Output
VERDICT: PASS or REJECT
REASON: brief explanation
"""
```

**비용**: 검증당 ~$0.001 (GPT-4o-mini)

### Architecture Flow

```
Input Events (100%)
    ↓
Stage 1: Rules (~70% rejected, $0, ~1ms)
    ↓
Remaining Events (~30%)
    ↓
Stage 2: Zero-shot (~70% decided, $0, ~50ms)
    ↓
Uncertain Events (~9%)
    ↓
Stage 3: LLM (~10% rejected, $0.001/event, ~300ms)
    ↓
Verified Events (~20%)
```

### Error Handling (Updated in v2)

- **Stage 2 실패**: Stage 3로 건너뜀 (우아한 성능 저하)
- **Stage 3 타임아웃**: 거부 (보수적 접근)
- **Stage 3 오류**: 거부 및 로그
- **규칙 오류**: 로그 후 계속

> **v1에서의 변경**: LLM 오류는 이제 통과(허용적) 대신 거부(보수적)로 처리됩니다.

## Consequences

### Positive
- **비용 효율적**: 90%가 LLM 호출 없이 필터링됨
- **정확함**: 3계층 필터링이 정교한 거짓 양성을 포착
- **빠름**: 규칙은 마이크로초, Zero-shot은 ~50ms로 실행
- **우아한 성능 저하**: Zero-shot 또는 LLM 없이도 작동
- **투명함**: 각 단계에서 거부 이유가 로그됨
- **다국어**: 한국어, 중국어, 아랍어 스포츠 패턴 지원

### Negative
- 규칙은 패턴이 진화함에 따라 유지 관리가 필요함
- Zero-shot 모델은 ~1.2GB 메모리가 필요함
- 초기 모델 로딩에 ~10초 시작 시간이 추가됨
- 3단계 시스템이 단일 접근법보다 더 복잡함
- Zero-shot 정확도가 도메인에 따라 다양함

## Alternatives Considered

### Alternative A: LLM-Only Verification
모든 검증에 LLM을 사용합니다.

**기각 사유:**
- 10배 높은 비용 (이벤트당 $0.01)
- 모든 이벤트에 대해 높은 지연 시간
- 단일 장애점
- 명백한 경우에 과잉

### Alternative B: Rules-Only Verification
패턴 매칭만 사용합니다.

**기각 사유:**
- 정교한 거짓 양성을 포착할 수 없음
- 패턴 유지 관리 부담이 증가함
- 엣지 케이스에서 낮은 정확도
- 의미론적 이해가 없음

### Alternative C: ML Classification Model
이벤트 감지를 위한 맞춤형 분류기를 훈련시킵니다.

**Stage 2로 부분적으로 채택됨** - 맞춤형 훈련 대신 zero-shot 분류 사용:
- 레이블이 지정된 훈련 데이터가 필요 없음
- 사전 훈련된 모델이 잘 일반화됨
- CAMEO/ACLED 표준에서 해석 가능한 레이블

## Performance Characteristics

| Metric | Stage 1 (Rules) | Stage 2 (Zero-shot) | Stage 3 (LLM) |
|--------|-----------------|---------------------|---------------|
| Latency | ~1ms | ~50ms | ~300ms |
| Cost | $0 | $0 | $0.001/event |
| Accuracy | ~85% | ~90% | ~95% |
| Filter Rate | ~70% | ~70% of remaining | ~10% of remaining |

### Cost Comparison

| Approach | Cost/day (168 events x 96 scans) |
|----------|----------------------------------|
| LLM-only | $16.13 |
| 2-stage (v1) | $4.80 |
| 3-stage (v2) | **$1.44** |

## Implementation

```python
async def verify_event_hybrid(
    text: str,
    llm: ChatOpenAI | None = None,
    use_llm: bool = True,
    use_zero_shot: bool = True
) -> tuple[bool, str]:
    # Stage 1: Rules
    passed_rules, rejection = is_likely_real_event(text)
    if not passed_rules:
        return False, rejection

    # Stage 2: Zero-shot (if enabled)
    if use_zero_shot:
        is_intl, confidence, label = classify_with_zero_shot(text)
        if is_intl is not None and confidence >= 0.8:
            if is_intl:
                return True, f"ZERO_SHOT: {label} ({confidence:.2f})"
            else:
                return False, f"ZERO_SHOT_REJECT: {label} ({confidence:.2f})"

    # Stage 3: LLM (if enabled and needed)
    if use_llm and llm:
        try:
            return await verify_event_with_llm(text, llm)
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return False, "LLM_ERROR: verification failed"

    return True, "PASSED_RULES_ONLY"
```

## References
- 구현: `app/agent/event_verifier.py`
- Zero-shot 분류기: `app/agent/zero_shot_classifier.py`
- 게이트 순서: `docs/adr/ADR-002-gate-ordering.md`
- 프로젝트 문서: `docs/EVENT_VERIFICATION.md`
- Zero-shot 문서: `docs/architecture/ZERO_SHOT_CLASSIFIER.md`

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2025-01-23 | v1 | 초기 2단계 하이브리드 (Rules -> LLM) |
| 2025-01-23 | v2 | Zero-shot 분류 (Stage 2) 추가, LLM 오류 처리를 보수적으로 변경 |
