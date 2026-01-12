# Detection Layers - 감지 레이어 아키텍처

> **목표**: 키워드 매칭의 한계를 보완하는 지능형 감지 시스템

---

## 핵심 개념

### 문제: 키워드 매칭의 한계

```
키워드 매칭 방식:
  "war", "protest", "violence" → 매칭되면 감지

한계:
1. 키워드에 없는 새로운 유형의 사건은?
2. 암호화된 언어, 신조어는?
3. 예상 못한 방식으로 표현된 사건은?
```

### 해결: 다층 감지 시스템

```
┌─────────────────────────────────────────────────────────────────┐
│                    다층 감지 시스템                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 1: Keyword Matching (기존)                               │
│           - "war", "protest" 등 키워드 매칭                     │
│           - 빠르고 예측 가능                                    │
│           - 알려진 위협 감지                                    │
│                                                                 │
│  Layer 2: Anomaly Detection (NEW)                               │
│           - 볼륨/속도 이상 감지                                 │
│           - 키워드 무관하게 "변화" 감지                         │
│           - 예상 못한 사건도 감지                               │
│                                                                 │
│  Layer 3: Semantic Clustering (NEW)                             │
│           - 임베딩 기반 문서 그룹화                             │
│           - 새 클러스터 = 새로운 주제 출현                      │
│           - 키워드 없이도 관련 문서 그룹화                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Layer 2: Anomaly Detection

### 개념

```
평상시: ████████████████████ (baseline)

이상 발생: ████████████████████████████████ (3σ 초과!)
                 ↑
                 "뭔가 일어났다" (키워드 상관없이)
```

### 구현 파일

`app/agents/triggers/anomaly.py`

### 주요 기능

| 기능 | 설명 |
|------|------|
| 볼륨 스파이크 | 평소보다 갑자기 많은 이벤트 |
| 소스별 이상 | 특정 소스에서만 급증 |
| 키워드별 이상 | 특정 키워드 언급 급증 |
| EWMA | 단기/장기 추세 비교 |

### 사용법

```python
from app.agents.triggers import AnomalyDetector, AnomalySignal

detector = AnomalyDetector(
    short_window=10,     # 최근 10개 샘플
    long_window=50,      # 최근 50개 샘플
    z_threshold=2.5,     # 2.5σ 기준
)

# 스캔 결과 기록 및 이상 감지
anomalies: list[AnomalySignal] = detector.record_scan(
    event_count=25,
    source_counts={"gdelt": 15, "twitter": 10},
    keyword_counts={"war": 5, "protest": 8},
)

# 이상 신호 처리
for anomaly in anomalies:
    print(f"{anomaly.signal_type}: {anomaly.description}")
    print(f"  Z-Score: {anomaly.z_score:.2f}")
    print(f"  Baseline: {anomaly.baseline_value:.1f}")
    print(f"  Current: {anomaly.current_value}")
```

### AnomalySignal 구조

```python
@dataclass
class AnomalySignal:
    signal_type: str          # volume_spike, keyword_spike:war, etc.
    severity: float           # 0.0 ~ 1.0
    z_score: float            # 표준편차 기준 얼마나 벗어났는지
    baseline_value: float     # 평소 값
    current_value: float      # 현재 값
    detected_at: datetime
    description: str
    metadata: dict
```

### 알고리즘

- **Z-Score**: `z = (current - mean) / std`
- **임계값**: 기본 2.5σ (99% 신뢰구간)
- **EWMA**: 지수 가중 이동 평균으로 추세 추적

---

## Layer 3: Semantic Clustering

### 개념

```python
# 키워드 방식
if "war" in text:
    trigger()  # 키워드 있어야 감지

# 클러스터링 방식
embedding = embed(text)
cluster = find_cluster(embedding)
if new_cluster_emerged():
    trigger()  # 키워드 없어도 감지
```

### 구현 파일

`app/agents/triggers/clustering.py`

### 주요 기능

| 기능 | 설명 |
|------|------|
| 실시간 클러스터링 | 새 문서 → 기존/새 클러스터 |
| 새 클러스터 감지 | 기존에 없던 주제 출현 |
| 클러스터 성장 감지 | 특정 주제 급성장 |
| 유사 클러스터 검색 | 쿼리와 유사한 클러스터 찾기 |

### 사용법

```python
from app.agents.triggers import SemanticClusterer, ClusteringSignal

clusterer = SemanticClusterer(
    similarity_threshold=0.7,   # 클러스터 소속 임계값
    new_cluster_threshold=0.4,  # 새 클러스터 생성 임계값
    min_cluster_size=2,         # 최소 클러스터 크기
)

# 초기화 (임베딩 모델 로딩)
await clusterer.initialize()

# 문서 처리
documents = [
    {"title": "Russian forces advance...", "url": "..."},
    {"title": "Ukraine military reports...", "url": "..."},
]

signals: list[ClusteringSignal] = await clusterer.process_documents(documents)

# 신호 처리
for signal in signals:
    if signal.signal_type == "new_cluster":
        print(f"새 주제 발견: {signal.cluster.size} 문서")
        for doc in signal.cluster.documents[:3]:
            print(f"  - {doc['title'][:50]}...")
```

### 임베딩 모델

- **모델**: BAAI/bge-m3
- **특징**: 다국어, 고성능, 1024차원
- **메모리**: ~2GB

### 클러스터링 알고리즘

```
새 문서 도착
    │
    ▼
기존 클러스터와 유사도 계산
    │
    ├─ 유사도 ≥ 0.7 → 기존 클러스터에 추가
    │
    ├─ 유사도 < 0.4 → 새 클러스터 생성 (= 새 주제!)
    │
    └─ 0.4 ≤ 유사도 < 0.7 → 가장 가까운 클러스터에 추가
```

---

## TriggerManager 통합

### 초기화

```python
from app.agents.triggers import TriggerManager

manager = TriggerManager(
    openai_api_key="...",
    enable_anomaly_detection=True,   # 이상 감지 활성화
    enable_clustering=True,          # 클러스터링 활성화
    on_anomaly=handle_anomaly,       # 이상 감지 콜백
    on_new_cluster=handle_cluster,   # 새 클러스터 콜백
)

# 초기화 (클러스터링 모델 로딩 포함)
results = await manager.initialize_all()
# {"GDELT": True, "semantic_clusterer": True, "anomaly_detector": True}
```

### 스캔

```python
# scan_all()이 자동으로 감지 레이어 실행
events = await manager.scan_all()

# 콜백이 자동 호출됨:
# - on_anomaly(AnomalySignal) - 이상 감지 시
# - on_new_cluster(ClusteringSignal) - 새 클러스터 감지 시
# - on_event(TriggerEvent, category) - 이벤트 감지 시
```

### 상태 확인

```python
status = manager.get_status()
# {
#     "last_scan": "2026-01-12T10:30:00",
#     "triggers": [...],
#     "detection_layers": {
#         "anomaly_detector": {
#             "volume_samples": 25,
#             "ewma_divergence": 0.15,
#         },
#         "semantic_clusterer": {
#             "initialized": True,
#             "total_clusters": 8,
#             "total_documents": 45,
#         }
#     }
# }
```

---

## 아키텍처 다이어그램

```
┌─────────────────────────────────────────────────────────────────┐
│                         TriggerManager                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐      │
│  │                   Trigger Sources                     │      │
│  │                                                       │      │
│  │  ┌─────────┐   ┌─────────┐   ┌─────────┐            │      │
│  │  │  GDELT  │   │ Twitter │   │Telegram │            │      │
│  │  └────┬────┘   └────┬────┘   └────┬────┘            │      │
│  │       └─────────────┴─────────────┘                  │      │
│  │                      │                               │      │
│  │                      ▼                               │      │
│  │              Deduplicated Events                     │      │
│  └──────────────────────┬───────────────────────────────┘      │
│                         │                                       │
│                         ▼                                       │
│  ┌──────────────────────────────────────────────────────┐      │
│  │                 Detection Layers                      │      │
│  │                                                       │      │
│  │  ┌────────────────────┐  ┌────────────────────────┐  │      │
│  │  │  Anomaly Detector  │  │  Semantic Clusterer    │  │      │
│  │  │                    │  │                        │  │      │
│  │  │  - Volume spike    │  │  - New cluster         │  │      │
│  │  │  - Keyword spike   │  │  - Cluster growth      │  │      │
│  │  │  - EWMA divergence │  │  - Similar search      │  │      │
│  │  └────────────────────┘  └────────────────────────┘  │      │
│  │            │                        │                │      │
│  │            ▼                        ▼                │      │
│  │     AnomalySignal           ClusteringSignal        │      │
│  └──────────────────────────────────────────────────────┘      │
│                         │                                       │
│                         ▼                                       │
│  ┌──────────────────────────────────────────────────────┐      │
│  │                   LLM Classification                  │      │
│  │                   (GPT-4o-mini)                       │      │
│  └──────────────────────────────────────────────────────┘      │
│                         │                                       │
│                         ▼                                       │
│                    Callbacks                                    │
│           on_event / on_anomaly / on_new_cluster               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 환경 변수

감지 레이어는 별도 환경 변수 없이 기본 활성화됨.
비활성화하려면 코드에서:

```python
manager = TriggerManager(
    enable_anomaly_detection=False,
    enable_clustering=False,
)
```

---

## 의존성

```toml
# pyproject.toml
sentence-transformers>=3.1.0  # 임베딩 모델 (BGE-M3)
numpy>=1.24.0                 # 수치 계산
```

---

## 성능 고려사항

| 항목 | 값 | 비고 |
|------|-----|------|
| 임베딩 모델 메모리 | ~2GB | BGE-M3 |
| 임베딩 속도 | ~50ms/문서 | CPU 기준 |
| 클러스터 최대 수 | 100개 | 메모리 관리 |
| 클러스터 TTL | 24시간 | 오래된 클러스터 정리 |

---

## 연구 배경

### Anomaly Detection
- Google Timeseries Insights API 패턴 참고
- GDELT 프로젝트의 breaking news 감지 방식
- 연구 결과: AUC 86.6% ~ 93.7%

### Semantic Clustering
- LLM Enhanced Clustering for News Event Detection (2024)
- 연구 결과: 임베딩 기반이 키워드 기반보다 클러스터링 품질 우수

---

*작성일: 2026-01-12*
