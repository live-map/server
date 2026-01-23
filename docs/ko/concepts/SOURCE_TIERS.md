# Source Tier System (소스 티어 시스템)

LiveMap은 신뢰도, 편집 표준, 역사적 정확도를 기반으로 모든 데이터 소스를 티어로 분류합니다.

---

## 티어 개요

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SOURCE TIERS                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  TIER-1 GOVERNMENT (0.99)     공식 정부 데이터                      │
│  ├── USGS                     미국 지질조사국                       │
│  └── NOAA                     미국 해양대기청                       │
│                                                                     │
│  TIER-1 NEWS (0.90)           주요 뉴스 수집기                      │
│  ├── GDELT                    글로벌 뉴스 (Reuters, AP, BBC)        │
│  └── GDELT Anomaly            GDELT 이상 탐지                       │
│                                                                     │
│  TIER-2 DATA (0.85)           연구/학술 소스                        │
│  └── ACLED                    Armed Conflict Location & Event       │
│                                                                     │
│  TIER-2 NEWS (0.75)           2차 뉴스 수집기                       │
│  ├── Currents API             다중 소스 뉴스                        │
│  └── World News API           글로벌 뉴스 커버리지                  │
│                                                                     │
│  TIER-3 SOCIAL (0.40)         소셜 미디어 플랫폼                    │
│  ├── Reddit                   커뮤니티 기반 뉴스                    │
│  └── Bluesky                  탈중앙화 소셜                         │
│                                                                     │
│  TIER-3 MESSAGING (0.35)      메시징 플랫폼                         │
│  └── Telegram                 분쟁 지역 보고                        │
│                                                                     │
│  TIER-3 TRENDS (0.30)         트렌드 지표                           │
│  └── Google Trends            검색 관심 스파이크                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 티어 상세

### Tier-1 정부 (신뢰도: 0.99)

최고 신뢰도를 가진 공식 정부 데이터 소스.

| 소스 | 설명 | 데이터 유형 |
|--------|-------------|-----------|
| **USGS** | 미국 지질조사국 | 지진, 지질 이벤트 |
| **NOAA** | 국립기상청 | 기상 경보, 악천후 |

**특성**:
- 공식 권위
- 실시간 계측 데이터
- 편집 편향 없음
- 검증 불필요

### Tier-1 뉴스 (신뢰도: 0.90)

확립된 편집 표준을 가진 주요 뉴스 수집기.

| 소스 | 설명 | 커버리지 |
|--------|-------------|----------|
| **GDELT** | Global Database of Events | 100개+ 언어, 글로벌 |
| **GDELT Anomaly** | 볼륨/테마 이상 | 속보 이벤트 |

**특성**:
- Tier-1 통신사 포함 (Reuters, AP, AFP, BBC)
- 확립된 팩트체킹 프로세스
- 전문 저널리즘 표준
- 높은 검증 정확도

### Tier-2 데이터 (신뢰도: 0.85)

연구 및 학술 데이터 소스.

| 소스 | 설명 | 커버리지 |
|--------|-------------|----------|
| **ACLED** | Armed Conflict Location & Event Data | 글로벌 분쟁 추적 |

**특성**:
- 학술 방법론
- 엄격한 데이터 수집
- 동료 검토 프로세스
- 전문 커버리지

### Tier-2 뉴스 (신뢰도: 0.75)

더 넓지만 덜 큐레이션된 커버리지를 가진 2차 뉴스 수집기.

| 소스 | 설명 | 커버리지 |
|--------|-------------|----------|
| **Currents API** | 다중 소스 뉴스 | 일반 뉴스 |
| **World News API** | 글로벌 뉴스 | 국제 초점 |

**특성**:
- 더 넓은 소스 포함
- 가변적 편집 표준
- 커버리지 범위에 좋음
- 확인 필요

### Tier-3 소셜 (신뢰도: 0.40)

소셜 미디어 플랫폼 - 조기 신호에 가치 있지만 노이즈가 많음.

| 소스 | 설명 | 최적 용도 |
|--------|-------------|----------|
| **Reddit** | 커뮤니티 뉴스 | 조기 신호, 트렌드 |
| **Bluesky** | 탈중앙화 소셜 | 속보 신호 |

**특성**:
- 가장 빠른 감지
- 높은 노이즈 비율
- 사용자 생성 콘텐츠
- 커뮤니티 모더레이션만

### Tier-3 메시징 (신뢰도: 0.35)

지역적 중요성을 가진 메시징 플랫폼.

| 소스 | 설명 | 최적 용도 |
|--------|-------------|----------|
| **Telegram** | 채널 & 그룹 | 분쟁 지역 보고 |

**특성**:
- 분쟁 지역에 중요
- 목격자 보고
- 매우 높은 노이즈
- 검증 필수

### Tier-3 트렌드 (신뢰도: 0.30)

대중 관심을 보여주는 트렌드 지표.

| 소스 | 설명 | 최적 용도 |
|--------|-------------|----------|
| **Google Trends** | 검색 관심 | 브레이크아웃 감지 |

**특성**:
- 간접 신호만
- 대중 인식 표시
- 자체로는 소스 아님
- 우선순위 지정에 유용

---

## 신뢰도 할당

### 고려 요소

| 요소 | 가중치 | 설명 |
|--------|--------|-------------|
| 편집 표준 | 30% | 팩트체킹, 편집 검토 |
| 역사적 정확도 | 25% | 정확한 보도 이력 |
| 소스 유형 | 20% | 공식 vs 수집기 vs 사용자 |
| 검증 능력 | 15% | 주장을 독립적으로 검증 가능한가? |
| 적시성 | 10% | 얼마나 빨리 보도하는가? |

### 신뢰도 점수

| 티어 | 점수 범위 | 게시 정책 |
|------|-------------|-------------------|
| Tier-1 정부 | 0.99 | 즉시 게시 |
| Tier-1 뉴스 | 0.90 | 게시 가능 (신뢰도 ≥ 0.70) |
| Tier-2 데이터 | 0.85 | 확인 필요 |
| Tier-2 뉴스 | 0.75 | 확인 필요 |
| Tier-3 소셜 | 0.40 | 신호만 |
| Tier-3 메시징 | 0.35 | 신호만 |
| Tier-3 트렌드 | 0.30 | 지표만 |

---

## 구현

### Source-to-Tier 매핑

```python
# app/agent/triggers/base.py
from enum import Enum

class SourceTier(str, Enum):
    TIER1_GOVT = "tier1_govt"
    TIER1_NEWS = "tier1_news"
    TIER2_DATA = "tier2_data"
    TIER2_NEWS = "tier2_news"
    TIER3_SOCIAL = "tier3_social"
    TIER3_MSG = "tier3_msg"
    TIER3_TREND = "tier3_trend"

SOURCE_TIER_MAP = {
    TriggerSource.USGS: SourceTier.TIER1_GOVT,
    TriggerSource.NOAA: SourceTier.TIER1_GOVT,
    TriggerSource.GDELT: SourceTier.TIER1_NEWS,
    TriggerSource.GDELT_ANOMALY: SourceTier.TIER1_NEWS,
    TriggerSource.ACLED: SourceTier.TIER2_DATA,
    TriggerSource.CURRENTS: SourceTier.TIER2_NEWS,
    TriggerSource.WORLDNEWS: SourceTier.TIER2_NEWS,
    TriggerSource.REDDIT: SourceTier.TIER3_SOCIAL,
    TriggerSource.BLUESKY: SourceTier.TIER3_SOCIAL,
    TriggerSource.TELEGRAM: SourceTier.TIER3_MSG,
    TriggerSource.GOOGLE_TRENDS: SourceTier.TIER3_TREND,
}

TIER_CREDIBILITY = {
    SourceTier.TIER1_GOVT: 0.99,
    SourceTier.TIER1_NEWS: 0.90,
    SourceTier.TIER2_DATA: 0.85,
    SourceTier.TIER2_NEWS: 0.75,
    SourceTier.TIER3_SOCIAL: 0.40,
    SourceTier.TIER3_MSG: 0.35,
    SourceTier.TIER3_TREND: 0.30,
}
```

---

## 예시

### 예시 1: 지진 (USGS)

```
소스: USGS
티어: TIER1_GOVT
신뢰도: 0.99

→ 즉시 게시 (확인 불필요)
```

### 예시 2: 군사 충돌 (GDELT + Reddit)

```
소스 1: GDELT (Reuters 기사)
티어: TIER1_NEWS
신뢰도: 0.90

소스 2: Reddit (r/worldnews)
티어: TIER3_SOCIAL
신뢰도: 0.40

결합 티어 평균: (0.90 + 0.40) / 2 = 0.65
다양성 보너스: +0.03 (다른 티어)

→ Two-source 충족, 게시 가능
```

### 예시 3: Reddit만의 보고

```
소스: Reddit (r/CombatFootage)
티어: TIER3_SOCIAL
신뢰도: 0.40

→ 신호만, 확인 대기
```

---

## 관련 문서

- [Two-Source Rule](TWO_SOURCE_RULE.md) - 검증 요구사항
- [Confidence Scoring](CONFIDENCE_SCORING.md) - 점수 계산
- [ADR-003: Tier System](../adr/ADR-003-tier-system.md) - 설계 결정
