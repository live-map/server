# Importance Scoring Algorithm

## Overview

The Importance Scorer evaluates news events on a 0.0-1.0 scale using six dimensions derived from the Goldstein Scale and ACLED methodology. This determines whether an event is significant enough to warrant processing and publication.

---

## Score Components

The final importance score is a weighted sum of six components:

```
importance = (event_type × 0.20) +
             (actor_significance × 0.20) +
             (geographic_scope × 0.15) +
             (casualty_scale × 0.15) +
             (source_coverage × 0.15) +
             (escalation_potential × 0.15)
```

---

## 1. Event Type Score (Goldstein Scale)

Based on the GDELT Goldstein Scale, which measures conflict intensity from -10 (extreme conflict) to +10 (extreme cooperation).

### Normalization

```python
def goldstein_to_importance(goldstein_score: float) -> float:
    """Convert Goldstein (-10 to +10) to importance (0 to 1)"""
    return (10 - goldstein_score) / 20
```

| Goldstein Range | Importance | Example Events |
|-----------------|------------|----------------|
| -10 to -8 | 0.90-1.00 | Nuclear strike, genocide, declaration of war |
| -8 to -5 | 0.75-0.90 | Airstrike, terror attack, assassination |
| -5 to -2 | 0.60-0.75 | Armed clash, coup, violent riot |
| -2 to 0 | 0.50-0.60 | Protest, sanctions, military exercise |
| 0 to +5 | 0.25-0.50 | Ceasefire, peace talks, treaty |
| +5 to +10 | 0.00-0.25 | Alliance, humanitarian aid, cooperation |

### Event Pattern Matching

```python
EVENT_TYPE_SCORES = {
    # Extreme conflict
    "nuclear strike": -10.0,
    "genocide": -9.5,
    "ethnic cleansing": -9.0,
    "declaration of war": -8.5,
    "ground invasion": -8.0,

    # High conflict
    "airstrike": -7.0,
    "missile strike": -7.0,
    "terror attack": -7.0,
    "assassination": -5.0,

    # Moderate conflict
    "armed clash": -4.5,
    "coup": -5.0,
    "violent riot": -3.5,
    "explosion": -3.0,

    # Low conflict
    "protest": -1.0,
    "sanctions": -2.0,
    "troops deployed": 0.0,

    # Cooperative
    "ceasefire": 2.0,
    "peace talks": 3.0,
    "peace agreement": 4.0,
}
```

---

## 2. Actor Significance

Evaluates the importance of actors mentioned in the event.

| Actor Category | Score | Examples |
|----------------|-------|----------|
| UN Security Council P5 | 0.80-1.0 | US, Russia, China, France, UK |
| G7 Countries | 0.65-0.80 | Germany, Japan, Italy, Canada |
| Regional Powers | 0.60-0.85 | Iran, Saudi Arabia, Turkey, Israel |
| International Organizations | 0.70-0.90 | NATO, UN, WHO, EU |
| Non-State Actors | 0.70-0.85 | ISIS, Al-Qaeda, Hamas |
| Other | 0.30-0.50 | Regional actors |

### Calculation

```python
def calculate_actor_significance(text: str) -> float:
    matched_actors = []
    for actor, score in ACTOR_SCORES.items():
        if actor.lower() in text.lower():
            matched_actors.append(score)

    if not matched_actors:
        return 0.3  # Default for unknown actors

    return max(matched_actors)  # Use highest-significance actor
```

---

## 3. Geographic Scope

Determines if the event is local or international.

| Scope | Score | Indicators |
|-------|-------|------------|
| International | 0.80-1.0 | Multiple countries, "international", "global" |
| Regional | 0.50-0.80 | Neighboring countries, regional organizations |
| National | 0.30-0.50 | Single country, capital city |
| Local | 0.00-0.30 | City, province, local area |

### Calculation

```python
def calculate_geographic_scope(text: str) -> float:
    # Check for diplomatic terms
    diplomatic_terms = ["embassy", "ambassador", "treaty", "summit"]
    if any(term in text.lower() for term in diplomatic_terms):
        return 0.85

    # Count country mentions
    countries_mentioned = count_countries(text)
    if countries_mentioned >= 3:
        return 1.0
    elif countries_mentioned == 2:
        return 0.70
    elif countries_mentioned == 1:
        return 0.40
    else:
        return 0.20
```

---

## 4. Casualty Scale

Evaluates human impact using logarithmic scaling.

| Casualties | Score | Description |
|------------|-------|-------------|
| 500+ | 1.0 | Mass casualty event |
| 100-500 | 0.90 | Major disaster |
| 50-100 | 0.80 | Significant incident |
| 10-50 | 0.70 | Notable event |
| 5-10 | 0.55 | Moderate incident |
| 1-5 | 0.45 | Minor incident |
| 1 | 0.30 | Single casualty |
| 0 | 0.00 | No casualties |

### Calculation

```python
def calculate_casualty_scale(text: str) -> float:
    # Extract numeric casualties
    casualties = extract_casualty_count(text)

    if casualties is None:
        # Check qualitative descriptions
        if "mass casualties" in text.lower():
            return 0.9
        elif "dozens killed" in text.lower():
            return 0.7
        elif "several killed" in text.lower():
            return 0.5
        return 0.0

    # Numeric scaling
    if casualties <= 0:
        return 0.0
    elif casualties <= 1:
        return 0.3
    elif casualties <= 5:
        return 0.45
    elif casualties <= 10:
        return 0.55
    elif casualties <= 50:
        return 0.7
    elif casualties <= 100:
        return 0.8
    elif casualties <= 500:
        return 0.9
    else:
        return 1.0
```

---

## 5. Source Coverage

Evaluates the quality and diversity of reporting sources.

| Coverage | Score | Criteria |
|----------|-------|----------|
| Excellent | 0.90-1.0 | 5+ domains, 2+ Tier-1 sources |
| Good | 0.70-0.90 | 3-5 domains, 1+ Tier-1 source |
| Moderate | 0.50-0.70 | 2 domains, any tier |
| Minimal | 0.30-0.50 | 1 Tier-1 domain |
| Poor | 0.00-0.30 | 1 non-Tier-1 domain |

### Tier Definitions

```python
TIER_1_DOMAINS = {"reuters", "apnews", "afp", "ap."}
TIER_2_DOMAINS = {"bbc", "cnn", "nytimes", "guardian", "aljazeera", "dw.", "france24"}
```

### Calculation

```python
def calculate_source_coverage(sources: list[str]) -> float:
    unique_domains = set(extract_domain(s) for s in sources)
    tier1_count = sum(1 for d in unique_domains if is_tier1(d))
    tier2_count = sum(1 for d in unique_domains if is_tier2(d))

    if len(unique_domains) >= 5 and tier1_count >= 2:
        return 1.0
    elif len(unique_domains) >= 3 and tier1_count >= 1:
        return 0.8
    elif len(unique_domains) >= 2:
        return 0.6
    elif tier1_count >= 1:
        return 0.5
    else:
        return 0.3
```

---

## 6. Escalation Potential

Assesses the risk of the event expanding or worsening.

| Indicator | Score | Keywords |
|-----------|-------|----------|
| Extreme | 0.90-0.95 | "threatens war", "nuclear", "mobilization" |
| High | 0.75-0.90 | "escalating", "spreading", "warning" |
| Moderate | 0.50-0.75 | "tensions rising", "standoff" |
| Low | 0.25-0.50 | "contained", "isolated" |
| De-escalation | -0.30 penalty | "ceasefire", "withdrawal", "talks" |

### Calculation

```python
def calculate_escalation_potential(text: str) -> float:
    score = 0.5  # Baseline

    # Escalation indicators
    if "threatens war" in text.lower():
        score = 0.95
    elif "nuclear" in text.lower():
        score = max(score, 0.9)
    elif "escalating" in text.lower():
        score = max(score, 0.8)
    elif "mobilization" in text.lower():
        score = max(score, 0.85)

    # De-escalation penalty
    if any(term in text.lower() for term in ["ceasefire", "de-escalation", "withdrawal"]):
        score = max(0, score - 0.3)

    return score
```

---

## Importance Levels

| Score Range | Level | Action |
|-------------|-------|--------|
| 0.70-1.00 | **CRITICAL** | Immediate processing |
| 0.50-0.69 | **HIGH** | Standard processing |
| 0.30-0.49 | **MEDIUM** | Processing with review |
| 0.00-0.29 | **LOW** | Filtered out |

### Threshold

Events scoring below 0.25 (LOW) are filtered from the pipeline.

```python
MIN_IMPORTANCE_THRESHOLD = 0.25
```

---

## Multi-Source Boost

When an event is detected by multiple sources (via clustering), the importance score receives a boost:

```python
def apply_multi_source_boost(score: float, cluster_size: int) -> float:
    boost = min(0.1 * (cluster_size - 1), 0.3)  # Max +0.3
    return min(score + boost, 1.0)
```

| Cluster Size | Boost | Rationale |
|--------------|-------|-----------|
| 1 source | +0.0 | No boost |
| 2 sources | +0.1 | Corroboration |
| 3 sources | +0.2 | Strong signal |
| 4+ sources | +0.3 | Breaking story |

---

## Example Calculations

### Example 1: Terror Attack in Major City

**Input:**
- Title: "Terror attack in Paris kills 12"
- Content: "ISIS claims responsibility for Paris attack..."
- Sources: reuters.com, bbc.com, france24.com

**Calculation:**
```
event_type:         -7.0 → 0.85 × 0.20 = 0.170
actor_significance: ISIS → 0.80 × 0.20 = 0.160
geographic_scope:   France + Paris → 0.50 × 0.15 = 0.075
casualty_scale:     12 killed → 0.55 × 0.15 = 0.083
source_coverage:    3 domains, 1 Tier-1 → 0.80 × 0.15 = 0.120
escalation:         terror + ISIS → 0.75 × 0.15 = 0.113

Total: 0.721 → CRITICAL
```

### Example 2: Local Protest

**Input:**
- Title: "Protesters gather outside city hall"
- Content: "Dozens protest new parking fees..."
- Sources: localgazette.com

**Calculation:**
```
event_type:         protest → 0.55 × 0.20 = 0.110
actor_significance: none → 0.30 × 0.20 = 0.060
geographic_scope:   local → 0.20 × 0.15 = 0.030
casualty_scale:     0 → 0.00 × 0.15 = 0.000
source_coverage:    1 non-Tier-1 → 0.30 × 0.15 = 0.045
escalation:         none → 0.50 × 0.15 = 0.075

Total: 0.320 → MEDIUM (but likely filtered)
```

---

## Configuration

```python
# Default weights
IMPORTANCE_WEIGHTS = {
    "event_type": 0.20,
    "actor_significance": 0.20,
    "geographic_scope": 0.15,
    "casualty_scale": 0.15,
    "source_coverage": 0.15,
    "escalation_potential": 0.15,
}

# Thresholds
MIN_IMPORTANCE_THRESHOLD = 0.25
CRITICAL_IMPORTANCE_THRESHOLD = 0.70
```

---

## File Location

```
app/agent/importance_scorer.py
```

---

## Related Documentation

- [ADR-008: Importance Scoring](../adr/ADR-008-importance-scoring.md)
- [Source Tiers](SOURCE_TIERS.md)
- [Confidence Scoring](CONFIDENCE_SCORING.md)
