# Scanner Pipeline Detailed Documentation

## Overview

The Scanner is a pipeline that collects news events from multiple sources, filters them based on confidence scores, and selects events worthy of article generation.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              SCANNER PIPELINE                                     │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   [Stage 1]        [Stage 2]        [Stage 3]        [Stage 3.5]                │
│   Trigger    →    Clustering   →   Classification →  Event         →            │
│   Collection      & Dedup          & Grouping        Verification               │
│                                                      (Gate 0)                   │
│                                                                                  │
│   [Stage 4]        [Stage 5]        [Stage 6]        [Stage 7]                  │
│   Confidence  →   Content     →    Final        →   Output                      │
│   Scoring         Gates            Filtering        to Agent                    │
│                   (Gate 1-2)                                                    │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Stage 1: Trigger Collection

### 1.1 Overview

Events are collected in parallel from each source (Trigger).

**File**: `app/agent/triggers/manager.py`

### 1.2 Source Tier Classification

| Tier | Source | Reliability | Description |
|------|--------|-------------|-------------|
| **Tier-1 Govt** | USGS | 0.99 | U.S. Geological Survey (Earthquakes) |
| **Tier-1 Govt** | NOAA | 0.99 | National Oceanic and Atmospheric Administration (Weather Alerts) |
| **Tier-1 News** | GDELT | 0.90 | Global Event Database |
| **Tier-1 News** | GDELT Anomaly | 0.90 | GDELT Anomaly Detection |
| **Tier-2 Data** | ACLED | 0.85 | Conflict Data |
| **Tier-2 News** | Currents | 0.75 | News API |
| **Tier-2 News** | WorldNews | 0.75 | News API |
| **Tier-3 Social** | Reddit | 0.40 | Social Media |
| **Tier-3 Social** | Bluesky | 0.40 | Social Media |
| **Tier-3 Trend** | Google Trends | 0.30 | Search Trends |

### 1.3 Collection Example

```python
# TriggerManager.scan_all() call
events = await self.trigger_manager.scan_all()
```

**Input**: None (configuration-based)

**Output Example**:
```python
[
    TriggerEvent(
        source=TriggerSource.USGS,
        title="M5.2 Earthquake - 120 km SSE of Sand Point, Alaska",
        content="Magnitude 5.2 earthquake at depth 10km...",
        url="https://earthquake.usgs.gov/...",
        detected_at=datetime(2026, 1, 23, 10, 0, 0),
        keywords_matched=["earthquake"],
        metadata={"magnitude": 5.2, "depth": 10}
    ),
    TriggerEvent(
        source=TriggerSource.GDELT,
        title="Trump Administration Arrests Three Protesters",
        content="Federal agents arrested three people...",
        url="https://...",
        detected_at=datetime(2026, 1, 23, 10, 5, 0),
        keywords_matched=["protest", "arrested"],
        metadata={"tone": -3.5}
    ),
    # ... more events
]
```

**Log Output**:
```
10:06:36 | INFO | USGS scan: 3 earthquakes found (M5.0+)
10:06:37 | INFO | NOAA scan: 58 severe alerts found
10:06:39 | INFO | Reddit scan: 14 new posts found
10:06:47 | INFO | GDELT Anomaly scan: 50 GKG, 0 Goldstein, 50 total new
10:06:47 | INFO | Total events: 125, unique: 109
```

### 1.4 Individual Trigger Operations

#### USGS (Earthquakes)
```python
# app/agent/triggers/usgs.py
async def scan(self) -> list[TriggerEvent]:
    # USGS API call: last 1 hour, M5.0 or higher
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    params = {
        "format": "geojson",
        "minmagnitude": 5.0,
        "starttime": (now - 1hour).isoformat()
    }
    # Parse response → return TriggerEvent list
```

#### NOAA (Weather Alerts)
```python
# app/agent/triggers/noaa.py
async def scan(self) -> list[TriggerEvent]:
    # NOAA Alerts API call
    url = "https://api.weather.gov/alerts/active"
    params = {"severity": "Extreme,Severe"}
    # Filter Warning, Watch, Advisory
```

#### GDELT (News)
```python
# app/agent/triggers/gdelt.py
async def scan(self) -> list[TriggerEvent]:
    # GDELT DOC API call
    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": "(airstrike OR missile OR protest OR earthquake...)",
        "mode": "artlist",
        "maxrecords": 100,
        "timespan": "1h"
    }
```

#### Reddit (Social)
```python
# app/agent/triggers/reddit.py
async def scan(self) -> list[TriggerEvent]:
    # Reddit JSON API (no authentication required)
    subreddits = ["worldnews", "news", "UkraineWarVideoReport", "CombatFootage"]
    for sub in subreddits:
        url = f"https://www.reddit.com/r/{sub}/new.json"
        # Minimum score filtering (default 10)
```

---

## Stage 2: Semantic Clustering

### 2.1 Overview

Groups identical/similar events to remove duplicates.

**File**: `app/agent/triggers/clustering.py`

### 2.2 How It Works

```
Input: 109 events
         ↓
    [Generate Embeddings]
    Vectorize each event text using BAAI/bge-m3 model
         ↓
    [HDBSCAN Clustering]
    Group similar events together
         ↓
    [Select Representative Event]
    Choose the most representative event from each cluster
         ↓
Output: 39 clusters (duplicates removed)
```

### 2.3 Example

**Input** (3 similar articles):
```python
[
    TriggerEvent(title="M6.2 earthquake strikes Russia's Kamchatka", source=GDELT),
    TriggerEvent(title="Strong 6.2 magnitude quake hits Kamchatka Peninsula", source=GDELT),
    TriggerEvent(title="Earthquake of magnitude 6.2 recorded near Vilyuchinsk", source=GDELT_ANOMALY),
]
```

**Processing**:
```python
# 1. Generate embeddings
embeddings = encoder.encode([
    "M6.2 earthquake strikes Russia's Kamchatka",
    "Strong 6.2 magnitude quake hits Kamchatka Peninsula",
    "Earthquake of magnitude 6.2 recorded near Vilyuchinsk"
])
# Shape: (3, 1024)

# 2. Calculate cosine similarity
similarity_matrix = [
    [1.00, 0.89, 0.85],  # Article 1 vs Articles 1,2,3
    [0.89, 1.00, 0.87],  # Article 2 vs Articles 1,2,3
    [0.85, 0.87, 1.00],  # Article 3 vs Articles 1,2,3
]

# 3. Clustering (threshold=0.7)
# All above 0.7, so grouped into one cluster

# 4. Select representative event (longest content or first)
```

**Output** (1 cluster):
```python
Cluster(
    id="eb719719d08a",
    representative=TriggerEvent(title="M6.2 earthquake strikes Russia's Kamchatka"),
    members=[event1, event2, event3],
    size=3
)
```

**Log Output**:
```
10:06:47 | INFO | New cluster detected: eb719719d08a (3 docs)
10:06:47 | INFO | New cluster detected: 3017d6e3fd2e (2 docs)
10:06:47 | INFO | New cluster detected: 07ebcab08784 (42 docs)  # Large cluster
...
```

---

## Stage 3: Source Classification

### 3.1 Overview

Classifies events into Tier-1 government sources and other sources.

**File**: `app/agent/scanner.py` (`_classify_and_group` method)

### 3.2 Classification Logic

```python
# SOURCE_TIER_MAP definition (app/agent/triggers/base.py)
SOURCE_TIER_MAP = {
    TriggerSource.USGS: SourceTier.TIER1_GOVT,
    TriggerSource.NOAA: SourceTier.TIER1_GOVT,
    TriggerSource.GDELT: SourceTier.TIER1_NEWS,
    TriggerSource.GDELT_ANOMALY: SourceTier.TIER1_NEWS,
    TriggerSource.REDDIT: SourceTier.TIER3_SOCIAL,
    # ...
}
```

### 3.3 Example

**Input**: 109 events

**Processing**:
```python
tier1_govt_events = []  # USGS, NOAA
other_events = []       # GDELT, Reddit, etc.

for event in events:
    source_tier = SOURCE_TIER_MAP.get(event.source)
    if source_tier == SourceTier.TIER1_GOVT:
        tier1_govt_events.append(event)
    else:
        other_events.append(event)
```

**Output**:
```
tier1_govt_events: 46 (USGS 3 + NOAA 43)
other_events: 63 (GDELT 50 + Reddit 13)
```

**Log Output**:
```
10:06:47 | INFO | Source classification: 46 Tier-1 govt, 63 other sources
```

### 3.4 Special Handling for Tier-1 Government Sources

Tier-1 government sources (USGS, NOAA) are **exempt from the Two-Source Rule**:
- As official agency announcements, they can be published immediately without additional verification
- Confidence Score is automatically assigned as 0.74

---

## Stage 3.5: Event Verification (Gate 0) - 3-Stage Hybrid

### 3.5.1 Overview

From content collected via keyword matching, only **actual events** are allowed to pass through.

**File**: `app/agent/event_verifier.py`

**Reference Documentation**: [Zero-shot Classification](./ZERO_SHOT_CLASSIFIER.md), [Event Verification](./EVENT_VERIFICATION.md)

### 3.5.2 Problem Definition

Keyword matching generates False Positives:

| Collected Content | Keyword | Is Real Event |
|-------------------|---------|---------------|
| "Iran attacks US bases" | attack | O Real |
| "New war movie releases" | war | X Movie |
| "Call of Duty review" | war | X Game |
| "In 1945, the war ended" | war | X History |

### 3.5.3 3-Stage Hybrid Solution

```
Collected events (168)
    ↓
[Stage 1: Rule-based Filter] - $0, ~1ms
- NOT_EVENT_PATTERNS matching
- Remove movies/games/history/sports
- Multilingual sports patterns (Korean/Arabic/Chinese)
    ↓ (~50 pass, 70% filtered)
[Stage 2: Zero-shot Classification] - $0, ~50ms
- BART-large-MNLI local model
- Confidence ≥ 0.8 → immediate decision
- Confidence < 0.8 → proceed to Stage 3
    ↓ (~40 pass or forwarded to LLM)
[Stage 3: LLM Verification] - $0.001/item, ~300ms
- Only handles edge cases
- PASS/REJECT + REASON
    ↓
Verified events (~35)
```

### 3.5.4 Stage 1: Rule-based Filter

```python
NOT_EVENT_PATTERNS = [
    # Entertainment
    r"\b(movie|film|tv show|series|drama|actor|actress|celebrity)\b",
    # Games
    r"\b(game|gaming|esports|playstation|xbox|nintendo)\b",
    # History/Past
    r"\b(in \d{4}|years ago|historically|last century|decades ago)\b",
    # Speculation/Hypothetical
    r"\b(if .* would|could potentially|might happen|hypothetically)\b",
    # Reviews/Opinions
    r"\b(review|opinion|editorial|analysis|commentary)\b",
    # Sports (English)
    r"\b(football|soccer|basketball|tennis|olympics|world cup)\b",
    # Sports (Multilingual)
    r"(손흥민|토트넘|맨유|리버풀|챔피언스리그|월드컵)",  # Korean
    r"(كرة القدم|الدوري|ريال مدريد|برشلونة)",  # Arabic
    r"(足球|皇马|巴萨|世界杯|欧冠)",  # Chinese
]

def is_likely_real_event(text: str) -> tuple[bool, str | None]:
    text_lower = text.lower()
    for pattern in NOT_EVENT_PATTERNS:
        if re.search(pattern, text_lower):
            return False, f"NOT_EVENT: matched pattern '{pattern}'"
    return True, None
```

### 3.5.5 Stage 2: Zero-shot Classification

```python
from app.agent.zero_shot_classifier import get_zero_shot_classifier

# CAMEO/ACLED-based labels
INTERNATIONAL_AFFAIRS_LABELS = [
    "military conflict", "diplomatic relations", "terrorism",
    "humanitarian crisis", "international sanctions", "protest and civil unrest"
]

REJECT_LABELS = [
    "sports", "entertainment", "local news", "opinion and analysis"
]

def classify_with_zero_shot(text: str) -> tuple[bool | None, float, str]:
    classifier = get_zero_shot_classifier()
    is_intl, confidence, label = classifier.classify(text)
    return is_intl, confidence, label
```

**Decision Criteria**:
| Classification Result | Confidence | Decision |
|-----------------------|------------|----------|
| International | ≥ 0.8 | **PASS** immediately |
| Rejection | ≥ 0.8 | **REJECT** immediately |
| Any | < 0.8 | Proceed to Stage 3 (LLM) |

### 3.5.6 Stage 3: LLM Verification

```python
EVENT_VERIFY_PROMPT = """Determine whether the following text reports an actual international affairs event.

Text: {text}

Judgment Criteria:
- PASS: Actual occurring events (war, diplomacy, terrorism, protests, summits, etc.)
- REJECT: Movies/games/history/speculation/opinions/sports/entertainment

Response Format:
VERDICT: PASS or REJECT
REASON: One-line explanation"""
```

### 3.5.7 Cost Analysis

| Stage | Throughput | Cost | Filter Rate |
|-------|------------|------|-------------|
| Stage 1 (Rules) | 168 → 50 | $0 | ~70% |
| Stage 2 (Zero-shot) | 50 → 40 | $0 | ~20% |
| Stage 3 (LLM) | 15 (uncertain cases) | $0.015/scan | Edge cases |
| **Daily Total Cost** | | **$1.44** | |

**Cost Savings**:
- LLM only: $16.13/day
- 2-stage hybrid (Rules + LLM): $4.80/day (70% savings)
- 3-stage hybrid (Rules + Zero-shot + LLM): $1.44/day (**91% savings**)

### 3.5.8 Configuration

```python
# config.py
event_verification_enabled: bool = True
event_verification_use_zero_shot: bool = True  # Enable Zero-shot classification
event_verification_use_llm: bool = True         # Enable LLM verification (Stage 3)
```

**Log Output**:
```
10:06:47 | INFO | [GATE0-REJECT] NOT_EVENT: matched pattern 'movie': New war movie...
10:06:47 | INFO | [GATE0-REJECT] ZERO_SHOT: sports (0.92): World Cup final...
10:06:48 | INFO | [GATE0-PASS] ZERO_SHOT: military conflict (0.89): Iran attacks...
10:06:48 | INFO | [GATE0-REJECT] LLM_REJECT: Fictional scenario (movie plot)
10:06:48 | INFO | Event verification: 35/168 passed (79% filtered)
```

---

## Stage 4: Cross-Source Matching & Confidence Scoring

### 4.1 Overview

Finds identical events from different sources, groups them, and calculates confidence scores.

**Files**:
- `app/agent/cross_source_matcher.py`
- `app/agent/confidence_scorer.py`

### 4.2 Cross-Source Matching

```
Input: 63 "other_events" (GDELT, Reddit)
         ↓
    [Embedding-based Similarity Calculation]
    Match similar events across different sources
         ↓
    [Create MatchedEvent]
    - Single source: cluster_size=1
    - Multiple sources: cluster_size=2+
         ↓
Output: 50 clusters
```

**Example - Multi-source Matching**:
```python
# GDELT article
event1 = TriggerEvent(
    source=GDELT,
    title="Minnesota church protest leads to arrests"
)

# Reddit post
event2 = TriggerEvent(
    source=REDDIT,
    title="3 arrested at Minnesota church during ICE protest"
)

# Similarity: 0.82 (exceeds threshold 0.70)
# → Grouped into one MatchedEvent

matched = MatchedEvent(
    primary_event=event1,
    matching_events=[event2],
    similarity_scores=[0.82],
    source_count=2  # GDELT + Reddit
)
```

### 4.3 Confidence Scoring

**Confidence Calculation Formula**:
```python
final_score = (base_score * 0.5) + (tier_average * 0.5) + diversity_bonus
```

**Base Score (based on number of sources)**:
| Number of Sources | Base Score |
|-------------------|------------|
| 1 | 0.50 |
| 2 | 0.70 |
| 3+ | 0.85 |

**Tier Average (average source reliability)**:
```python
# Example: 1 GDELT source
tier_average = 0.90

# Example: GDELT + Reddit
tier_average = (0.90 + 0.40) / 2 = 0.65
```

**Diversity Bonus**:
- +0.03 if sources come from different Tiers

### 4.4 Calculation Examples

#### Example 1: USGS Single Source
```python
sources = [{"name": "usgs", "tier": "tier1_govt"}]

base_score = 0.50       # 1 source
tier_average = 0.99     # tier1_govt
diversity_bonus = 0.00  # single tier

final = (0.50 * 0.5) + (0.99 * 0.5) + 0.00
      = 0.25 + 0.495 + 0.00
      = 0.745 → 0.74 (rounded)

recommendation = "immediate_publish"  # tier1_govt special handling
```

#### Example 2: GDELT Single Source
```python
sources = [{"name": "gdelt", "tier": "tier1_news"}]

base_score = 0.50       # 1 source
tier_average = 0.90     # tier1_news
diversity_bonus = 0.00

final = (0.50 * 0.5) + (0.90 * 0.5) + 0.00
      = 0.25 + 0.45 + 0.00
      = 0.70

recommendation = "publishable"
```

#### Example 3: GDELT + Reddit (Multiple Sources)
```python
sources = [
    {"name": "gdelt", "tier": "tier1_news"},
    {"name": "reddit", "tier": "tier3_social"}
]

base_score = 0.70       # 2 sources
tier_average = (0.90 + 0.40) / 2 = 0.65
diversity_bonus = 0.03  # tier1 + tier3

final = (0.70 * 0.5) + (0.65 * 0.5) + 0.03
      = 0.35 + 0.325 + 0.03
      = 0.705 → 0.71

two_source_satisfied = True  # 2 or more sources
recommendation = "publishable"
```

#### Example 4: Reddit Single Source (Filtered)
```python
sources = [{"name": "reddit", "tier": "tier3_social"}]

base_score = 0.50       # 1 source
tier_average = 0.40     # tier3_social
diversity_bonus = 0.00

final = (0.50 * 0.5) + (0.40 * 0.5) + 0.00
      = 0.25 + 0.20 + 0.00
      = 0.45

recommendation = "do_not_publish"  # below 0.70
```

**Log Output**:
```
10:06:48 | INFO | [CONFIDENCE] usgs: 0.74 (immediate_publish)
10:06:48 | INFO | [CONFIDENCE] Cluster (1 sources): 0.70 (publishable) | Two-Source: False | EEUU prohibirá...
10:06:48 | INFO | [CONFIDENCE] Cluster (1 sources): 0.45 (do_not_publish) | Two-Source: False | Reddit post...
10:06:48 | INFO | Confidence filter: 95 events passed (threshold=0.7)
```

---

## Stage 5: Content Gates

### 5.1 Overview

Additional filtering to determine if content is worthy of article generation.

**Files**:
- `app/agent/checkworthiness.py` (Gate 1)
- `app/agent/specificity.py` (Gate 2)

### 5.2 Gate 1: Check-worthiness

**Purpose**: Filter out entertainment, speculative articles, and human interest stories

```python
def check_worthiness(text, entertainment_threshold, speculation_threshold, human_interest_threshold):
    # Entertainment patterns
    entertainment_patterns = [
        r'\b(celebrity|movie|album|concert|grammy|oscar)\b',
        r'\b(kardashian|swift|bieber)\b',
        ...
    ]

    # Speculation patterns
    speculation_patterns = [
        r'\b(might|could|may|possibly|rumor)\b',
        r'\b(sources say|reportedly|allegedly)\b',
        ...
    ]

    # Human interest patterns
    human_interest_patterns = [
        r'\b(heartwarming|inspiring|adorable)\b',
        r'\b(viral video|cute|amazing story)\b',
        ...
    ]
```

**Example**:
```python
# Article that passes
text = "Federal agents arrested three protesters at a Minnesota church"
result = check_worthiness(text)
# → is_checkworthy=True

# Article that gets filtered
text = "Taylor Swift's new album might be released next month, sources say"
result = check_worthiness(text)
# → is_checkworthy=False, reason=ENTERTAINMENT
```

### 5.3 Gate 2: Specificity

**Purpose**: Verify that specific information (who, when, where, what) is present

```python
def check_specificity(text, min_score=0.3):
    score = 0.0

    # Numbers present (+0.2)
    if re.search(r'\d+', text):
        score += 0.2

    # Proper nouns present (+0.2)
    if re.search(r'[A-Z][a-z]+', text):
        score += 0.2

    # Date present (+0.2)
    if re.search(r'(January|February|...|2026|yesterday)', text):
        score += 0.2

    # Location present (+0.2)
    if re.search(r'(in|at|near) [A-Z][a-z]+', text):
        score += 0.2

    # Quote present (+0.2)
    if re.search(r'[""].*[""]', text):
        score += 0.2

    return SpecificityResult(score=score, is_specific=(score >= min_score))
```

**Example**:
```python
# High specificity
text = "A magnitude 5.2 earthquake struck 120 km southeast of Sand Point, Alaska on January 23, 2026"
# Numbers (5.2, 120): +0.2
# Proper nouns (Sand Point, Alaska): +0.2
# Date (January 23, 2026): +0.2
# Location (southeast of Sand Point): +0.2
# → score=0.8, is_specific=True

# Low specificity
text = "Something happened somewhere recently"
# → score=0.0, is_specific=False
```

### 5.4 Gate Application Rules

| Source | Gate 1 | Gate 2 |
|--------|--------|--------|
| Tier-1 Govt (USGS, NOAA) | **Exempt** | **Exempt** |
| Tier-1 News (GDELT) - English | Applied | Applied |
| Tier-1 News (GDELT) - Non-English | Applied | **Exempt** |
| Tier-3 Social (Reddit) | Applied | Applied |

**Reason for Non-English Exemption**: Specificity patterns are English-only, so applying them to non-English articles would cause false positives

**Log Output**:
```
10:06:48 | INFO | Content gates: 95/95 passed
# Or when filtered
10:06:48 | INFO | [GATE1-REJECT] ENTERTAINMENT: Taylor Swift's new album...
10:06:48 | INFO | [GATE2-REJECT] Low specificity (0.10): Something happened...
```

---

## Stage 6: Final Filtering

### 6.1 Pass Conditions

For an event to become a final publication candidate:

```python
# Condition 1: Meet confidence threshold
confidence.score >= 0.70

# OR

# Condition 2: Satisfy Two-Source Rule
confidence.two_source_satisfied == True
```

### 6.2 Result Formatting

```python
results.append({
    "description": event.title,
    "category": category,  # natural_disaster, war, protest, etc.
    "sources": ["USGS"],
    "source_count": 1,
    "trigger_source": "usgs",
    "keywords": ["earthquake"],
    "url": "https://...",
    "confidence_score": 0.74,
    "confidence_level": "high",
    "two_source_satisfied": False,
    "recommendation": "immediate_publish",
    "is_tier1_govt": True,
})
```

### 6.3 Category Inference

```python
def _infer_category_from_event(self, event):
    text = f"{event.title} {event.content}".lower()

    # Source-based
    if event.source == USGS:
        return "natural_disaster"
    if event.source == NOAA:
        return "natural_disaster"

    # Keyword-based
    if any(kw in text for kw in ["earthquake", "tsunami", "flood"]):
        return "natural_disaster"
    if any(kw in text for kw in ["war", "invasion", "airstrike"]):
        return "war"
    if any(kw in text for kw in ["terrorist", "bombing"]):
        return "terrorism"
    if any(kw in text for kw in ["protest", "demonstration"]):
        return "protest"

    return "other"
```

---

## Stage 7: Output to Agent

### 7.1 Output Format

```python
[
    {
        "description": "M5.2 Earthquake - 120 km SSE of Sand Point, Alaska",
        "category": "natural_disaster",
        "sources": ["USGS"],
        "source_count": 1,
        "confidence_score": 0.74,
        "is_tier1_govt": True,
    },
    {
        "description": "3 people involved in Minnesota church protest arrested",
        "category": "protest",
        "sources": ["kunr.org"],
        "source_count": 1,
        "confidence_score": 0.70,
        "is_tier1_govt": False,
    },
    # ... total 95 events
]
```

### 7.2 Sorting Order

1. **Tier-1 Govt first** (USGS, NOAA)
2. **Higher confidence first** (0.74 > 0.70)
3. **Multiple sources first** (higher source_count)

### 7.3 Investigation Handoff

```python
# lifespan.py
max_investigations = 3
investigation_count = 0

for event in events:
    if investigation_count >= max_investigations:
        break

    # Duplicate check (DB query)
    if is_duplicate(event):
        continue  # Don't increment count

    # Hand off to Agent
    result = await agent.investigate(
        event=event["description"],
        category=event["category"],
    )

    # Increment count on success
    if result.get("article_en"):
        save_to_db(result)
        investigation_count += 1
```

---

## Complete Flow Summary

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Stage 1: Trigger Collection                                             │
│ ─────────────────────────────                                           │
│ USGS: 3, NOAA: 58, GDELT: 50, Reddit: 14                                │
│ → Total: 125, Unique: 109                                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ Stage 2: Semantic Clustering                                            │
│ ────────────────────────────                                            │
│ 109 → 39 clusters (duplicates removed)                                  │
│ Example: 3 articles about "Russia earthquake" → 1 cluster               │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ Stage 3: Source Classification                                          │
│ ─────────────────────────────                                           │
│ Tier-1 Govt: 46 (USGS 3 + NOAA 43)                                      │
│ Other: 63 (GDELT 50 + Reddit 13)                                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ Stage 3.5: Event Verification (Gate 0) - 3-Stage Hybrid                 │
│ ─────────────────────────────────────────────────                       │
│ Stage 1 (Rules): Remove movie/game/history/sports patterns → 70% filter │
│ Stage 2 (Zero-shot): BART-MNLI classification, confidence ≥0.8 → 20%    │
│ Stage 3 (LLM): Final judgment for uncertain cases only                  │
│ → 109 → 35 passed (74 filtered)                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ Stage 4: Confidence Scoring                                             │
│ ──────────────────────────                                              │
│ USGS/NOAA: 0.74 (immediate_publish)                                     │
│ GDELT: 0.70 (publishable)                                               │
│ Reddit: 0.45 (do_not_publish) → filtered                                │
│ → 96 passed (threshold=0.70)                                            │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ Stage 5: Content Gates                                                  │
│ ────────────────────                                                    │
│ Gate 1 (Check-worthiness): Filter entertainment/speculation             │
│ Gate 2 (Specificity): Specificity check (English only)                  │
│ → 95 passed                                                             │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ Stage 6: Deduplication (DB Query)                                       │
│ ──────────────────────────────                                          │
│ Skip already published events                                           │
│ Example: M5.2 Alaska earthquake → already exists as event_id=24 → SKIP  │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ Stage 7: Output to Agent                                                │
│ ────────────────────────                                                │
│ Pass up to 3 events to ClaimVerificationAgent                           │
│ Agent generates article and saves to DB                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Configuration Options (config.py)

```python
class AgentSettings:
    # Trigger settings
    gdelt_enabled: bool = True
    gdelt_timespan: str = "1h"
    usgs_enabled: bool = True
    usgs_min_magnitude: float = 5.0
    noaa_enabled: bool = True
    reddit_enabled: bool = True

    # Confidence settings
    min_confidence_score: float = 0.70
    cross_source_similarity_threshold: float = 0.70

    # Event Verification (Gate 0) settings
    event_verification_enabled: bool = True
    event_verification_use_zero_shot: bool = True  # Stage 2 Zero-shot
    event_verification_use_llm: bool = True        # Stage 3 LLM

    # Gate settings
    checkworthiness_enabled: bool = True
    specificity_enabled: bool = True
    min_specificity_score: float = 0.30

    # Logging
    log_gate_rejections: bool = True
```

---

## Debugging Guide

### When Events Are Not Being Collected
```bash
# Check each trigger's response
10:06:37 | ERROR | GDELT scan error: 429 Too Many Requests
# → Rate limit. Retry after a while
```

### When Events Are Being Filtered
```bash
# Confidence filter
10:06:48 | INFO | [CONFIDENCE] Cluster (1 sources): 0.45 (do_not_publish)
# → Reddit single source. Needs matching with another source

# Gate 1 filter
10:06:48 | INFO | [GATE1-REJECT] ENTERTAINMENT: Celebrity news...
# → Entertainment article

# Gate 2 filter
10:06:48 | INFO | [GATE2-REJECT] Low specificity (0.10): Vague headline...
# → Lacks specific information
```

### When Articles Are Not Being Generated
```bash
[SCANNER] [1] SKIPPING: Duplicate event (matched event_id=24)
[SCANNER] [2] SKIPPING: Duplicate event (matched event_id=22)
[SCANNER] [3] SKIPPING: Duplicate event (matched event_id=23)
# → All top events are duplicates. New events cannot obtain investigation slots
# → Need to modify lifespan.py (duplicates should not consume slots)
```
