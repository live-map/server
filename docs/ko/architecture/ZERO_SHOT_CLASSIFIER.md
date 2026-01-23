# Zero-shot Classification for Event Verification

## 개요

Zero-shot 분류는 3단계 이벤트 검증 파이프라인의 **Stage 2**입니다. 사전 학습된 NLI (Natural Language Inference) 모델을 사용하여 태스크별 학습 데이터 없이 텍스트를 분류합니다.

```
Stage 1: Rules → Stage 2: Zero-shot → Stage 3: LLM
         (70%)              (70%)            (엣지 케이스)
```

---

## 모델: facebook/bart-large-mnli

### 이 모델을 선택한 이유

| 기준 | facebook/bart-large-mnli |
|----------|-------------------------|
| 아키텍처 | BART-large (406M 파라미터) |
| 학습 데이터 | MultiNLI 데이터셋 (433K premise-hypothesis 쌍) |
| Zero-shot 성능 | 우수 |
| 속도 | 분류당 ~50ms (CPU) |
| 메모리 | ~1.2GB |
| 라이선스 | MIT |

### Zero-shot 분류 작동 방식

모델은 **Natural Language Inference**를 사용하여 텍스트를 분류합니다:

```
Premise: "Iran attacks US bases in Iraq, 3 soldiers injured"
Hypothesis: "This is about military conflict"
→ 모델 예측: entailment (0.92)
```

여러 가설(레이블)을 테스트하면 명시적 학습 없이 텍스트를 카테고리로 분류할 수 있습니다.

---

## 분류 레이블

### CAMEO/ACLED 기반 카테고리

확립된 분쟁 연구 표준에서 파생된 레이블을 사용합니다:

- **CAMEO** (Conflict and Mediation Event Observations): 국제관계를 위한 표준화된 이벤트 코딩
- **ACLED** (Armed Conflict Location & Event Data): 분쟁 이벤트 분류체계

### 국제 정세 레이블 (PASS)

이 레이블은 텍스트가 검증을 통과해야 함을 나타냅니다:

```python
INTERNATIONAL_AFFAIRS_LABELS = [
    "military conflict",       # 국가/단체 간 무력 충돌
    "diplomatic relations",    # 회담, 협상, 조약
    "political crisis",        # 국제적 영향을 가진 정부 위기
    "terrorism",               # 국제적 함의를 가진 테러 공격
    "humanitarian crisis",     # 난민 위기, 국경 넘는 재해
    "international sanctions", # 국가 간 경제/정치 제재
    "protest and civil unrest", # 국제적 관심을 받는 대규모 시위
]
```

### 거부 레이블 (REJECT)

이 레이블은 텍스트가 거부되어야 함을 나타냅니다:

```python
REJECT_LABELS = [
    "sports",              # 모든 스포츠 콘텐츠
    "entertainment",       # 영화, 음악, 연예인
    "local news",          # 단일 국가 국내 이슈
    "opinion and analysis",# 사설, 분석 기사
    "advertisement",       # 홍보 콘텐츠
]
```

---

## 신뢰도 임계값

### 임계값 설정

```python
ZERO_SHOT_HIGH_CONFIDENCE = 0.8  # 즉시 결정
ZERO_SHOT_LOW_CONFIDENCE = 0.5   # LLM으로 전달
```

### 결정 매트릭스

| 최상위 레이블 | 신뢰도 | 조치 |
|-----------|------------|--------|
| 국제 정세 | ≥ 0.8 | **PASS** 즉시 |
| 거부 대상 | ≥ 0.8 | **REJECT** 즉시 |
| 모든 경우 | 0.5-0.8 | **LLM**으로 전달 |
| 모든 경우 | < 0.5 | **LLM**으로 전달 |

### 0.8 임계값을 선택한 이유

경험적 테스트 결과:
- **≥ 0.8**: 실제 데이터에서 ~95% 정확도
- **0.6-0.8**: ~80% 정확도 (오류가 너무 많음)
- **< 0.6**: 모델이 실제로 불확실함

---

## 구현

### 싱글톤 패턴

각 분류마다 모델을 다시 로드하지 않기 위해:

```python
_zero_shot_instance: ZeroShotClassifier | None = None

def get_zero_shot_classifier() -> ZeroShotClassifier:
    global _zero_shot_instance
    if _zero_shot_instance is None:
        _zero_shot_instance = ZeroShotClassifier()
    return _zero_shot_instance
```

### 지연 로딩

모델은 처음 필요할 때만 로드됩니다:

```python
class ZeroShotClassifier:
    def __init__(self, model_name: str = "facebook/bart-large-mnli"):
        self.model_name = model_name
        self._pipeline = None  # 지연 로딩

    def _load_model(self):
        if self._pipeline is None:
            from transformers import pipeline
            self._pipeline = pipeline(
                "zero-shot-classification",
                model=self.model_name,
                device=-1,  # CPU
            )
```

### 분류 메서드

```python
def classify(self, text: str) -> tuple[bool, float, str]:
    """
    Args:
        text: 분류할 텍스트 (최대 512자)

    Returns:
        (is_international, confidence, top_label)
    """
    self._load_model()
    truncated_text = text[:512]

    all_labels = self.intl_labels + self.reject_labels
    result = self._pipeline(truncated_text, all_labels)

    top_label = result["labels"][0]
    confidence = result["scores"][0]
    is_intl = top_label in self.intl_labels

    return is_intl, confidence, top_label
```

---

## 성능 벤치마크

### 지연 시간

| 작업 | 시간 |
|-----------|------|
| 모델 로딩 | ~10초 (첫 호출만) |
| 단일 분류 | ~50ms |
| 배치 (10개 텍스트) | ~400ms |

### 메모리 사용량

| 상태 | 메모리 |
|-------|--------|
| 로딩 전 | ~100MB |
| 로딩 후 | ~1.3GB |
| 추론 중 | ~1.5GB 피크 |

### 정확도 (100개 샘플 테스트)

| 카테고리 | 정밀도 | 재현율 | F1 |
|----------|-----------|--------|-----|
| 군사 충돌 | 0.94 | 0.91 | 0.92 |
| 외교 관계 | 0.89 | 0.87 | 0.88 |
| 스포츠 | 0.96 | 0.98 | 0.97 |
| 엔터테인먼트 | 0.92 | 0.90 | 0.91 |
| **전체 (높은 신뢰도)** | **0.93** | **0.91** | **0.92** |

---

## Event Verifier와의 통합

### event_verifier.py에서

```python
def classify_with_zero_shot(text: str) -> tuple[bool | None, float, str]:
    """
    에러 핸들링을 포함한 Zero-shot 분류 래퍼.

    Returns:
        (is_international, confidence, label)
        - is_international: 분류기를 사용할 수 없으면 None
    """
    try:
        from app.agent.zero_shot_classifier import get_zero_shot_classifier
        classifier = get_zero_shot_classifier()
        return classifier.classify(text)
    except ImportError:
        logger.warning("Zero-shot classifier not available")
        return None, 0.0, "UNAVAILABLE"
    except Exception as e:
        logger.warning(f"Zero-shot error: {e}")
        return None, 0.0, f"ERROR: {e}"
```

### verify_event_hybrid()에서

```python
async def verify_event_hybrid(text, llm, use_zero_shot=True):
    # Stage 1: Rules
    passed, reason = is_likely_real_event(text)
    if not passed:
        return False, reason

    # Stage 2: Zero-shot
    if use_zero_shot:
        is_intl, confidence, label = classify_with_zero_shot(text)

        if is_intl is not None and confidence >= 0.8:
            if is_intl:
                return True, f"ZERO_SHOT: {label} ({confidence:.2f})"
            else:
                return False, f"ZERO_SHOT_REJECT: {label} ({confidence:.2f})"

    # Stage 3: LLM (불확실한 케이스)
    if llm:
        return await verify_event_with_llm(text, llm)

    return True, "PASSED_RULES_ONLY"
```

---

## 설정

### 환경 변수

```bash
# Zero-shot 비활성화 (테스트 또는 저메모리 환경용)
EVENT_VERIFICATION_USE_ZERO_SHOT=false

# 커스텀 모델 (권장하지 않음)
ZERO_SHOT_MODEL_NAME=facebook/bart-large-mnli
```

### config.py

```python
class AgentSettings(BaseSettings):
    event_verification_use_zero_shot: bool = True
```

---

## 에러 처리

### 우아한 성능 저하

Zero-shot이 실패하면 LLM으로 건너뜁니다:

```python
try:
    classifier = get_zero_shot_classifier()
    is_intl, confidence, label = classifier.classify(text)
except ImportError:
    # transformers 미설치
    logger.warning("Zero-shot unavailable, skipping to LLM")
except Exception as e:
    # 모델 로딩 또는 추론 에러
    logger.error(f"Zero-shot error: {e}")
# LLM 검증으로 계속
```

### 일반적인 오류

| 오류 | 원인 | 해결책 |
|-------|-------|----------|
| `ImportError` | transformers 미설치 | `pip install transformers` |
| `MemoryError` | RAM 부족 | 배치 크기 줄이거나 비활성화 |
| `RuntimeError` | CUDA 문제 | CPU용 `device=-1` 설정 |

---

## 제한사항

### 1. 언어 편향

모델은 주로 영어 텍스트로 학습되었습니다. 비영어 텍스트는:
- 낮은 신뢰도 점수
- 잘못된 분류 위험

**완화책**: Stage 1 규칙이 다국어 스포츠 패턴을 처리합니다.

### 2. 모호한 케이스

일부 텍스트는 실제로 모호합니다:
- "World Cup security concerns" (스포츠인가 보안인가?)
- "Game-changing sanctions" (은유인가 게임인가?)

**완화책**: 신뢰도 < 0.8이면 LLM으로 전달.

### 3. 컨텍스트 길이

BART는 1024 토큰 제한이 있습니다. 512자로 자릅니다:
- 긴 기사에서 컨텍스트를 놓칠 수 있음
- 헤드라인 중심 접근법

### 4. 콜드 스타트

첫 분류는 모델 로딩에 ~10초 소요:
- lifespan 이벤트로 미리 로드
- 초기화 중 워밍업 고려

---

## 향후 개선사항

1. **파인튜닝**: LiveMap 특화 데이터로 학습하여 정확도 향상
2. **증류**: 더 빠른 추론을 위한 작은 모델 (DistilBART) 사용
3. **캐싱**: 자주 사용되는 분류 캐시
4. **GPU 지원**: 더 빠른 추론을 위한 CUDA 활성화
5. **배치 처리**: 여러 텍스트 병렬 처리

---

## 참고 자료

- 모델: [facebook/bart-large-mnli](https://huggingface.co/facebook/bart-large-mnli)
- 논문: [BART: Denoising Sequence-to-Sequence Pre-training](https://arxiv.org/abs/1910.13461)
- CAMEO: [Conflict and Mediation Event Observations](https://parusanalytics.com/eventdata/data.dir/cameo.html)
- ACLED: [Armed Conflict Location & Event Data](https://acleddata.com/resources/general-guides/)

---

*관련 문서:*
- [Event Verification System](./EVENT_VERIFICATION.md)
- [ADR-004: Hybrid Verification](../adr/ADR-004-hybrid-verification.md)
