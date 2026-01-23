# 국제 정세 집중 전략

## 1. 왜 집중하는가?

### 1.1 리소스 효율성

현재 시스템의 처리량은 제한적입니다:

| 항목 | 현재 값 |
|------|--------|
| 15분당 Investigation | 최대 5개 |
| 하루 최대 기사 | ~480개 |
| 수집되는 이벤트 | ~168개/스캔 |

**문제**: 1000개 이벤트 중 진짜 중요한 건 10-20개

### 1.2 품질 > 양

| 전략 | 결과 |
|------|------|
| 모든 카테고리 처리 | 얕은 커버리지, 품질 분산 |
| **국제 정세 집중** | 깊은 커버리지, 전문성 구축 |

### 1.3 차별화 전략

| 카테고리 | 경쟁 상황 |
|----------|----------|
| 자연재해 | USGS/NOAA가 공식 채널로 운영 |
| 경제 뉴스 | Bloomberg, Reuters 등 전문 서비스 존재 |
| **국제 정세** | 속보성 + 검증 = 차별화 가능 |

---

## 2. 포함 카테고리

### 2.1 카테고리 정의

| 카테고리 | 설명 | 키워드 | 예시 |
|----------|------|--------|------|
| **war** | 전쟁, 무력 충돌, 침공 | war, invasion, airstrike, missile, bombing, troops, offensive | 러시아-우크라이나 전쟁 |
| **conflict** | 지역 분쟁, 교전, 충돌 | conflict, clash, fighting, battle, skirmish, ceasefire | 가자 분쟁, 수단 내전 |
| **politics** | 정상회담, 외교, 제재, 선거 | summit, sanctions, election, president, prime minister, parliament | 미중 정상회담, 대북 제재 |
| **security** | 테러, 핵, 사이버 공격 | nuclear, cyberattack, espionage, intelligence | 이란 핵 협상, 북한 미사일 |
| **military** | 군사 작전, 무기, 훈련 | military, army, navy, air force, defense, weapons, deployment | NATO 확장, 합동 훈련 |
| **terrorism** | 테러 공격, 테러 조직 | terrorist, terrorism, extremist, hostage, attack | ISIS 공격, 알카에다 |
| **diplomacy** | 외교 협상, 조약, 대사관 | diplomat, embassy, treaty, negotiation, ambassador | 평화 협정, 대사 추방 |

### 2.2 키워드 매핑

```python
INTERNATIONAL_AFFAIRS_KEYWORDS = {
    "war": [
        "war", "warfare", "invasion", "invade",
        "airstrike", "air strike", "missile", "bombing",
        "troops", "offensive", "military operation"
    ],
    "conflict": [
        "conflict", "clash", "clashes", "fighting",
        "battle", "skirmish", "ceasefire", "cease-fire",
        "hostilities", "armed conflict"
    ],
    "politics": [
        "summit", "sanctions", "election", "elections",
        "president", "prime minister", "parliament",
        "government", "regime", "administration",
        "foreign minister", "state department"
    ],
    "security": [
        "nuclear", "cyberattack", "cyber attack",
        "espionage", "intelligence", "spy", "spying",
        "security threat", "national security"
    ],
    "military": [
        "military", "army", "navy", "air force",
        "defense", "defence", "weapons", "deployment",
        "troops", "soldiers", "forces", "base", "bases"
    ],
    "terrorism": [
        "terrorist", "terrorism", "terror attack",
        "extremist", "hostage", "kidnapping",
        "ISIS", "Al-Qaeda", "Taliban", "militant"
    ],
    "diplomacy": [
        "diplomat", "diplomatic", "embassy",
        "treaty", "negotiation", "negotiations",
        "ambassador", "envoy", "bilateral",
        "multilateral", "UN", "United Nations"
    ],
}
```

---

## 3. 제외 카테고리

### 3.1 제외 목록

| 카테고리 | 제외 사유 |
|----------|----------|
| **natural_disaster** | USGS/NOAA가 공식 채널로 운영, 우리보다 빠르고 정확 |
| **economy** | 별도 전문성 필요 (금융 데이터, 시장 분석) |
| **society** | 범위가 넓어 품질 관리 어려움 |

### 3.2 제외 방법

```python
# config.py
usgs_enabled: bool = False  # 지진 비활성화
noaa_enabled: bool = False  # 날씨 비활성화

# 또는 카테고리 필터로 제외
focus_international_affairs: bool = True
international_affairs_categories: list[str] = [
    "war", "conflict", "politics", "security",
    "military", "terrorism", "diplomacy"
]
```

### 3.3 향후 확장 계획

| Phase | 카테고리 | 조건 |
|-------|----------|------|
| A (현재) | 국제 정세 7개 | M1/M2 맥북 |
| B | + natural_disaster | GPU 서버 확보 시 |
| C | + economy, society | Kubernetes 분산 처리 시 |

---

## 4. 구현 상세

### 4.1 config.py 설정

```python
class AgentSettings(BaseSettings):
    # 자연재해 소스 비활성화
    usgs_enabled: bool = False
    noaa_enabled: bool = False

    # Investigation 처리량 증가
    max_investigations: int = 5  # 3 → 5

    # 국제 정세 카테고리 정의
    international_affairs_categories: list[str] = [
        "war", "conflict", "politics", "security",
        "military", "terrorism", "diplomacy"
    ]

    # 국제 정세 집중 모드
    focus_international_affairs: bool = True
```

### 4.2 scanner.py 필터 로직

```python
def _infer_category_from_event(self, event: TriggerEvent) -> str:
    """이벤트에서 카테고리 추론 (국제 정세 세분화)"""
    text = f"{event.title} {event.content}".lower()

    # 국제 정세 키워드 매핑
    for category, keywords in INTERNATIONAL_AFFAIRS_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category

    # 소스 기반 분류
    if event.source == TriggerSource.USGS:
        return "natural_disaster"
    if event.source == TriggerSource.NOAA:
        return "natural_disaster"

    return "other"


async def _classify_and_group(self, events: list[TriggerEvent]) -> list[dict]:
    """이벤트 분류 및 그룹화"""

    # ... 기존 로직 ...

    # 국제 정세 필터 적용
    if agent_settings.focus_international_affairs:
        allowed = agent_settings.international_affairs_categories
        filtered_events = [
            item for item in limited_events
            if item.get("_category") in allowed
        ]
        logger.info(
            f"International affairs filter: "
            f"{len(filtered_events)}/{len(limited_events)} events"
        )
        limited_events = filtered_events

    return limited_events
```

### 4.3 카테고리 분류 개선

#### 기존 카테고리
```
natural_disaster, war, terrorism, protest, military, violence, other
```

#### 개선된 카테고리 (국제 정세 세분화)
```
war           - 전쟁, 무력 충돌, 침공
conflict      - 지역 분쟁, 충돌, 교전
politics      - 정상회담, 외교, 제재, 선거
security      - 테러, 핵, 사이버 공격
military      - 군사 작전, 무기, 훈련
terrorism     - 테러 공격, 테러 조직
diplomacy     - 외교 협상, 조약, 대사관
```

---

## 5. 예상 결과

### 5.1 Before vs After

| 지표 | Before | After |
|------|--------|-------|
| 수집 이벤트 | 168개 | ~80개 (국제 정세만) |
| 필터 통과 | 21개 | ~15개 |
| 기사 생성 | 3개 (대부분 재해) | 5개 (모두 국제 정세) |
| 하루 기사 | ~288개 | ~480개 |
| 기사 품질 | 분산됨 | 국제 정세 집중 |

### 5.2 로그 출력

```
10:06:47 | INFO | International affairs filter: 12/95 events
10:06:47 | INFO | Filtered categories: war(3), conflict(2), politics(4), security(2), diplomacy(1)
10:06:47 | INFO | Excluded: natural_disaster(46), economy(15), society(12), other(10)
```

---

## 6. 확장 로드맵

### Phase A: 현재 (M1/M2 맥북)

| 항목 | 설정 |
|------|------|
| 소스 | GDELT + Reddit만 활성화 |
| 카테고리 | 국제 정세 7개만 |
| 처리량 | 15분당 5개 기사 |
| 비용 | $100-200/월 |

### Phase B: GPU 서버 (RTX 3080+)

| 항목 | 설정 |
|------|------|
| 소스 | 모든 Tier-1/2 활성화 |
| 카테고리 | + natural_disaster |
| 처리량 | 15분당 10개 기사 |
| 비용 | $450-600/월 |

**성능 향상**:
- 임베딩 10배 빠름 (30초 → 3초)
- LLM 동시 호출 5 → 10

### Phase C: 분산 처리 (Kubernetes)

| 항목 | 설정 |
|------|------|
| 소스 | 모든 소스 활성화 |
| 카테고리 | 전체 카테고리 |
| 처리량 | 15분당 50+ 기사 |
| 비용 | $800-1000/월 |

**아키텍처**:
- 여러 워커가 병렬 Investigation
- Kafka 큐로 이벤트 백로그 관리
- Redis로 Investigation 상태 관리

---

## 7. 주요 모니터링 지표

### 7.1 카테고리별 분포

```
매 스캔마다 로그:
[CATEGORY DISTRIBUTION]
- war: 15 events (18%)
- conflict: 12 events (15%)
- politics: 25 events (31%)
- security: 8 events (10%)
- military: 10 events (12%)
- terrorism: 5 events (6%)
- diplomacy: 5 events (6%)
- excluded: 83 events (natural_disaster, economy, etc.)
```

### 7.2 Investigation 성공률

```
[INVESTIGATION STATS]
- Attempted: 5
- Success (article generated): 4 (80%)
- Skipped (duplicate): 1 (20%)
- Failed: 0 (0%)
```

### 7.3 품질 지표

| 지표 | 목표 | 측정 방법 |
|------|------|----------|
| 국제 정세 비율 | > 90% | 생성된 기사 중 국제 정세 카테고리 비율 |
| 중복률 | < 30% | 스킵된 Investigation 비율 |
| Two-Source 충족 | > 60% | 2개 이상 소스 확인된 기사 비율 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|------|----------|
| 2025-01-23 | 초기 문서 작성 |

---

*이 문서는 국제 정세 집중 전략의 설계 및 구현을 설명합니다.*
