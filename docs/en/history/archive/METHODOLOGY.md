# LiveMap International Affairs News Agent Methodology

> "Faster than anyone, verified, unbiased international affairs news"

---

## 1. Mission

LiveMap provides international affairs news that **enables ordinary people to understand what's happening in the world**.

### Core Values
- **Speed**: Social media monitoring detects events 15-60 minutes faster than traditional media
- **Accuracy**: Multi-source cross-verification filters rumors and fake news
- **Objectivity**: Algorithm-based processing eliminates editorial bias
- **Focus**: Specialized in international affairs (war, diplomacy, conflict, security)

### Current Strategy: Focus on International Affairs

For quality and resource efficiency, we focus on the following categories:

| Category | Description | Examples |
|----------|-------------|----------|
| **war** | War, armed conflict, invasion | Russia-Ukraine, Gaza conflict |
| **conflict** | Regional disputes, engagements | Border clashes, civil wars |
| **politics** | Summits, diplomacy, sanctions | US-China summit, North Korea sanctions |
| **security** | Terrorism, nuclear, cyber attacks | Iran nuclear talks, North Korea missiles |
| **military** | Military operations, weapons, exercises | NATO expansion, military drills |
| **terrorism** | Terror attacks, terror organizations | ISIS, Al-Qaeda related |
| **diplomacy** | Diplomatic negotiations, treaties | Peace agreements, embassy issues |

**Excluded categories** (for now):
- `natural_disaster`: USGS/NOAA are sufficient official channels
- `economy`: Requires separate expertise
- `society`: Scope too broad for quality management

---

## 2. Journalism Principles Compliance

### 2.1 Two-Source Rule

**Definition**: Must be confirmed by 2 or more independent sources before publishing

| Source Type | Single Source Publishing? | Rationale |
|-------------|---------------------------|-----------|
| Government API (USGS, NOAA) | Yes | Official authoritative data |
| Tier-1 News (GDELT: Reuters, AP, BBC) | Yes (confidence >= 0.70) | Established editorial standards |
| Tier-2 News (Currents, World News API) | No | Cross-verification required |
| Social Media (Reddit, Telegram) | No | Always needs news verification |

### 2.2 IFCN (International Fact-Checking Network) 5 Principles

| Principle | Our Implementation |
|-----------|-------------------|
| **1. Non-partisanship/Fairness** | Equal weighting by source tier, no political bias |
| **2. Source Transparency** | All articles cite sources |
| **3. Funding Transparency** | No advertising/sponsorship influence |
| **4. Methodology Transparency** | This document + open source code |
| **5. Corrections Policy** | Immediate correction and notification on error discovery |

---

## 3. Source Reliability Matrix

### 3.1 Tier Classification Criteria

Sources are classified into 3 tiers based on editorial standards, verification processes, and historical accuracy.

#### Tier-1: Primary Sources (Reliability: 0.90-0.99)

| Source | Type | Reliability | Rationale |
|--------|------|-------------|-----------|
| **USGS** | Government | 0.99 | Official US Geological Survey data |
| **NOAA** | Government | 0.99 | Official US National Weather Service data |
| **GDELT** (Reuters, AP, BBC) | News Aggregation | 0.90 | Global news monitoring, includes Tier-1 wire services |

#### Tier-2: Secondary Sources (Reliability: 0.75-0.85)

| Source | Type | Reliability | Rationale |
|--------|------|-------------|-----------|
| **ACLED** | Research | 0.85 | Academic research-based conflict data |
| **Currents API** | News Aggregation | 0.75 | Multi-outlet aggregation, deduplication needed |
| **World News API** | News Aggregation | 0.75 | Global news coverage |

#### Tier-3: Signal Sources (Reliability: 0.30-0.40)

| Source | Type | Reliability | Rationale |
|--------|------|-------------|-----------|
| **Reddit** | Social | 0.40 | Leading signals, community verification, confirmation needed |
| **Telegram** | Messaging | 0.35 | Important in conflict zones, high noise |

### 3.2 Reliability Rationale

Each source's reliability is determined based on:
- **Editorial Standards**: Presence of in-house fact-checking process
- **Historical Accuracy**: Past reporting accuracy
- **Source Type**: Official institutions vs aggregation services vs individual posts
- **Verifiability**: Ease of confirming claim origins

---

## 4. Pipeline Architecture

### 4.1 7-Stage Scanner Pipeline

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           SCANNER PIPELINE                                  │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│   [Stage 1]        [Stage 2]        [Stage 3]        [Stage 3.5]          │
│   Trigger    →    Clustering   →   Classification →  Event         →      │
│   Collection      & Dedup          & Grouping        Verification         │
│                                                      (Gate 0)             │
│                                                                            │
│   [Stage 4]        [Stage 5]        [Stage 6]        [Stage 7]            │
│   Confidence  →   Content     →    Final        →   Output                │
│   Scoring         Gates            Filtering        to Agent              │
│                   (Gate 1-2)                                              │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Event Verification (Gate 0) - Hybrid Approach

From content collected via keyword matching, only **actual events** pass through.

#### Stage 1: Rule-Based Filter (70% removed)

| Pattern | Example | Action |
|---------|---------|--------|
| Entertainment | "new war movie releases" | Remove |
| Gaming | "Call of Duty: Modern Warfare" | Remove |
| Historical/Past | "in 1945", "decades ago" | Remove |
| Speculation/Hypothesis | "might happen", "could potentially" | Remove |
| Sports | "World Cup", "Olympics" | Remove |

#### Stage 2: LLM Verification (only 30% verified)

LLM makes final judgment on content that passes rule filter:
- **YES**: Actually occurred event -> Pass
- **NO**: Movie/game/historical/speculation -> Remove

**Cost efficiency**:
- Rule filter: $0 (instant processing)
- LLM verification: Only on rule-passed content -> 70% cost savings

### 4.3 Investigation Agent

PLANNER -> EXECUTOR structure for dynamic source investigation:

```
1. PLANNER: Context analysis -> Generate search queries
2. EXECUTOR: Multi-source investigation
   - GDELT DOC API (detailed articles)
   - Tavily Search (web search)
   - Government sites (White House, Foreign Ministry, etc.)
3. VERIFIER: Evaluate evidence per claim
4. WRITER: Generate bilingual articles (Korean/English)
```

### 4.4 Article Generation (Bilingual)

All articles are generated simultaneously in Korean and English:

| Field | Description |
|-------|-------------|
| `title_ko` / `title_en` | Title |
| `content_ko` / `content_en` | Body |
| `summary_ko` / `summary_en` | Summary |
| `sources` | Source list |
| `confidence_score` | Confidence score |

---

## 5. Quality Gates

### 5.1 Gate 0: Event Verification (New)

| Stage | Method | Cost |
|-------|--------|------|
| Stage 1 | Rule-based pattern matching | $0 |
| Stage 2 | LLM event judgment | $0.001/item |

### 5.2 Gate 1: Check-worthiness

Filter content without news value:
- Entertainment news
- Speculation/opinion
- Promotional content

### 5.3 Gate 2: Specificity

Require specific, verifiable details:
- Recent dates (within 7 days)
- Specific locations
- Quantifiable data

### 5.4 Gate 3: Evidence Sufficiency

After claim verification:
- Minimum 2 supporting claims
- Evidence ratio above 60%
- Source diversity required

---

## 6. Transparency Policy

### 6.1 AI Generation Disclosure

All articles state:
```
This article was automatically generated by AI and has undergone
multi-source cross-verification.
```

### 6.2 Error Correction Process

1. Immediately correct article upon error discovery
2. Display correction history at bottom of article
3. Retract article and notify on serious errors

### 6.3 Source Citation Rules

- List all source URLs used in every article
- Display confidence score and calculation basis
- Show Two-Source Rule compliance status

---

## 7. Limitations and Caveats

### 7.1 False Positive Possibility

- Target: < 5%
- Mitigation: Multiple gates, cross-verification

### 7.2 LLM Hallucination Risk

- Mitigated through claim verification
- Only facts are published, speculation excluded

### 7.3 Speed vs Accuracy Tradeoff

| Choice | Advantage | Disadvantage |
|--------|-----------|--------------|
| Speed priority | Fast reporting | Risk of errors |
| Accuracy priority | Reliability | Delayed reporting |

**Our choice**: Accuracy priority (Two-Source Rule compliance)

### 7.4 GDELT Dependency

- Detection capability degrades when GDELT is down
- Mitigation: Utilize secondary sources like Reddit

---

## 8. Throughput Analysis

### Current Performance (M1/M2 MacBook)

| Stage | Processing Time |
|-------|-----------------|
| Collection (Trigger Scan) | 8-10 seconds |
| Embedding Generation (50 items) | 1-3 seconds |
| Similarity Matching | 0.1 seconds |
| Event Verification (Gate 0) | 2-5 seconds |
| **Scanner Total** | ~15 seconds |

### Investigation Throughput

| Item | Current Setting |
|------|-----------------|
| Concurrent LLM Calls | 5 |
| Time per Article | 60-120 seconds |
| Articles per 15 minutes | Max 5 |
| Max Articles per Day | ~480 |

---

## 9. Cost Structure

### Source Costs

| Source | Monthly Cost |
|--------|--------------|
| GDELT | $0 |
| Reddit | $0 |
| USGS/NOAA | $0 |
| Currents API | $0 (1,000/day) |
| World News API | $0 (500/day) |
| **Source Total** | **$0/month** |

### Operating Costs

| Item | Monthly Cost |
|------|--------------|
| LLM (gpt-4o-mini) | $50-100 |
| Server (Cloud Run) | $50-100 |
| **Operating Total** | **$100-200/month** |

---

## Change History

| Date | Version | Changes |
|------|---------|---------|
| 2025-01-22 | 1.0.0 | Initial methodology document |
| 2025-01-23 | 2.0.0 | International affairs focus strategy, Gate 0 event verification added |

---

*This document is continuously updated as part of LiveMap's transparency commitment.*
