# Confidence Score API

## Overview

The Confidence Score represents the reliability of a news event based on multi-source cross-verification. Scores range from 0.0 to 0.99, with higher scores indicating greater verification confidence.

## Score Components

### 1. Source Count Base Score

| Number of Sources | Base Score |
|-------------------|------------|
| 1 source | 0.50 |
| 2 sources | 0.70 |
| 3+ sources | 0.85 |

### 2. Tier Weights

Each source is assigned a credibility tier with a corresponding weight:

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

A bonus of 0.03 is added for each additional tier type represented (beyond the first).

## Calculation Formula

```
final_score = (base_score × 0.5) + (tier_average × 0.5) + diversity_bonus
```

Where:
- `base_score`: Based on number of unique sources
- `tier_average`: Average of tier weights for all sources
- `diversity_bonus`: (number_of_tier_types - 1) × 0.03

Maximum score is capped at 0.99.

## API Endpoints

### GET /api/v1/confidence/calculate

Calculate confidence score for a set of sources.

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

Get confidence score breakdown for a specific article.

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

Sources with established editorial standards or official government authority.

| Source | Tier | Weight | Description |
|--------|------|--------|-------------|
| USGS | tier1_govt | 0.99 | US Geological Survey |
| NOAA | tier1_govt | 0.99 | National Oceanic and Atmospheric Administration |
| EMSC | tier1_govt | 0.99 | European-Mediterranean Seismological Centre |
| GDELT | tier1_news | 0.90 | Global news aggregator (includes Reuters, AP, BBC) |

### Tier-2: Secondary Sources

Aggregated news services and research data providers.

| Source | Tier | Weight | Description |
|--------|------|--------|-------------|
| ACLED | tier2_data | 0.85 | Armed Conflict Location & Event Data |
| Currents | tier2_news | 0.75 | News API aggregator |
| World News | tier2_news | 0.75 | Global news API |

### Tier-3: Signal Sources

Social media and trend indicators requiring verification.

| Source | Tier | Weight | Description |
|--------|------|--------|-------------|
| Reddit | tier3_social | 0.40 | Social news aggregator |
| Bluesky | tier3_social | 0.40 | Decentralized social network |
| Telegram | tier3_msg | 0.35 | Messaging platform |
| Google Trends | tier3_trend | 0.30 | Search interest indicator |

## Publication Thresholds

| Score Range | Status | Recommendation |
|-------------|--------|----------------|
| 0.00 - 0.49 | Low | Do not publish, needs more verification |
| 0.50 - 0.69 | Medium | Review required before publication |
| 0.70 - 0.84 | High | Publishable with source citation |
| 0.85 - 0.99 | Very High | Immediate publication recommended |

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

| Code | Description |
|------|-------------|
| 400 | Invalid source format |
| 400 | Unknown tier type |
| 404 | Article not found |
| 422 | Empty sources array |

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| /confidence/calculate | 100 requests/minute |
| /articles/{id}/confidence | 1000 requests/minute |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-01-22 | Initial API specification |
