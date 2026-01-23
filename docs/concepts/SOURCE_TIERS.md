# Source Tier System

LiveMap classifies all data sources into tiers based on their credibility, editorial standards, and historical accuracy.

---

## Tier Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SOURCE TIERS                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  TIER-1 GOVERNMENT (0.99)     Official government data              │
│  ├── USGS                     US Geological Survey                  │
│  └── NOAA                     National Oceanic & Atmospheric        │
│                                                                     │
│  TIER-1 NEWS (0.90)           Major news aggregators                │
│  ├── GDELT                    Global news (Reuters, AP, BBC)        │
│  └── GDELT Anomaly            GDELT anomaly detection               │
│                                                                     │
│  TIER-2 DATA (0.85)           Research/academic sources             │
│  └── ACLED                    Armed Conflict Location & Event       │
│                                                                     │
│  TIER-2 NEWS (0.75)           Secondary news aggregators            │
│  ├── Currents API             Multi-source news                     │
│  └── World News API           Global news coverage                  │
│                                                                     │
│  TIER-3 SOCIAL (0.40)         Social media platforms                │
│  ├── Reddit                   Community-driven news                 │
│  └── Bluesky                  Decentralized social                  │
│                                                                     │
│  TIER-3 MESSAGING (0.35)      Messaging platforms                   │
│  └── Telegram                 Conflict zone reports                 │
│                                                                     │
│  TIER-3 TRENDS (0.30)         Trend indicators                      │
│  └── Google Trends            Search interest spikes                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Tier Details

### Tier-1 Government (Credibility: 0.99)

Official government data sources with highest reliability.

| Source | Description | Data Type |
|--------|-------------|-----------|
| **USGS** | US Geological Survey | Earthquakes, geological events |
| **NOAA** | National Weather Service | Weather alerts, severe weather |

**Characteristics**:
- Official authority
- Real-time instrumentation data
- Zero editorial bias
- No verification needed

### Tier-1 News (Credibility: 0.90)

Major news aggregators with established editorial standards.

| Source | Description | Coverage |
|--------|-------------|----------|
| **GDELT** | Global Database of Events | 100+ languages, global |
| **GDELT Anomaly** | Volume/theme anomalies | Breaking events |

**Characteristics**:
- Includes Tier-1 wire services (Reuters, AP, AFP, BBC)
- Established fact-checking processes
- Professional journalism standards
- High verification accuracy

### Tier-2 Data (Credibility: 0.85)

Research and academic data sources.

| Source | Description | Coverage |
|--------|-------------|----------|
| **ACLED** | Armed Conflict Location & Event Data | Global conflict tracking |

**Characteristics**:
- Academic methodology
- Rigorous data collection
- Peer-reviewed processes
- Specialized coverage

### Tier-2 News (Credibility: 0.75)

Secondary news aggregators with broader but less curated coverage.

| Source | Description | Coverage |
|--------|-------------|----------|
| **Currents API** | Multi-source news | General news |
| **World News API** | Global news | International focus |

**Characteristics**:
- Broader source inclusion
- Variable editorial standards
- Good for coverage breadth
- Requires corroboration

### Tier-3 Social (Credibility: 0.40)

Social media platforms - valuable for early signals but noisy.

| Source | Description | Best For |
|--------|-------------|----------|
| **Reddit** | Community news | Early signals, trends |
| **Bluesky** | Decentralized social | Breaking news signals |

**Characteristics**:
- Fastest detection
- High noise ratio
- User-generated content
- Community moderation only

### Tier-3 Messaging (Credibility: 0.35)

Messaging platforms with regional importance.

| Source | Description | Best For |
|--------|-------------|----------|
| **Telegram** | Channels & groups | Conflict zone reports |

**Characteristics**:
- Critical for conflict zones
- Eyewitness reports
- Very high noise
- Verification essential

### Tier-3 Trends (Credibility: 0.30)

Trend indicators showing public interest.

| Source | Description | Best For |
|--------|-------------|----------|
| **Google Trends** | Search interest | Breakout detection |

**Characteristics**:
- Indirect signal only
- Shows public awareness
- Not a source itself
- Useful for prioritization

---

## Credibility Assignment

### Factors Considered

| Factor | Weight | Description |
|--------|--------|-------------|
| Editorial standards | 30% | Fact-checking, editorial review |
| Historical accuracy | 25% | Track record of correct reports |
| Source type | 20% | Official vs aggregator vs user |
| Verification ability | 15% | Can claims be independently verified? |
| Timeliness | 10% | How quickly do they report? |

### Credibility Scores

| Tier | Score Range | Publishing Policy |
|------|-------------|-------------------|
| Tier-1 Govt | 0.99 | Immediate publish |
| Tier-1 News | 0.90 | Publishable (confidence ≥ 0.70) |
| Tier-2 Data | 0.85 | Needs corroboration |
| Tier-2 News | 0.75 | Needs corroboration |
| Tier-3 Social | 0.40 | Signal only |
| Tier-3 Msg | 0.35 | Signal only |
| Tier-3 Trend | 0.30 | Indicator only |

---

## Implementation

### Source-to-Tier Mapping

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

## Examples

### Example 1: Earthquake (USGS)

```
Source: USGS
Tier: TIER1_GOVT
Credibility: 0.99

→ Immediate publish (no corroboration needed)
```

### Example 2: Military Conflict (GDELT + Reddit)

```
Source 1: GDELT (Reuters article)
Tier: TIER1_NEWS
Credibility: 0.90

Source 2: Reddit (r/worldnews)
Tier: TIER3_SOCIAL
Credibility: 0.40

Combined tier average: (0.90 + 0.40) / 2 = 0.65
Diversity bonus: +0.03 (different tiers)

→ Two-source satisfied, publishable
```

### Example 3: Reddit-only Report

```
Source: Reddit (r/CombatFootage)
Tier: TIER3_SOCIAL
Credibility: 0.40

→ Signal only, await corroboration
```

---

## Related Documentation

- [Two-Source Rule](TWO_SOURCE_RULE.md) - Verification requirements
- [Confidence Scoring](CONFIDENCE_SCORING.md) - Score calculation
- [ADR-003: Tier System](../adr/ADR-003-tier-system.md) - Design decision
