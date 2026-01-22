# LiveMap News Verification Methodology

> "Faster than anyone, verified, unbiased informational news"

## Mission Statement

LiveMap delivers **real-time, verified international news** by combining:
- **Speed**: Social media monitoring detects breaking news 15-60 minutes before traditional outlets
- **Accuracy**: Multi-source cross-verification eliminates rumors and fake news
- **Objectivity**: Automated processing removes human editorial bias

---

## Journalism Standards Compliance

### Two-Source Rule

The **Two-Source Rule** is a fundamental journalism principle requiring independent confirmation from at least two sources before publication.

| Source Type | Single Source Publishable? | Rationale |
|-------------|---------------------------|-----------|
| Government APIs (USGS, NOAA, EMSC) | Yes | Official authoritative data |
| Tier-1 News (Reuters, AP, BBC via GDELT) | Yes (confidence ≥ 0.70) | Established editorial standards |
| Tier-2 News (Currents, World News API) | No | Requires cross-verification |
| Social Media (Reddit, Bluesky, Telegram) | No | Always requires news verification |

### IFCN (International Fact-Checking Network) 5 Principles

We adhere to all five IFCN principles:

| Principle | Our Implementation |
|-----------|-------------------|
| **1. Non-partisanship & Fairness** | All sources weighted equally by tier, no political bias |
| **2. Source Transparency** | Every article lists all contributing sources |
| **3. Funding Transparency** | No advertising or sponsorship influence |
| **4. Methodology Transparency** | This document + open source code |
| **5. Corrections Policy** | Immediate correction with notification on errors |

---

## Source Credibility Matrix

### Tier Classification

Sources are classified into three tiers based on editorial standards, verification processes, and historical accuracy.

#### Tier-1: Primary Sources (Confidence: 0.90-0.99)

| Source | Type | Confidence | Justification |
|--------|------|------------|---------------|
| **USGS** | Government | 0.99 | Official US geological monitoring, peer-reviewed methodology |
| **NOAA** | Government | 0.99 | Official US weather service, scientific standards |
| **EMSC** | Government | 0.99 | European seismological authority |
| **GDELT** (Reuters, AP, BBC) | News Aggregator | 0.90 | Global news monitoring, includes Tier-1 wire services |

#### Tier-2: Secondary Sources (Confidence: 0.75-0.85)

| Source | Type | Confidence | Justification |
|--------|------|------------|---------------|
| **ACLED** | Research | 0.85 | Academic research-based conflict data |
| **Currents API** | News Aggregator | 0.75 | Aggregates multiple outlets, deduplication needed |
| **World News API** | News Aggregator | 0.75 | Global news coverage, requires verification |

#### Tier-3: Signal Sources (Confidence: 0.30-0.40)

| Source | Type | Confidence | Justification |
|--------|------|------------|---------------|
| **Reddit** | Social | 0.40 | Early signals, community verification, needs confirmation |
| **Bluesky** | Social | 0.40 | Real-time signals, decentralized, needs verification |
| **Telegram** | Messaging | 0.35 | Critical for conflict zones, high noise ratio |
| **Google Trends** | Analytics | 0.30 | Interest indicator, not direct news source |

---

## Pipeline Architecture

### Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                      15-minute Scan Cycle                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────── STAGE 1: Parallel Detection ───────────────┐ │
│  │                                                                 │ │
│  │  ┌─────────────────────┐    ┌─────────────────────────────┐   │ │
│  │  │   GDELT Anomaly     │    │     Social + Trends          │   │ │
│  │  │   Detection         │    │                              │   │ │
│  │  │  ┌───────────────┐  │    │  ┌─────────┐  ┌─────────┐   │   │ │
│  │  │  │ timelinevolraw│  │    │  │ Bluesky │  │ Reddit  │   │   │ │
│  │  │  │ (spike detect)│  │    │  │Firehose │  │  API    │   │   │ │
│  │  │  └───────────────┘  │    │  └────┬────┘  └────┬────┘   │   │ │
│  │  │  ┌───────────────┐  │    │       │            │        │   │ │
│  │  │  │ GKG Themes    │  │    │  ┌─────────┐  ┌─────────┐   │   │ │
│  │  │  │ (CRISISLEX)   │  │    │  │ Google  │  │Telegram │   │   │ │
│  │  │  └───────────────┘  │    │  │ Trends  │  │Channels │   │   │ │
│  │  │  ┌───────────────┐  │    │  └────┬────┘  └────┬────┘   │   │ │
│  │  │  │ Goldstein<-5  │  │    │       │            │        │   │ │
│  │  │  │ (conflict)    │  │    │       └────────────┘        │   │ │
│  │  │  └───────────────┘  │    │              │               │   │ │
│  │  └─────────┬───────────┘    │              ▼               │   │ │
│  │            │                │    ┌───────────────────┐    │   │ │
│  │            │                │    │ Social Velocity   │    │   │ │
│  │            │                │    │ Score             │    │   │ │
│  │            │                │    └─────────┬─────────┘    │   │ │
│  │            │                └──────────────┼───────────────┘   │ │
│  │            │                               │                   │ │
│  │            └───────────────┬───────────────┘                   │ │
│  │                            │                                   │ │
│  │                            ▼                                   │ │
│  │                 ┌───────────────────┐                         │ │
│  │                 │ Candidate Events  │                         │ │
│  │                 │ (GDELT anomaly OR │                         │ │
│  │                 │  Social velocity) │                         │ │
│  │                 └─────────┬─────────┘                         │ │
│  └───────────────────────────┼────────────────────────────────────┘ │
│                              │                                      │
│  ┌───────────────────────────┼──── STAGE 2: Cross-Verification ───┐│
│  │                           ▼                                     ││
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           ││
│  │  │  GDELT  │  │Currents │  │ World   │  │ Expert  │           ││
│  │  │   DOC   │  │  API    │  │News API │  │ APIs    │           ││
│  │  │(detail) │  │         │  │         │  │USGS/NOAA│           ││
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘           ││
│  │       │            │            │            │                 ││
│  │       └────────────┴────────────┴────────────┘                 ││
│  │                         │                                       ││
│  │                         ▼                                       ││
│  │              ┌───────────────────┐                             ││
│  │              │ Cross-Source      │                             ││
│  │              │ Matcher           │                             ││
│  │              │ (Embedding sim.)  │                             ││
│  │              └─────────┬─────────┘                             ││
│  │                        │                                        ││
│  │                        ▼                                        ││
│  │              ┌───────────────────┐                             ││
│  │              │ Multi-Source      │                             ││
│  │              │ Confidence Score  │                             ││
│  │              │ (Tier weights)    │                             ││
│  │              └─────────┬─────────┘                             ││
│  └────────────────────────┼────────────────────────────────────────┘│
│                           │                                         │
│                  confidence >= 0.70?                                │
│                           │                                         │
│              Yes ─────────┴───────── No ──▶ (Archive/Wait)          │
│                           │                                         │
│                           ▼                                         │
│                  ┌───────────────────┐                             │
│                  │ Article Generation│                             │
│                  │ (Source citation) │                             │
│                  └───────────────────┘                             │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### GDELT Dual Role

GDELT serves two distinct purposes in our pipeline:

1. **Stage 1: Anomaly Detection API**
   - `timelinevolraw`: Detects volume spikes indicating breaking news
   - `GKG Themes`: Monitors crisis-related themes (CRISISLEX, PROTEST, etc.)
   - `Goldstein Score < -5`: Identifies high-intensity conflict events

2. **Stage 2: DOC API**
   - Retrieves detailed article metadata
   - Provides source URLs for verification
   - Cross-references with other sources

---

## Multi-Source Confidence Scoring

### Algorithm

```python
TIER_WEIGHTS = {
    "tier1_news": 0.90,    # GDELT (Reuters, AP, BBC)
    "tier1_govt": 0.99,    # USGS, NOAA, EMSC
    "tier2_news": 0.75,    # Currents, World News API
    "tier2_data": 0.85,    # ACLED
    "tier3_social": 0.40,  # Reddit, Bluesky
    "tier3_trend": 0.30,   # Google Trends
    "tier3_msg": 0.35,     # Telegram
}

def calculate_confidence(sources: list[dict]) -> float:
    """
    Multi-source confidence scoring with tier weights.

    Args:
        sources: [{"name": "GDELT", "tier": "tier1_news"}, ...]

    Returns:
        Confidence score 0.0 - 0.99
    """
    if not sources:
        return 0.0

    # 1. Base score from source count
    source_count = len(set(s["name"] for s in sources))
    if source_count == 1:
        base = 0.50
    elif source_count == 2:
        base = 0.70
    else:
        base = 0.85

    # 2. Weighted tier average
    tier_scores = [TIER_WEIGHTS.get(s["tier"], 0.50) for s in sources]
    tier_avg = sum(tier_scores) / len(tier_scores)

    # 3. Source type diversity bonus
    source_types = set(s["tier"].split("_")[0] for s in sources)
    diversity_bonus = (len(source_types) - 1) * 0.03

    # 4. Final score = 50% base + 50% tier average + diversity bonus
    final = (base * 0.5) + (tier_avg * 0.5) + diversity_bonus

    return min(final, 0.99)
```

### Confidence Score Examples

| Source Combination | Calculation | Score | Action |
|-------------------|-------------|-------|--------|
| GDELT only | (0.50×0.5)+(0.90×0.5) | **0.70** | Review for publication |
| GDELT + Currents | (0.70×0.5)+(0.825×0.5) | **0.76** | Publish |
| GDELT + Social | (0.70×0.5)+(0.65×0.5)+0.03 | **0.71** | Review for publication |
| GDELT + Currents + Social | (0.85×0.5)+(0.68×0.5)+0.06 | **0.83** | Publish |
| GDELT + USGS (earthquake) | (0.70×0.5)+(0.945×0.5) | **0.82** | Immediate publish |
| 3+ Tier-1 sources | (0.85×0.5)+(0.93×0.5)+0.03 | **0.92** | Immediate publish |

---

## Social Velocity Scoring

### Purpose

Social velocity measures the speed at which a topic spreads across social platforms, identifying potential breaking news before traditional media coverage.

### Calculation

```python
def calculate_social_velocity(topic: str) -> float:
    scores = {
        "reddit": {
            "upvote_velocity": get_reddit_velocity(topic),  # upvotes/min
            "cross_posts": count_cross_posts(topic),
        },
        "bluesky": {
            "post_count": count_bluesky_posts(topic, window="15min"),
            "repost_velocity": count_reposts(topic),
        },
        "google_trends": {
            "breakout": is_breakout(topic),  # 100%+ surge
            "interest": get_interest_score(topic),
        },
        "telegram": {
            "channel_count": count_telegram_channels(topic),
            "message_count": count_messages(topic),
        },
    }

    weights = {
        "reddit": 0.25,
        "bluesky": 0.15,
        "google_trends": 0.30,
        "telegram": 0.30,
    }

    return weighted_sum(scores, weights)
```

### Velocity Thresholds

| Velocity Score | Status | Action |
|---------------|--------|--------|
| < 20 | Normal | Ignore |
| 20-50 | Emerging | Monitor |
| 50-80 | Trending | Start news verification |
| > 80 | Viral | Immediate news verification |

---

## Content Filtering Gates

### Gate 1: Check-Worthiness

Rejects content that is not newsworthy:
- Entertainment news
- Speculation/opinion
- Promotional content
- Human interest stories without broader significance

### Gate 2: Specificity

Requires concrete, verifiable details:
- Recent date (within 7 days)
- Specific location
- Quantifiable data (casualties, amounts, etc.)

**Minimum Score**: 0.4 (40% of criteria met)

### Gate 3: Evidence Sufficiency

After claim verification:
- Minimum supported claims required
- Evidence ratio threshold
- Source diversity requirement

---

## Verification Process

### Claim Extraction

1. Parse article text
2. Extract 3-10 specific factual claims
3. Prioritize verifiable assertions (dates, numbers, locations, quotes)

### Claim Verification (QA Approach)

For each claim:
1. Generate verification question
2. Search multiple sources (Tavily, DuckDuckGo)
3. LLM evaluates evidence
4. Assign verdict: SUPPORTED / REFUTED / NEI (Not Enough Information)
5. Calculate confidence (1-5 scale)

### Evidence Requirements

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| Min Supported Claims | 2 | Two-source rule |
| Evidence Ratio | 0.60 | Majority of claims verified |
| Source Count | 2+ | Cross-verification |

---

## Category-Specific Sources

### Conflict

| Source | Role |
|--------|------|
| GDELT | Primary news detection |
| ACLED | Research-backed conflict data |
| Telegram | Real-time from conflict zones |

**Keywords**: airstrike, missile, invasion, casualties, ceasefire

### Disaster

| Source | Role |
|--------|------|
| USGS | Authoritative earthquake data |
| NOAA | Weather alerts and warnings |
| EMSC | European seismic monitoring |
| GDELT | News coverage |

**Keywords**: earthquake, magnitude, tsunami, wildfire, hurricane

### Politics

| Source | Role |
|--------|------|
| GDELT | Global political news |
| Currents API | Additional coverage |
| Reddit | Public sentiment |

**Keywords**: summit, sanctions, election, legislation, diplomatic

### Economy

| Source | Role |
|--------|------|
| GDELT | Financial news |
| Google Trends | Public interest signals |

**Keywords**: tariffs, recession, inflation, market, trade

---

## Validation Methods

### Historical Backtesting

| Event | Date | Validation |
|-------|------|------------|
| Israel-Hamas Attack | 2023-10-07 | Social lead time, GDELT detection |
| Turkey Earthquake | 2023-02-06 | USGS vs GDELT timing comparison |
| SVB Collapse | 2023-03-10 | Social velocity → news verification flow |
| Trump Indictment | 2023-03-30 | Multi-source confidence progression |

### Real-Time Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| False Positive Rate | < 5% | Rumors/fake news published |
| False Negative Rate | < 10% | Real breaking news missed |
| Latency | < 30 min | Event → publication time |

### Source Accuracy Tracking

| Source | Metric | Target |
|--------|--------|--------|
| GDELT Anomaly | Breaking news detection rate | > 80% |
| Social Velocity | Valid early signal rate | > 60% |
| USGS/NOAA | Official data match rate | > 99% |

---

## Transparency Reporting

### Monthly Report Contents

1. **Publication Statistics**
   - Total articles published
   - By category breakdown
   - Confidence score distribution

2. **Source Contribution**
   - Articles per source
   - Cross-verification rates
   - Source accuracy metrics

3. **Corrections**
   - Number of corrections/retractions
   - Correction reasons
   - Time to correction

4. **Performance Metrics**
   - Detection latency
   - Verification accuracy
   - False positive/negative rates

---

## Cost Structure

| Component | Monthly Cost |
|-----------|-------------|
| GDELT | $0 |
| Currents API | $0 (1,000/day) |
| World News API | $0 (500/day) |
| USGS/NOAA/EMSC | $0 |
| ACLED | $0 |
| Reddit API | $0 (100 QPM) |
| Bluesky Firehose | $0 |
| Google Trends | $0 |
| Telegram | $0 |
| **Total Source Cost** | **$0/month** |

Server and LLM API costs are additional.

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2025-01-22 | 1.0.0 | Initial methodology documentation |

---

*This document is automatically updated and maintained as part of the LiveMap transparency commitment.*
