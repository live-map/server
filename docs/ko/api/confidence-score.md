# Confidence Score API

## Overview

Confidence Score는 다중 소스 교차 검증을 기반으로 한 뉴스 이벤트의 신뢰도를 나타냅니다. 점수는 0.0에서 0.99까지이며, 높은 점수일수록 검증 신뢰도가 높음을 의미합니다.

## Score Components

### 1. Source Count Base Score

| 소스 개수 | Base Score |
|-----------|------------|
| 1개 소스 | 0.50 |
| 2개 소스 | 0.70 |
| 3개 이상 소스 | 0.85 |

### 2. Tier Weights

각 소스는 해당 가중치를 가진 신뢰도 등급에 할당됩니다:

```json
{
  "tier1_govt": 0.99,
  "tier1_news": 0.90,
  "tier2_data": 0.85,
  "tier2_news": 0.75,
  "tier3_social": 0.40,
  "tier3_msg": 0.35,
  "tier3_trend": 0.30
}
```

### 3. Diversity Bonus

첫 번째 이후 추가되는 각 등급 유형에 대해 0.03의 보너스가 추가됩니다.

## Calculation Formula

```
final_score = (base_score × 0.5) + (tier_average × 0.5) + diversity_bonus
```

설명:
- `base_score`: 고유 소스 개수 기반
- `tier_average`: 모든 소스의 등급 가중치 평균
- `diversity_bonus`: (등급_유형_개수 - 1) × 0.03

최대 점수는 0.99로 제한됩니다.

## API Endpoints

### GET /api/v1/confidence/calculate

소스 집합에 대한 confidence score를 계산합니다.

**Request Body:**

```json
{
  "sources": [
    {
      "name": "GDELT",
      "tier": "tier1_news"
    },
    {
      "name": "Currents",
      "tier": "tier2_news"
    },
    {
      "name": "Reddit",
      "tier": "tier3_social"
    }
  ]
}
```

**Response:**

```json
{
  "confidence_score": 0.83,
  "components": {
    "source_count": 3,
    "base_score": 0.85,
    "tier_average": 0.68,
    "tier_types": ["tier1", "tier2", "tier3"],
    "diversity_bonus": 0.06
  },
  "publishable": true,
  "recommendation": "Publish with full source citation"
}
```

### GET /api/v1/articles/{id}/confidence

특정 기사의 confidence score 세부 내역을 조회합니다.

**Response:**

```json
{
  "article_id": 123,
  "confidence_score": 0.82,
  "sources": [
    {
      "name": "GDELT",
      "tier": "tier1_news",
      "weight": 0.90,
      "url": "https://example.com/article"
    },
    {
      "name": "USGS",
      "tier": "tier1_govt",
      "weight": 0.99,
      "url": "https://earthquake.usgs.gov/..."
    }
  ],
  "verification": {
    "claims_total": 5,
    "claims_supported": 4,
    "claims_refuted": 0,
    "claims_nei": 1,
    "evidence_ratio": 0.80
  }
}
```

## Source Tier Definitions

### Tier-1: Primary Sources

확립된 편집 기준 또는 공식 정부 권한을 가진 소스입니다.

| Source | Tier | Weight | 설명 |
|--------|------|--------|------|
| USGS | tier1_govt | 0.99 | 미국 지질조사국 |
| NOAA | tier1_govt | 0.99 | 미국 해양대기청 |
| EMSC | tier1_govt | 0.99 | 유럽-지중해 지진학센터 |
| GDELT | tier1_news | 0.90 | 글로벌 뉴스 통합 서비스 (Reuters, AP, BBC 포함) |

### Tier-2: Secondary Sources

통합 뉴스 서비스 및 연구 데이터 제공자입니다.

| Source | Tier | Weight | 설명 |
|--------|------|--------|------|
| ACLED | tier2_data | 0.85 | 무력 충돌 위치 및 이벤트 데이터 |
| Currents | tier2_news | 0.75 | 뉴스 API 통합 서비스 |
| World News | tier2_news | 0.75 | 글로벌 뉴스 API |

### Tier-3: Signal Sources

검증이 필요한 소셜 미디어 및 트렌드 지표입니다.

| Source | Tier | Weight | 설명 |
|--------|------|--------|------|
| Reddit | tier3_social | 0.40 | 소셜 뉴스 통합 서비스 |
| Bluesky | tier3_social | 0.40 | 탈중앙화 소셜 네트워크 |
| Telegram | tier3_msg | 0.35 | 메시징 플랫폼 |
| Google Trends | tier3_trend | 0.30 | 검색 관심도 지표 |

## Publication Thresholds

| 점수 범위 | 상태 | 권장 사항 |
|-----------|------|-----------|
| 0.00 - 0.49 | Low | 게시하지 않음, 추가 검증 필요 |
| 0.50 - 0.69 | Medium | 게시 전 검토 필요 |
| 0.70 - 0.84 | High | 소스 인용과 함께 게시 가능 |
| 0.85 - 0.99 | Very High | 즉시 게시 권장 |

## Example Calculations

### Example 1: Single Tier-1 Source

```python
sources = [{"name": "GDELT", "tier": "tier1_news"}]

base_score = 0.50  # 1 source
tier_average = 0.90  # tier1_news weight
diversity_bonus = 0  # only 1 tier type

final = (0.50 × 0.5) + (0.90 × 0.5) + 0 = 0.70
```

### Example 2: Multi-Source with Diversity

```python
sources = [
    {"name": "GDELT", "tier": "tier1_news"},
    {"name": "Currents", "tier": "tier2_news"},
    {"name": "Reddit", "tier": "tier3_social"}
]

base_score = 0.85  # 3 sources
tier_average = (0.90 + 0.75 + 0.40) / 3 = 0.68
diversity_bonus = (3 - 1) × 0.03 = 0.06  # 3 tier types

final = (0.85 × 0.5) + (0.68 × 0.5) + 0.06 = 0.83
```

### Example 3: Government + News Source

```python
sources = [
    {"name": "USGS", "tier": "tier1_govt"},
    {"name": "GDELT", "tier": "tier1_news"}
]

base_score = 0.70  # 2 sources
tier_average = (0.99 + 0.90) / 2 = 0.945
diversity_bonus = 0  # both tier1

final = (0.70 × 0.5) + (0.945 × 0.5) + 0 = 0.82
```

## Error Codes

| 코드 | 설명 |
|------|------|
| 400 | 잘못된 소스 형식 |
| 400 | 알 수 없는 등급 유형 |
| 404 | 기사를 찾을 수 없음 |
| 422 | 빈 소스 배열 |

## Rate Limits

| Endpoint | 제한 |
|----------|------|
| /confidence/calculate | 분당 100회 요청 |
| /articles/{id}/confidence | 분당 1000회 요청 |

## Changelog

| 버전 | 날짜 | 변경 사항 |
|------|------|-----------|
| 1.0.0 | 2025-01-22 | 초기 API 명세 |
