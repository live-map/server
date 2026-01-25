# News API Expansion Research

## Overview

Research on additional news APIs to expand source coverage and improve event detection.

---

## Current Sources

| Source | Tier | Coverage | Cost |
|--------|------|----------|------|
| GDELT | Tier-1 | Global news | Free |
| Currents API | Tier-2 | Global | Free (limited) |
| WorldNews API | Tier-2 | Multi-language | Free (limited) |
| USGS | Tier-1 | Earthquakes | Free |
| NOAA | Tier-1 | Weather | Free |
| EMSC | Tier-1 | Earthquakes (Europe) | Free |

---

## Recommended Additions

### 1. FactSet Real-Time News (HIGH Priority)

**Status:** Recommended

| Aspect | Details |
|--------|---------|
| Type | Premium news feed |
| Coverage | Financial & political news |
| Latency | Real-time (<1 second) |
| Cost | ~$500-2000/month |
| Quality | Wire-level (Tier-1) |

**Advantages:**
- Sub-second breaking news
- Direct wire feeds (Reuters, AP)
- Structured metadata
- Financial market focus
- Professional-grade reliability

**Disadvantages:**
- Expensive
- Requires enterprise contract
- Financial focus may miss some events

**Use Case:** Breaking news fast-path, financial market events

---

### 2. NewsAPI.ai (HIGH Priority)

**Status:** Recommended

| Aspect | Details |
|--------|---------|
| Type | News aggregator |
| Coverage | 150,000+ sources, 80 languages |
| Latency | Near real-time |
| Cost | Free (100 req/day), Pro $79/month |
| Quality | Tier-2 (aggregated) |

**Advantages:**
- Massive source coverage
- Multilingual support
- Event clustering built-in
- Sentiment analysis
- Affordable pricing

**Disadvantages:**
- Aggregated (not wire-level)
- API rate limits
- May have duplicates

**Use Case:** Broad coverage, multilingual events, volume

---

### 3. ACLED Direct Feed (MEDIUM Priority)

**Status:** Under evaluation

| Aspect | Details |
|--------|---------|
| Type | Conflict data |
| Coverage | Global conflict events |
| Latency | Daily updates |
| Cost | Free (academic), $$ (commercial) |
| Quality | Research-grade (Tier-1) |

**Advantages:**
- Comprehensive conflict data
- Geolocated events
- Actor coding
- Historical context

**Disadvantages:**
- Daily (not real-time)
- Conflict focus only
- Commercial licensing unclear

**Use Case:** Conflict verification, historical context

---

### 4. Janes (MEDIUM Priority)

**Status:** Future consideration

| Aspect | Details |
|--------|---------|
| Type | Defense intelligence |
| Coverage | Military & security |
| Latency | Daily updates |
| Cost | Enterprise ($10K+/year) |
| Quality | Expert-level (Tier-1) |

**Advantages:**
- Authoritative military data
- Equipment identification
- Order of battle data
- Expert analysis

**Disadvantages:**
- Very expensive
- Specialized focus
- Enterprise sales process

**Use Case:** Military verification, defense events

---

### 5. ReliefWeb API (LOW Priority)

**Status:** Optional

| Aspect | Details |
|--------|---------|
| Type | Humanitarian |
| Coverage | Humanitarian crises |
| Latency | Daily updates |
| Cost | Free |
| Quality | UN-level (Tier-1) |

**Advantages:**
- Free
- UN credibility
- Humanitarian focus
- Structured data

**Disadvantages:**
- Humanitarian only
- Not real-time
- Limited scope

**Use Case:** Humanitarian events, disaster response

---

### 6. Twitter/X API v2 (DEPRIORITIZED)

**Status:** Not recommended currently

| Aspect | Details |
|--------|---------|
| Type | Social media |
| Coverage | Global social |
| Latency | Real-time |
| Cost | $100-5000/month |
| Quality | Tier-3 (unverified) |

**Reasons for deprioritization:**
- API pricing changes (expensive)
- Verification quality concerns
- Bot/spam issues
- Political controversies

**Alternative:** Use social signals via GDELT instead

---

## Implementation Priorities

### Phase 1 (Q1 2026)

| API | Priority | Rationale |
|-----|----------|-----------|
| NewsAPI.ai | HIGH | Best coverage/cost ratio |
| ACLED Direct | MEDIUM | Conflict verification |

**Estimated cost:** ~$100/month

### Phase 2 (Q2 2026)

| API | Priority | Rationale |
|-----|----------|-----------|
| FactSet | HIGH | Breaking news speed |
| ReliefWeb | LOW | Humanitarian coverage |

**Estimated cost:** ~$500-2000/month

### Phase 3 (Q3+ 2026)

| API | Priority | Rationale |
|-----|----------|-----------|
| Janes | MEDIUM | Military verification |
| Other specialized | TBD | Based on user demand |

---

## Integration Complexity

| API | Effort | Notes |
|-----|--------|-------|
| NewsAPI.ai | Low | REST API, good docs |
| ACLED | Medium | Requires data processing |
| FactSet | High | Enterprise integration |
| Janes | High | Enterprise integration |
| ReliefWeb | Low | Simple REST API |

---

## Coverage Gap Analysis

### Current Gaps

| Category | Current Coverage | Gap |
|----------|------------------|-----|
| Financial news | Partial (GDELT) | FactSet would fill |
| Multilingual | Partial | NewsAPI.ai would improve |
| Conflict data | Basic | ACLED would enhance |
| Military | None | Janes would add |
| Humanitarian | Partial | ReliefWeb would complete |

### Geographic Gaps

| Region | Current | Recommended Addition |
|--------|---------|----------------------|
| Africa | Weak | ACLED, ReliefWeb |
| Middle East | Good | ACLED |
| Asia | Moderate | NewsAPI.ai |
| Europe | Good | - |
| Americas | Good | - |

---

## Cost-Benefit Analysis

### Scenario: Add NewsAPI.ai + ACLED

**Costs:**
- NewsAPI.ai Pro: $79/month
- ACLED: Free (academic) / TBD (commercial)
- Integration: ~20 hours development
- Total: ~$100/month + one-time dev

**Benefits:**
- +50% source coverage
- +30% multilingual events
- +100% conflict data quality
- Better verification accuracy

**ROI:** High (significant coverage improvement at low cost)

### Scenario: Add FactSet

**Costs:**
- FactSet: ~$1000/month
- Integration: ~40 hours development
- Total: ~$1000/month + one-time dev

**Benefits:**
- Sub-second breaking news
- Wire-level quality
- Financial market events
- Professional reliability

**ROI:** Medium (high cost, specific use case)

---

## Recommendations

1. **Immediate:** Integrate NewsAPI.ai ($79/month) for coverage expansion
2. **Short-term:** Evaluate ACLED for conflict verification
3. **Medium-term:** Consider FactSet for enterprise/premium tier
4. **Long-term:** Monitor new APIs and specialized sources

---

## References

- NewsAPI.ai: https://newsapi.ai/
- ACLED: https://acleddata.com/
- FactSet: https://www.factset.com/
- Janes: https://www.janes.com/
- ReliefWeb: https://reliefweb.int/
