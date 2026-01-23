# International Affairs Focus Strategy

## 1. Why Focus?

### 1.1 Resource Efficiency

The current system's throughput is limited:

| Item | Current Value |
|------|--------|
| Investigations per 15 minutes | Maximum 5 |
| Maximum articles per day | ~480 |
| Events collected | ~168/scan |

**Problem**: Out of 1000 events, only 10-20 are truly important

### 1.2 Quality > Quantity

| Strategy | Result |
|------|------|
| Process all categories | Shallow coverage, dispersed quality |
| **Focus on international affairs** | Deep coverage, build expertise |

### 1.3 Differentiation Strategy

| Category | Competitive Landscape |
|----------|----------|
| Natural disasters | USGS/NOAA operate as official channels |
| Economic news | Specialized services like Bloomberg, Reuters exist |
| **International affairs** | Breaking news + verification = differentiation possible |

---

## 2. Included Categories

### 2.1 Category Definitions

| Category | Description | Keywords | Examples |
|----------|------|--------|------|
| **war** | War, armed conflict, invasion | war, invasion, airstrike, missile, bombing, troops, offensive | Russia-Ukraine War |
| **conflict** | Regional disputes, combat, clashes | conflict, clash, fighting, battle, skirmish, ceasefire | Gaza conflict, Sudan civil war |
| **politics** | Summits, diplomacy, sanctions, elections | summit, sanctions, election, president, prime minister, parliament | US-China summit, North Korea sanctions |
| **security** | Terrorism, nuclear, cyberattacks | nuclear, cyberattack, espionage, intelligence | Iran nuclear negotiations, North Korea missiles |
| **military** | Military operations, weapons, exercises | military, army, navy, air force, defense, weapons, deployment | NATO expansion, joint exercises |
| **terrorism** | Terror attacks, terrorist organizations | terrorist, terrorism, extremist, hostage, attack | ISIS attacks, Al-Qaeda |
| **diplomacy** | Diplomatic negotiations, treaties, embassies | diplomat, embassy, treaty, negotiation, ambassador | Peace agreements, ambassador expulsion |

### 2.2 Keyword Mapping

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

## 3. Excluded Categories

### 3.1 Exclusion List

| Category | Reason for Exclusion |
|----------|----------|
| **natural_disaster** | USGS/NOAA operate as official channels, faster and more accurate than us |
| **economy** | Requires separate expertise (financial data, market analysis) |
| **society** | Too broad in scope, difficult to maintain quality |

### 3.2 Exclusion Method

```python
# config.py
usgs_enabled: bool = False  # Disable earthquakes
noaa_enabled: bool = False  # Disable weather

# Or exclude via category filter
focus_international_affairs: bool = True
international_affairs_categories: list[str] = [
    "war", "conflict", "politics", "security",
    "military", "terrorism", "diplomacy"
]
```

### 3.3 Future Expansion Plan

| Phase | Categories | Conditions |
|-------|----------|------|
| A (Current) | 7 international affairs categories | M1/M2 MacBook |
| B | + natural_disaster | When GPU server is secured |
| C | + economy, society | When Kubernetes distributed processing is available |

---

## 4. Implementation Details

### 4.1 config.py Settings

```python
class AgentSettings(BaseSettings):
    # Disable natural disaster sources
    usgs_enabled: bool = False
    noaa_enabled: bool = False

    # Increase Investigation throughput
    max_investigations: int = 5  # 3 → 5

    # Define international affairs categories
    international_affairs_categories: list[str] = [
        "war", "conflict", "politics", "security",
        "military", "terrorism", "diplomacy"
    ]

    # International affairs focus mode
    focus_international_affairs: bool = True
```

### 4.2 scanner.py Filter Logic

```python
def _infer_category_from_event(self, event: TriggerEvent) -> str:
    """Infer category from event (international affairs subdivision)"""
    text = f"{event.title} {event.content}".lower()

    # International affairs keyword mapping
    for category, keywords in INTERNATIONAL_AFFAIRS_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category

    # Source-based classification
    if event.source == TriggerSource.USGS:
        return "natural_disaster"
    if event.source == TriggerSource.NOAA:
        return "natural_disaster"

    return "other"


async def _classify_and_group(self, events: list[TriggerEvent]) -> list[dict]:
    """Classify and group events"""

    # ... existing logic ...

    # Apply international affairs filter
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

### 4.3 Category Classification Improvement

#### Original Categories
```
natural_disaster, war, terrorism, protest, military, violence, other
```

#### Improved Categories (International Affairs Subdivision)
```
war           - War, armed conflict, invasion
conflict      - Regional disputes, clashes, combat
politics      - Summits, diplomacy, sanctions, elections
security      - Terrorism, nuclear, cyberattacks
military      - Military operations, weapons, exercises
terrorism     - Terror attacks, terrorist organizations
diplomacy     - Diplomatic negotiations, treaties, embassies
```

---

## 5. Expected Results

### 5.1 Before vs After

| Metric | Before | After |
|------|--------|-------|
| Collected events | 168 | ~80 (international affairs only) |
| Filter passed | 21 | ~15 |
| Articles generated | 3 (mostly disasters) | 5 (all international affairs) |
| Daily articles | ~288 | ~480 |
| Article quality | Dispersed | Focused on international affairs |

### 5.2 Log Output

```
10:06:47 | INFO | International affairs filter: 12/95 events
10:06:47 | INFO | Filtered categories: war(3), conflict(2), politics(4), security(2), diplomacy(1)
10:06:47 | INFO | Excluded: natural_disaster(46), economy(15), society(12), other(10)
```

---

## 6. Expansion Roadmap

### Phase A: Current (M1/M2 MacBook)

| Item | Setting |
|------|------|
| Sources | GDELT + Reddit only enabled |
| Categories | 7 international affairs categories only |
| Throughput | 5 articles per 15 minutes |
| Cost | $100-200/month |

### Phase B: GPU Server (RTX 3080+)

| Item | Setting |
|------|------|
| Sources | All Tier-1/2 enabled |
| Categories | + natural_disaster |
| Throughput | 10 articles per 15 minutes |
| Cost | $450-600/month |

**Performance Improvements**:
- Embedding 10x faster (30 seconds → 3 seconds)
- LLM concurrent calls 5 → 10

### Phase C: Distributed Processing (Kubernetes)

| Item | Setting |
|------|------|
| Sources | All sources enabled |
| Categories | All categories |
| Throughput | 50+ articles per 15 minutes |
| Cost | $800-1000/month |

**Architecture**:
- Multiple workers perform parallel Investigation
- Kafka queue manages event backlog
- Redis manages Investigation state

---

## 7. Key Monitoring Metrics

### 7.1 Category Distribution

```
Log per scan:
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

### 7.2 Investigation Success Rate

```
[INVESTIGATION STATS]
- Attempted: 5
- Success (article generated): 4 (80%)
- Skipped (duplicate): 1 (20%)
- Failed: 0 (0%)
```

### 7.3 Quality Metrics

| Metric | Target | Measurement Method |
|------|------|----------|
| International affairs ratio | > 90% | Ratio of international affairs categories among generated articles |
| Duplicate rate | < 30% | Ratio of skipped Investigations |
| Two-Source fulfillment | > 60% | Ratio of articles verified by 2+ sources |

---

## Changelog

| Date | Changes |
|------|----------|
| 2025-01-23 | Initial document created |

---

*This document describes the design and implementation of the International Affairs Focus Strategy.*
