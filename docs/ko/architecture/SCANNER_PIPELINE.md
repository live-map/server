# Scanner Pipeline 상세 문서

> **주의**: 이 문서는 Phase 5 (2026-01-24) 기준입니다.
> Phase 6 (2026-01-27) 변경 사항은 아래 "Phase 6 업데이트" 섹션을 참조하세요.

---

## Phase 6 업데이트 (2026-01-27)

### 주요 변경 사항

| 항목 | Phase 5 | Phase 6 |
|------|---------|---------|
| Recency 필터 | **활성화** (6시간) | **비활성화** (트리거에서 처리) |
| Title Dedup 위치 | Step 6.5 (LLM 후) | **Step 3.34 (LLM 전)** |
| Gate 0-2 | 패턴 기반 (600+ 정규식) | **LLM 분류기** (1개 프롬프트) |
| 소스 | 모든 소스 | **59개 도메인 화이트리스트** |

### 새로운 파이프라인 흐름

```
[도메인 화이트리스트] 59개 Tier-1/2 도메인만
     ↓
[Trigger 레벨 Recency] validate_trigger_recency()
     ↓
[Hash Dedup] URL+Title 해시
     ↓
[Scanner 진입]
     ↓
[Recency 필터] DISABLED ← 변경
     ↓
[Content Date / News Classification]
     ↓
[Cross-Source Matching + Confidence]
     ↓
[Importance Filter]
     ↓
[Title Dedup] ← Step 3.34 (LLM 전으로 이동)
     ↓
[LLM 분류기] ← Step 3.35 (Gate 0-2 대체)
  - temporal_category: breaking|developing|retrospective|predictive|timeless
  - is_news, category, is_significant
     ↓
[Temporal Filter] ← Phase 6.1 신규
  - RETROSPECTIVE 자동 거부 (회고/분석 기사)
  - PREDICTIVE 자동 거부 (미래 예측 기사)
     ↓
[Breaking News + Category Limiting]
     ↓
[발행]
```

### Phase 6.1: 시간적 분류 카테고리

| 카테고리 | 시간 범위 | 발행 | 언어적 마커 |
|---------|----------|-----|-----------|
| **BREAKING** | 24시간 이내 | ✅ | "just", "breaking", "happening now" |
| **DEVELOPING** | 1-7일 | ✅ | "latest update", "Day N of" |
| **RETROSPECTIVE** | 과거 분석 | ❌ | "years later", "looking back", "analysis" |
| **PREDICTIVE** | 미래 예측 | ❌ | "could", "may", "expected to" |
| **TIMELESS** | 시간 무관 | ⚠️ | 백과사전적 콘텐츠 |

### 관련 문서
- [Phase 6 히스토리](../history/PHASE_6_LLM_CLASSIFIER.md)
- [ADR-012: LLM 분류기](../adr/ADR-012-llm-classifier.md)

---

## 개요 (Phase 5 기준)

Scanner는 다중 소스에서 뉴스 이벤트를 수집하고, 신뢰도 기반으로 필터링하여 기사화할 이벤트를 선별하는 파이프라인입니다.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              SCANNER PIPELINE                                     │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   [Stage 1]        [Stage 2]        [Stage 3]        [Stage 3.5]                │
│   Trigger    →    Clustering   →   Classification →  Event         →            │
│   Collection      & Dedup          & Grouping        Verification               │
│                                                      (Gate 0)                   │
│                                                                                  │
│   [Stage 4]        [Stage 5]        [Stage 6]        [Stage 7]                  │
│   Confidence  →   Content     →    Final        →   Output                      │
│   Scoring         Gates            Filtering        to Agent                    │
│                   (Gate 1-2)                                                    │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Stage 1: Trigger Collection (이벤트 수집)

### 1.1 개요

각 소스(Trigger)에서 병렬로 이벤트를 수집합니다.

**파일**: `app/agent/triggers/manager.py`

### 1.2 소스별 Tier 분류

| Tier | 소스 | 신뢰도 | 설명 |
|------|------|--------|------|
| **Tier-1 Govt** | USGS | 0.99 | 미국 지질조사국 (지진) |
| **Tier-1 Govt** | NOAA | 0.99 | 미국 기상청 (기상경보) |
| **Tier-1 News** | GDELT | 0.90 | 글로벌 이벤트 데이터베이스 |
| **Tier-1 News** | GDELT Anomaly | 0.90 | GDELT 이상 탐지 |
| **Tier-2 Data** | ACLED | 0.85 | 분쟁 데이터 |
| **Tier-2 News** | Currents | 0.75 | 뉴스 API |
| **Tier-2 News** | WorldNews | 0.75 | 뉴스 API |
| **Tier-3 Social** | Reddit | 0.40 | 소셜 미디어 |
| **Tier-3 Social** | Bluesky | 0.40 | 소셜 미디어 |
| **Tier-3 Trend** | Google Trends | 0.30 | 검색 트렌드 |

### 1.3 수집 예시

```python
# TriggerManager.scan_all() 호출
events = await self.trigger_manager.scan_all()
```

**입력**: 없음 (설정 기반)

**출력 예시**:
```python
[
    TriggerEvent(
        source=TriggerSource.USGS,
        title="M5.2 Earthquake - 120 km SSE of Sand Point, Alaska",
        content="Magnitude 5.2 earthquake at depth 10km...",
        url="https://earthquake.usgs.gov/...",
        detected_at=datetime(2026, 1, 23, 10, 0, 0),
        keywords_matched=["earthquake"],
        metadata={"magnitude": 5.2, "depth": 10}
    ),
    TriggerEvent(
        source=TriggerSource.GDELT,
        title="Trump Administration Arrests Three Protesters",
        content="Federal agents arrested three people...",
        url="https://...",
        detected_at=datetime(2026, 1, 23, 10, 5, 0),
        keywords_matched=["protest", "arrested"],
        metadata={"tone": -3.5}
    ),
    # ... 더 많은 이벤트
]
```

**로그 출력**:
```
10:06:36 | INFO | USGS scan: 3 earthquakes found (M5.0+)
10:06:37 | INFO | NOAA scan: 58 severe alerts found
10:06:39 | INFO | Reddit scan: 14 new posts found
10:06:47 | INFO | GDELT Anomaly scan: 50 GKG, 0 Goldstein, 50 total new
10:06:47 | INFO | Total events: 125, unique: 109
```

### 1.4 각 트리거 동작

#### USGS (지진)
```python
# app/agent/triggers/usgs.py
async def scan(self) -> list[TriggerEvent]:
    # USGS API 호출: 최근 1시간, M5.0 이상
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    params = {
        "format": "geojson",
        "minmagnitude": 5.0,
        "starttime": (now - 1hour).isoformat()
    }
    # 응답 파싱 → TriggerEvent 리스트 반환
```

#### NOAA (기상경보)
```python
# app/agent/triggers/noaa.py
async def scan(self) -> list[TriggerEvent]:
    # NOAA Alerts API 호출
    url = "https://api.weather.gov/alerts/active"
    params = {"severity": "Extreme,Severe"}
    # Warning, Watch, Advisory 필터링
```

#### GDELT (뉴스)
```python
# app/agent/triggers/gdelt.py
async def scan(self) -> list[TriggerEvent]:
    # GDELT DOC API 호출
    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": "(airstrike OR missile OR protest OR earthquake...)",
        "mode": "artlist",
        "maxrecords": 100,
        "timespan": "1h"
    }
```

#### Reddit (소셜)
```python
# app/agent/triggers/reddit.py
async def scan(self) -> list[TriggerEvent]:
    # Reddit JSON API (인증 불필요)
    subreddits = ["worldnews", "news", "UkraineWarVideoReport", "CombatFootage"]
    for sub in subreddits:
        url = f"https://www.reddit.com/r/{sub}/new.json"
        # 최소 score 필터링 (기본 10)
```

---

## Stage 2: Semantic Clustering (의미적 클러스터링)

### 2.1 개요

동일/유사한 이벤트를 그룹화하여 중복을 제거합니다.

**파일**: `app/agent/triggers/clustering.py`

### 2.2 동작 방식

```
입력: 109개 이벤트
         ↓
    [Embedding 생성]
    BAAI/bge-m3 모델로 각 이벤트 텍스트를 벡터화
         ↓
    [HDBSCAN 클러스터링]
    유사한 이벤트를 그룹으로 묶음
         ↓
    [대표 이벤트 선택]
    각 클러스터에서 가장 대표적인 이벤트 선택
         ↓
출력: 39개 클러스터 (중복 제거됨)
```

### 2.3 예시

**입력** (유사한 3개 기사):
```python
[
    TriggerEvent(title="M6.2 earthquake strikes Russia's Kamchatka", source=GDELT),
    TriggerEvent(title="Strong 6.2 magnitude quake hits Kamchatka Peninsula", source=GDELT),
    TriggerEvent(title="Earthquake of magnitude 6.2 recorded near Vilyuchinsk", source=GDELT_ANOMALY),
]
```

**처리 과정**:
```python
# 1. 임베딩 생성
embeddings = encoder.encode([
    "M6.2 earthquake strikes Russia's Kamchatka",
    "Strong 6.2 magnitude quake hits Kamchatka Peninsula",
    "Earthquake of magnitude 6.2 recorded near Vilyuchinsk"
])
# Shape: (3, 1024)

# 2. 코사인 유사도 계산
similarity_matrix = [
    [1.00, 0.89, 0.85],  # 기사1 vs 기사1,2,3
    [0.89, 1.00, 0.87],  # 기사2 vs 기사1,2,3
    [0.85, 0.87, 1.00],  # 기사3 vs 기사1,2,3
]

# 3. 클러스터링 (threshold=0.7)
# 모두 0.7 이상이므로 하나의 클러스터로 그룹화

# 4. 대표 이벤트 선택 (가장 긴 내용 또는 첫 번째)
```

**출력** (1개 클러스터):
```python
Cluster(
    id="eb719719d08a",
    representative=TriggerEvent(title="M6.2 earthquake strikes Russia's Kamchatka"),
    members=[event1, event2, event3],
    size=3
)
```

**로그 출력**:
```
10:06:47 | INFO | New cluster detected: eb719719d08a (3 docs)
10:06:47 | INFO | New cluster detected: 3017d6e3fd2e (2 docs)
10:06:47 | INFO | New cluster detected: 07ebcab08784 (42 docs)  # 대형 클러스터
...
```

---

## Stage 3: Source Classification (소스 분류)

### 3.1 개요

이벤트를 Tier-1 정부 소스와 기타 소스로 분류합니다.

**파일**: `app/agent/scanner.py` (`_classify_and_group` 메서드)

### 3.2 분류 로직

```python
# SOURCE_TIER_MAP 정의 (app/agent/triggers/base.py)
SOURCE_TIER_MAP = {
    TriggerSource.USGS: SourceTier.TIER1_GOVT,
    TriggerSource.NOAA: SourceTier.TIER1_GOVT,
    TriggerSource.GDELT: SourceTier.TIER1_NEWS,
    TriggerSource.GDELT_ANOMALY: SourceTier.TIER1_NEWS,
    TriggerSource.REDDIT: SourceTier.TIER3_SOCIAL,
    # ...
}
```

### 3.3 예시

**입력**: 109개 이벤트

**처리**:
```python
tier1_govt_events = []  # USGS, NOAA
other_events = []       # GDELT, Reddit, etc.

for event in events:
    source_tier = SOURCE_TIER_MAP.get(event.source)
    if source_tier == SourceTier.TIER1_GOVT:
        tier1_govt_events.append(event)
    else:
        other_events.append(event)
```

**출력**:
```
tier1_govt_events: 46개 (USGS 3개 + NOAA 43개)
other_events: 63개 (GDELT 50개 + Reddit 13개)
```

**로그 출력**:
```
10:06:47 | INFO | Source classification: 46 Tier-1 govt, 63 other sources
```

### 3.4 Tier-1 정부 소스의 특별 처리

Tier-1 정부 소스(USGS, NOAA)는 **Two-Source Rule 면제**:
- 공식 기관 발표이므로 추가 검증 없이 즉시 발행 가능
- Confidence Score가 자동으로 0.74 부여

---

## Stage 3.5: 이벤트 검증 (Gate 0) - 3단계 하이브리드

### 3.5.1 개요

키워드 매칭으로 수집된 콘텐츠 중 **실제 이벤트**만 통과시킵니다.

**파일**: `app/agent/event_verifier.py`

**참고 문서**: [Zero-shot Classification](./ZERO_SHOT_CLASSIFIER.md), [Event Verification](./EVENT_VERIFICATION.md)

### 3.5.2 문제 정의

키워드 매칭은 False Positive를 생성합니다:

| 수집된 콘텐츠 | 키워드 | 실제 여부 |
|--------------|--------|----------|
| "Iran attacks US bases" | attack | O 실제 |
| "New war movie releases" | war | X 영화 |
| "Call of Duty review" | war | X 게임 |
| "In 1945, the war ended" | war | X 역사 |

### 3.5.3 3단계 하이브리드 솔루션

```
수집된 이벤트 (168개)
    ↓
[Stage 1: 규칙 기반 필터] - $0, ~1ms
- NOT_EVENT_PATTERNS 매칭
- 영화/게임/역사/스포츠 제거
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

### 3.5.4 Stage 1: 규칙 기반 필터

```python
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
    # 스포츠 (영어)
    r"\b(football|soccer|basketball|tennis|olympics|world cup)\b",
    # 스포츠 (다국어)
    r"(손흥민|토트넘|맨유|리버풀|챔피언스리그|월드컵)",  # 한국어
    r"(كرة القدم|الدوري|ريال مدريد|برشلونة)",  # 아랍어
    r"(足球|皇马|巴萨|世界杯|欧冠)",  # 중국어
]

def is_likely_real_event(text: str) -> tuple[bool, str | None]:
    text_lower = text.lower()
    for pattern in NOT_EVENT_PATTERNS:
        if re.search(pattern, text_lower):
            return False, f"NOT_EVENT: matched pattern '{pattern}'"
    return True, None
```

### 3.5.5 Stage 2: Zero-shot 분류

```python
from app.agent.zero_shot_classifier import get_zero_shot_classifier

# CAMEO/ACLED 기반 레이블
INTERNATIONAL_AFFAIRS_LABELS = [
    "military conflict", "diplomatic relations", "terrorism",
    "humanitarian crisis", "international sanctions", "protest and civil unrest"
]

REJECT_LABELS = [
    "sports", "entertainment", "local news", "opinion and analysis"
]

def classify_with_zero_shot(text: str) -> tuple[bool | None, float, str]:
    classifier = get_zero_shot_classifier()
    is_intl, confidence, label = classifier.classify(text)
    return is_intl, confidence, label
```

**결정 기준**:
| 분류 결과 | 확신도 | 결정 |
|-----------|--------|------|
| International | ≥ 0.8 | **PASS** 즉시 |
| Rejection | ≥ 0.8 | **REJECT** 즉시 |
| Any | < 0.8 | Stage 3 (LLM)으로 |

### 3.5.6 Stage 3: LLM 검증

```python
EVENT_VERIFY_PROMPT = """다음 텍스트가 실제로 발생한 국제 정세 이벤트를 보도하는지 판단하세요.

텍스트: {text}

판단 기준:
- PASS: 실제 발생한 사건 (전쟁, 외교, 테러, 시위, 정상회담 등)
- REJECT: 영화/게임/역사/추측/의견/스포츠/연예

답변 형식:
VERDICT: PASS 또는 REJECT
REASON: 한 줄 설명"""
```

### 3.5.7 비용 분석

| 단계 | 처리량 | 비용 | 필터율 |
|------|--------|------|--------|
| Stage 1 (규칙) | 168 → 50개 | $0 | ~70% |
| Stage 2 (Zero-shot) | 50 → 40개 | $0 | ~20% |
| Stage 3 (LLM) | 15개 (불확실 케이스) | $0.015/스캔 | Edge cases |
| **하루 총 비용** | | **$1.44** | |

**비용 절감**:
- LLM만 사용 시: $16.13/일
- 2단계 하이브리드 (Rules + LLM): $4.80/일 (70% 절감)
- 3단계 하이브리드 (Rules + Zero-shot + LLM): $1.44/일 (**91% 절감**)

### 3.5.8 설정

```python
# config.py
event_verification_enabled: bool = True
event_verification_use_zero_shot: bool = True  # Zero-shot 분류 활성화
event_verification_use_llm: bool = True         # LLM 검증 활성화 (Stage 3)
```

**로그 출력**:
```
10:06:47 | INFO | [GATE0-REJECT] NOT_EVENT: matched pattern 'movie': New war movie...
10:06:47 | INFO | [GATE0-REJECT] ZERO_SHOT: sports (0.92): World Cup final...
10:06:48 | INFO | [GATE0-PASS] ZERO_SHOT: military conflict (0.89): Iran attacks...
10:06:48 | INFO | [GATE0-REJECT] LLM_REJECT: 가상 시나리오 (영화 줄거리)
10:06:48 | INFO | Event verification: 35/168 passed (79% filtered)
```

---

## Stage 4: Cross-Source Matching & Confidence Scoring

### 4.1 개요

서로 다른 소스에서 동일한 이벤트를 찾아 그룹화하고, 신뢰도를 계산합니다.

**파일**:
- `app/agent/cross_source_matcher.py`
- `app/agent/confidence_scorer.py`

### 4.2 Cross-Source Matching

```
입력: 63개 "other_events" (GDELT, Reddit)
         ↓
    [Embedding 기반 유사도 계산]
    서로 다른 소스 간 유사 이벤트 매칭
         ↓
    [MatchedEvent 생성]
    - 단일 소스: cluster_size=1
    - 다중 소스: cluster_size=2+
         ↓
출력: 50개 클러스터
```

**예시 - 다중 소스 매칭**:
```python
# GDELT 기사
event1 = TriggerEvent(
    source=GDELT,
    title="Minnesota church protest leads to arrests"
)

# Reddit 포스트
event2 = TriggerEvent(
    source=REDDIT,
    title="3 arrested at Minnesota church during ICE protest"
)

# 유사도: 0.82 (threshold 0.70 초과)
# → 하나의 MatchedEvent로 그룹화

matched = MatchedEvent(
    primary_event=event1,
    matching_events=[event2],
    similarity_scores=[0.82],
    source_count=2  # GDELT + Reddit
)
```

### 4.3 Confidence Scoring

**신뢰도 계산 공식**:
```python
final_score = (base_score * 0.5) + (tier_average * 0.5) + diversity_bonus
```

**Base Score (소스 수 기반)**:
| 소스 수 | Base Score |
|---------|------------|
| 1개 | 0.50 |
| 2개 | 0.70 |
| 3개+ | 0.85 |

**Tier Average (소스 신뢰도 평균)**:
```python
# 예: GDELT 1개
tier_average = 0.90

# 예: GDELT + Reddit
tier_average = (0.90 + 0.40) / 2 = 0.65
```

**Diversity Bonus**:
- 서로 다른 Tier에서 왔으면 +0.03

### 4.4 계산 예시

#### 예시 1: USGS 단일 소스
```python
sources = [{"name": "usgs", "tier": "tier1_govt"}]

base_score = 0.50       # 1개 소스
tier_average = 0.99     # tier1_govt
diversity_bonus = 0.00  # 단일 tier

final = (0.50 * 0.5) + (0.99 * 0.5) + 0.00
      = 0.25 + 0.495 + 0.00
      = 0.745 → 0.74 (반올림)

recommendation = "immediate_publish"  # tier1_govt 특별 처리
```

#### 예시 2: GDELT 단일 소스
```python
sources = [{"name": "gdelt", "tier": "tier1_news"}]

base_score = 0.50       # 1개 소스
tier_average = 0.90     # tier1_news
diversity_bonus = 0.00

final = (0.50 * 0.5) + (0.90 * 0.5) + 0.00
      = 0.25 + 0.45 + 0.00
      = 0.70

recommendation = "publishable"
```

#### 예시 3: GDELT + Reddit (다중 소스)
```python
sources = [
    {"name": "gdelt", "tier": "tier1_news"},
    {"name": "reddit", "tier": "tier3_social"}
]

base_score = 0.70       # 2개 소스
tier_average = (0.90 + 0.40) / 2 = 0.65
diversity_bonus = 0.03  # tier1 + tier3

final = (0.70 * 0.5) + (0.65 * 0.5) + 0.03
      = 0.35 + 0.325 + 0.03
      = 0.705 → 0.71

two_source_satisfied = True  # 2개 이상 소스
recommendation = "publishable"
```

#### 예시 4: Reddit 단일 소스 (필터링됨)
```python
sources = [{"name": "reddit", "tier": "tier3_social"}]

base_score = 0.50       # 1개 소스
tier_average = 0.40     # tier3_social
diversity_bonus = 0.00

final = (0.50 * 0.5) + (0.40 * 0.5) + 0.00
      = 0.25 + 0.20 + 0.00
      = 0.45

recommendation = "do_not_publish"  # 0.70 미달
```

**로그 출력**:
```
10:06:48 | INFO | [CONFIDENCE] usgs: 0.74 (immediate_publish)
10:06:48 | INFO | [CONFIDENCE] Cluster (1 sources): 0.70 (publishable) | Two-Source: False | EEUU prohibirá...
10:06:48 | INFO | [CONFIDENCE] Cluster (1 sources): 0.45 (do_not_publish) | Two-Source: False | Reddit post...
10:06:48 | INFO | Confidence filter: 95 events passed (threshold=0.7)
```

---

## Stage 5: Content Gates (콘텐츠 게이트)

### 5.1 개요

기사화 가치가 있는 콘텐츠인지 추가 필터링합니다.

**파일**:
- `app/agent/checkworthiness.py` (Gate 1)
- `app/agent/specificity.py` (Gate 2)

### 5.2 Gate 1: Check-worthiness (검증 가치)

**목적**: 엔터테인먼트, 추측성 기사, 인간 관심사 기사 필터링

```python
def check_worthiness(text, entertainment_threshold, speculation_threshold, human_interest_threshold):
    # 엔터테인먼트 패턴
    entertainment_patterns = [
        r'\b(celebrity|movie|album|concert|grammy|oscar)\b',
        r'\b(kardashian|swift|bieber)\b',
        ...
    ]

    # 추측 패턴
    speculation_patterns = [
        r'\b(might|could|may|possibly|rumor)\b',
        r'\b(sources say|reportedly|allegedly)\b',
        ...
    ]

    # 인간 관심사 패턴
    human_interest_patterns = [
        r'\b(heartwarming|inspiring|adorable)\b',
        r'\b(viral video|cute|amazing story)\b',
        ...
    ]
```

**예시**:
```python
# 통과하는 기사
text = "Federal agents arrested three protesters at a Minnesota church"
result = check_worthiness(text)
# → is_checkworthy=True

# 필터링되는 기사
text = "Taylor Swift's new album might be released next month, sources say"
result = check_worthiness(text)
# → is_checkworthy=False, reason=ENTERTAINMENT
```

### 5.3 Gate 2: Specificity (구체성)

**목적**: 구체적인 정보(누가, 언제, 어디서, 무엇을)가 있는지 확인

```python
def check_specificity(text, min_score=0.3):
    score = 0.0

    # 숫자 존재 (+0.2)
    if re.search(r'\d+', text):
        score += 0.2

    # 고유명사 존재 (+0.2)
    if re.search(r'[A-Z][a-z]+', text):
        score += 0.2

    # 날짜 존재 (+0.2)
    if re.search(r'(January|February|...|2026|yesterday)', text):
        score += 0.2

    # 장소 존재 (+0.2)
    if re.search(r'(in|at|near) [A-Z][a-z]+', text):
        score += 0.2

    # 인용문 존재 (+0.2)
    if re.search(r'[""].*[""]', text):
        score += 0.2

    return SpecificityResult(score=score, is_specific=(score >= min_score))
```

**예시**:
```python
# 높은 구체성
text = "A magnitude 5.2 earthquake struck 120 km southeast of Sand Point, Alaska on January 23, 2026"
# 숫자(5.2, 120): +0.2
# 고유명사(Sand Point, Alaska): +0.2
# 날짜(January 23, 2026): +0.2
# 장소(southeast of Sand Point): +0.2
# → score=0.8, is_specific=True

# 낮은 구체성
text = "Something happened somewhere recently"
# → score=0.0, is_specific=False
```

### 5.4 Gate 적용 규칙

| 소스 | Gate 1 | Gate 2 |
|------|--------|--------|
| Tier-1 Govt (USGS, NOAA) | **면제** | **면제** |
| Tier-1 News (GDELT) - 영어 | 적용 | 적용 |
| Tier-1 News (GDELT) - 비영어 | 적용 | **면제** |
| Tier-3 Social (Reddit) | 적용 | 적용 |

**비영어 면제 이유**: Specificity 패턴이 영어 전용이므로 비영어 기사에 적용하면 오탐

**로그 출력**:
```
10:06:48 | INFO | Content gates: 95/95 passed
# 또는 필터링 시
10:06:48 | INFO | [GATE1-REJECT] ENTERTAINMENT: Taylor Swift's new album...
10:06:48 | INFO | [GATE2-REJECT] Low specificity (0.10): Something happened...
```

---

## Stage 6: Final Filtering (최종 필터링)

### 6.1 통과 조건

이벤트가 최종 발행 대상이 되려면:

```python
# 조건 1: 신뢰도 임계값 충족
confidence.score >= 0.70

# 또는

# 조건 2: Two-Source Rule 충족
confidence.two_source_satisfied == True
```

### 6.2 결과 포맷팅

```python
results.append({
    "description": event.title,
    "category": category,  # natural_disaster, war, protest, etc.
    "sources": ["USGS"],
    "source_count": 1,
    "trigger_source": "usgs",
    "keywords": ["earthquake"],
    "url": "https://...",
    "confidence_score": 0.74,
    "confidence_level": "high",
    "two_source_satisfied": False,
    "recommendation": "immediate_publish",
    "is_tier1_govt": True,
})
```

### 6.3 카테고리 추론

```python
def _infer_category_from_event(self, event):
    text = f"{event.title} {event.content}".lower()

    # 소스 기반
    if event.source == USGS:
        return "natural_disaster"
    if event.source == NOAA:
        return "natural_disaster"

    # 키워드 기반
    if any(kw in text for kw in ["earthquake", "tsunami", "flood"]):
        return "natural_disaster"
    if any(kw in text for kw in ["war", "invasion", "airstrike"]):
        return "war"
    if any(kw in text for kw in ["terrorist", "bombing"]):
        return "terrorism"
    if any(kw in text for kw in ["protest", "demonstration"]):
        return "protest"

    return "other"
```

---

## Stage 7: Output to Agent (에이전트로 전달)

### 7.1 출력 형식

```python
[
    {
        "description": "M5.2 Earthquake - 120 km SSE of Sand Point, Alaska",
        "category": "natural_disaster",
        "sources": ["USGS"],
        "source_count": 1,
        "confidence_score": 0.74,
        "is_tier1_govt": True,
    },
    {
        "description": "3 people involved in Minnesota church protest arrested",
        "category": "protest",
        "sources": ["kunr.org"],
        "source_count": 1,
        "confidence_score": 0.70,
        "is_tier1_govt": False,
    },
    # ... 총 95개 이벤트
]
```

### 7.2 정렬 순서

1. **Tier-1 Govt 먼저** (USGS, NOAA)
2. **신뢰도 높은 순서** (0.74 > 0.70)
3. **다중 소스 먼저** (source_count 높은 순)

### 7.3 Investigation 전달

```python
# lifespan.py
max_investigations = 3
investigation_count = 0

for event in events:
    if investigation_count >= max_investigations:
        break

    # 중복 체크 (DB 조회)
    if is_duplicate(event):
        continue  # 카운트 증가 안함

    # Agent에게 전달
    result = await agent.investigate(
        event=event["description"],
        category=event["category"],
    )

    # 성공 시 카운트 증가
    if result.get("article_en"):
        save_to_db(result)
        investigation_count += 1
```

---

## 전체 흐름 요약

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Stage 1: Trigger Collection                                             │
│ ─────────────────────────────                                           │
│ USGS: 3개, NOAA: 58개, GDELT: 50개, Reddit: 14개                         │
│ → Total: 125개, Unique: 109개                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ Stage 2: Semantic Clustering                                            │
│ ────────────────────────────                                            │
│ 109개 → 39개 클러스터 (중복 제거)                                         │
│ 예: "Russia earthquake" 관련 3개 기사 → 1개 클러스터                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ Stage 3: Source Classification                                          │
│ ─────────────────────────────                                           │
│ Tier-1 Govt: 46개 (USGS 3 + NOAA 43)                                    │
│ Other: 63개 (GDELT 50 + Reddit 13)                                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ Stage 3.5: Event Verification (Gate 0) - 3단계 하이브리드                │
│ ─────────────────────────────────────────────────                       │
│ Stage 1 (규칙): 영화/게임/역사/스포츠 패턴 제거 → 70% 필터                │
│ Stage 2 (Zero-shot): BART-MNLI 분류, 확신도 ≥0.8 결정 → 20% 추가 필터    │
│ Stage 3 (LLM): 불확실 케이스만 최종 판단                                  │
│ → 109개 → 35개 통과 (74개 필터)                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ Stage 4: Confidence Scoring                                             │
│ ──────────────────────────                                              │
│ USGS/NOAA: 0.74 (immediate_publish)                                     │
│ GDELT: 0.70 (publishable)                                               │
│ Reddit: 0.45 (do_not_publish) → 필터링                                   │
│ → 96개 통과 (threshold=0.70)                                             │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ Stage 5: Content Gates                                                  │
│ ────────────────────                                                    │
│ Gate 1 (Check-worthiness): 엔터테인먼트/추측 필터                         │
│ Gate 2 (Specificity): 구체성 검사 (영어만)                                │
│ → 95개 통과                                                              │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ Stage 6: Deduplication (DB 조회)                                        │
│ ──────────────────────────────                                          │
│ 이미 기사화된 이벤트 스킵                                                 │
│ 예: M5.2 Alaska 지진 → event_id=24로 이미 존재 → SKIP                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ Stage 7: Output to Agent                                                │
│ ────────────────────────                                                │
│ 최대 3개 이벤트를 ClaimVerificationAgent에 전달                          │
│ Agent가 기사 생성 후 DB 저장                                             │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 설정 옵션 (config.py)

```python
class AgentSettings:
    # Trigger 설정
    gdelt_enabled: bool = True
    gdelt_timespan: str = "1h"
    usgs_enabled: bool = True
    usgs_min_magnitude: float = 5.0
    noaa_enabled: bool = True
    reddit_enabled: bool = True

    # Confidence 설정
    min_confidence_score: float = 0.70
    cross_source_similarity_threshold: float = 0.70

    # Event Verification (Gate 0) 설정
    event_verification_enabled: bool = True
    event_verification_use_zero_shot: bool = True  # Stage 2 Zero-shot
    event_verification_use_llm: bool = True        # Stage 3 LLM

    # Gate 설정
    checkworthiness_enabled: bool = True
    specificity_enabled: bool = True
    min_specificity_score: float = 0.30

    # 로깅
    log_gate_rejections: bool = True
```

---

## 디버깅 가이드

### 이벤트가 수집되지 않을 때
```bash
# 각 트리거의 응답 확인
10:06:37 | ERROR | GDELT scan error: 429 Too Many Requests
# → Rate limit. 잠시 후 재시도
```

### 이벤트가 필터링될 때
```bash
# Confidence 필터
10:06:48 | INFO | [CONFIDENCE] Cluster (1 sources): 0.45 (do_not_publish)
# → Reddit 단독 소스. 다른 소스와 매칭 필요

# Gate 1 필터
10:06:48 | INFO | [GATE1-REJECT] ENTERTAINMENT: Celebrity news...
# → 엔터테인먼트 기사

# Gate 2 필터
10:06:48 | INFO | [GATE2-REJECT] Low specificity (0.10): Vague headline...
# → 구체적인 정보 부족
```

### 기사가 생성되지 않을 때
```bash
[SCANNER] [1] SKIPPING: Duplicate event (matched event_id=24)
[SCANNER] [2] SKIPPING: Duplicate event (matched event_id=22)
[SCANNER] [3] SKIPPING: Duplicate event (matched event_id=23)
# → 모든 상위 이벤트가 중복. 새 이벤트가 조사 슬롯을 얻지 못함
# → lifespan.py 수정 필요 (중복은 슬롯 소비 안 함)
```
