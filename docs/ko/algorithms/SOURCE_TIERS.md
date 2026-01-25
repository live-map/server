# 소스 티어 알고리즘

## 개요

소스 티어 시스템은 뉴스 도메인을 4개의 신뢰도 수준으로 분류하여 검증 요구 사항과 게시 자격을 결정합니다. 이를 통해 신뢰할 수 있는 소스에서는 더 빠른 게시가 가능하면서도 덜 확립된 소스에 대해서는 품질을 유지할 수 있습니다.

---

## 도메인 티어 분류

### Tier-1: 통신사 (0.95 신뢰도)

엄격한 편집 기준을 가진 1차 뉴스 소스.

| 도메인 | 유형 |
|--------|------|
| reuters.com | 통신사 |
| apnews.com | 통신사 |
| afp.com | 통신사 |
| un.org | 국제 기구 |
| nato.int | 국제 기구 |
| who.int | 국제 기구 |
| state.gov | 정부 |
| gov.uk | 정부 |
| europa.eu | 정부 |

**특성:**
- 단일 소스 게시 허용
- 검증 지연 없음
- 최소 필요 소스: 1
- 속보 패스트패스 자격

### Tier-2: 주요 뉴스 매체 (0.85 신뢰도)

전문 저널리즘 기준을 갖춘 확립된 뉴스 기관.

| 도메인 | 지역 |
|--------|------|
| nytimes.com | 미국 |
| washingtonpost.com | 미국 |
| cnn.com | 미국 |
| bbc.com | 영국 |
| theguardian.com | 영국 |
| dw.com | 독일 |
| aljazeera.com | 중동 |

**특성:**
- 단일 소스 게시 허용
- 60분 검증 지연
- 최소 필요 소스: 1
- 속보 패스트패스 자격

### Tier-3: 지역/전문 (0.70 신뢰도)

지역 신문 및 전문 출판물.

**특성:**
- Two-Source Rule 필요
- 검증 지연 없음
- 최소 필요 소스: 2
- 표준 게이트 처리

### Tier-4: 기타 (0.50 신뢰도)

블로그, 집계 사이트, 미분류 소스.

**특성:**
- 3개 이상의 소스 필요
- 더 높은 검증 부담
- 최소 필요 소스: 3
- 전체 게이트 처리
- 알 수 없는 도메인의 기본 티어

---

## 게시 규칙

### 결정 매트릭스

| 티어 | 최소 소스 | 단일 소스 OK | 검증 지연 | 속보 패스트패스 |
|------|-----------|-------------|-----------|----------------|
| Tier-1 | 1 | 예 | 0분 | 예 |
| Tier-2 | 1 | 예 | 60분 | 예 |
| Tier-3 | 2 | 아니오 | 0분 | 아니오 |
| Tier-4 | 3 | 아니오 | 0분 | 아니오 |

### 게시 조치

```python
def evaluate_source_mix(sources: list[dict]) -> dict:
    tiers = [get_domain_tier(s["url"]) for s in sources]

    if DomainTier.TIER_1 in tiers:
        return {
            "can_publish": True,
            "recommended_action": "PUBLISH_IMMEDIATE",
            "verification_delay_minutes": 0,
        }
    elif DomainTier.TIER_2 in tiers:
        return {
            "can_publish": True,
            "recommended_action": "PUBLISH_WITH_VERIFICATION",
            "verification_delay_minutes": 60,
        }
    elif len(unique_domains) >= 2:
        return {
            "can_publish": True,
            "recommended_action": "PUBLISH_STANDARD",
            "verification_delay_minutes": 0,
        }
    else:
        return {
            "can_publish": False,
            "recommended_action": "NEED_MORE_SOURCES",
        }
```

---

## Two-Source Rule 통합

저널리즘의 Two-Source Rule은 다음 조건에서 충족됩니다:

1. **단일 Tier-1 도메인 소스** (즉시 게시)
2. **단일 Tier-2 도메인 소스** (60분 검증 후)
3. **2개 이상의 다른 도메인 소스** (표준 규칙)

---

## 속보 통합

Tier-1 및 Tier-2 소스는 속보 패스트패스 자격이 있습니다:

```python
def is_fast_path_eligible(source_url: str) -> bool:
    tier = get_domain_tier(source_url)
    return tier in [DomainTier.TIER_1, DomainTier.TIER_2]
```

패스트패스 자격 소스에서 속보가 감지되면:
- **높은 신뢰도 (≥0.8)**: Gate 0, Gate 2, Gate 3 스킵
- **표준 신뢰도 (0.6-0.79)**: Gate 2, Gate 3 스킵

---

## 파일 위치

```
app/agent/source_tiers.py
```

---

## 관련 문서

- [ADR-011: 도메인 티어](../adr/ADR-011-domain-tiers.md)
- [ADR-003: 티어 시스템](../adr/ADR-003-tier-system.md) (트리거 티어)
- [신뢰도 점수](CONFIDENCE_SCORING.md)
- [ADR-007: 속보](../adr/ADR-007-breaking-news.md)
