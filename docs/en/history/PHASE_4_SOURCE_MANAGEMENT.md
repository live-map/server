# Phase 4: Source Management

**Date**: January 23-24, 2026
**Git Phases**: 8, 10 (Quality Gates & Event Verification)

---

## Overview

This phase focused on source quality management and content filtering. The system implemented comprehensive date filtering, evidence quality controls, and category-based content filters to ensure only relevant, recent, high-quality events are processed.

---

## Timeline

```
Jan 23 ─────────────────────────────────────────────────────────► Jan 24
  │                                                                   │
  ├── Quality Gates Enhancement (Jan 23)                              │
  │   ├── Recency filter for old articles                             │
  │   ├── URL date extraction                                         │
  │   ├── Wikipedia/old source filtering                              │
  │   └── Related sources for legal compliance                        │
  │                                                                   │
  └── Category Filtering (Jan 24)                                     │
      ├── Sports filter                                               │
      ├── Crime filter (local only)                                   │
      └── Category classification improvements                        │
```

---

## Key Achievements

### 1. Recency Filtering

**Problem:** Old articles being processed as new news.

**Solution:** Multi-layer date filtering:

**Key commit:** `144a14e - fix: Add recency filter to reject old articles as new news`

```python
# Layer 1: Publication date filter
def filter_old_articles(events: list[TriggerEvent]) -> list[TriggerEvent]:
    cutoff = datetime.utcnow() - timedelta(hours=24)
    return [e for e in events if e.detected_at > cutoff]

# Layer 2: Content date filter
def filter_past_references(events: list[TriggerEvent]) -> list[TriggerEvent]:
    """Filter events that reference past years (historical content)."""
    current_year = datetime.utcnow().year
    past_year_pattern = re.compile(r'\b(19|20)\d{2}\b')

    filtered = []
    for event in events:
        years = past_year_pattern.findall(event.content)
        if all(int(y) >= current_year - 1 for y in years):
            filtered.append(event)
    return filtered
```

### 2. URL Date Extraction

**Key commit:** `78b97a1 - fix: Extract publication date from URL to filter old articles`

Many news URLs contain publication dates that can be extracted:

```python
# URL patterns
PATTERNS = [
    r'/(\d{4})/(\d{2})/(\d{2})/',     # /2026/01/23/
    r'/(\d{4})-(\d{2})-(\d{2})/',     # /2026-01-23/
    r'/(\d{8})/',                      # /20260123/
    r'[?&]date=(\d{4}-\d{2}-\d{2})',  # ?date=2026-01-23
]

def extract_date_from_url(url: str) -> datetime | None:
    for pattern in PATTERNS:
        match = re.search(pattern, url)
        if match:
            return parse_date_groups(match.groups())
    return None
```

### 3. Evidence Source Filtering

**Key commit:** `d6fda6d - fix: Filter Wikipedia and old sources from evidence retrieval`

**Blocked sources:**
| Source Type | Reason |
|-------------|--------|
| Wikipedia | Not a primary source |
| Archive.org | Historical content |
| Web archives | May be outdated |
| PDF links | Often research papers, not news |

```python
BLOCKED_DOMAINS = [
    "wikipedia.org",
    "archive.org",
    "web.archive.org",
]

def filter_evidence_sources(evidence: list[Evidence]) -> list[Evidence]:
    return [e for e in evidence if not is_blocked_domain(e.url)]
```

### 4. Related Sources (Legal Compliance)

**Key commit:** `0f744b6 - feat: Add related sources section to articles for legal compliance`

Added attribution section to generated articles:

```python
class Article:
    title: str
    content: str
    related_sources: list[Source]  # New field

def generate_article(event: VerifiedEvent) -> Article:
    # ... article generation ...

    return Article(
        title=title,
        content=content,
        related_sources=[
            Source(
                name=s.name,
                url=s.url,
                accessed_at=datetime.utcnow()
            )
            for s in event.evidence_sources
        ]
    )
```

### 5. Category Filters

**Key commit:** `c7280eb - fix: Improve category classification and add sports/crime filters`

**Sports Filter:**
```python
SPORTS_KEYWORDS = [
    "world cup", "olympics", "championship",
    "tournament", "league", "match", "game",
    "scored", "goals", "points", "season"
]

def is_sports_content(text: str) -> bool:
    text_lower = text.lower()
    matches = sum(1 for kw in SPORTS_KEYWORDS if kw in text_lower)
    return matches >= 3
```

**Local Crime Filter:**
```python
# Only filter LOCAL crime, not international
def is_local_crime(event: TriggerEvent) -> bool:
    if not is_crime_content(event.content):
        return False

    # Allow international crime (terrorism, war crimes)
    if is_international_event(event):
        return False

    # Filter local crime
    return True
```

### 6. Category Classification Improvements

Enhanced zero-shot category detection:

```python
CATEGORY_LABELS = [
    "armed conflict or war",
    "terrorism or extremist attack",
    "political crisis or coup",
    "natural disaster",
    "humanitarian emergency",
    "diplomatic relations",
    "economic crisis",
    "nuclear or WMD incident",
]

def classify_category(text: str) -> tuple[str, float]:
    result = classifier(text, CATEGORY_LABELS)
    return result["labels"][0], result["scores"][0]
```

---

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Recency window | 24 hours | Balance freshness vs coverage |
| URL date extraction | Regex patterns | Fast, covers most formats |
| Wikipedia blocking | Hard block | Never a primary source |
| Sports filter | 3+ keyword threshold | Avoid false positives |
| Local crime filter | Geographic check | International crime is relevant |

---

## Filter Pipeline

```
Input Events (1000/day)
        ↓
[Recency Filter] ──────────────── Reject: >24h old
        ↓ (~800 remain)
[Content Date Filter] ─────────── Reject: Past year references
        ↓ (~700 remain)
[URL Date Filter] ─────────────── Reject: Old URL dates
        ↓ (~650 remain)
[Sports Filter] ───────────────── Reject: Sports content
        ↓ (~550 remain)
[Local Crime Filter] ──────────── Reject: Local crime only
        ↓ (~500 remain)
[Category Classification] ─────── Classify into 8 categories
        ↓
Filtered Events (500/day)
```

---

## Configuration

```python
# Recency settings
RECENCY_HOURS = 24
CONTENT_DATE_LOOKBACK_YEARS = 1

# Sports filter
SPORTS_KEYWORD_THRESHOLD = 3

# Category thresholds
CATEGORY_MIN_CONFIDENCE = 0.4
CATEGORY_UNKNOWN_THRESHOLD = 0.3
```

---

## Metrics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Old articles processed | ~15% | <1% | -93% |
| Sports content | ~10% | <1% | -90% |
| Local crime | ~8% | <1% | -88% |
| Category accuracy | ~70% | ~85% | +21% |

---

## Lessons Learned

1. **URL dates are reliable**: Most news sites include dates in URLs, providing a cheap first filter.

2. **Multi-layer filtering is robust**: Combining multiple date checks catches edge cases.

3. **Sports/crime dominate feeds**: Without filtering, ~20% of events were sports/local crime.

4. **Attribution builds trust**: Related sources section improves credibility and legal compliance.

5. **Category confidence matters**: Low-confidence classifications should be reviewed.

---

## Code References

| Component | File | Lines |
|-----------|------|-------|
| Recency filter | `app/agent/scanner.py` | 400-450 |
| URL date extraction | `app/agent/utils.py` | 100-150 |
| Evidence filter | `app/agent/evidence_retriever.py` | 200-250 |
| Category filter | `app/agent/scanner.py` | 550-600 |

---

## Related Documentation

- [Guide: Configuration](../guides/CONFIGURATION.md)
- [Concept: International Affairs](../concepts/INTERNATIONAL_AFFAIRS.md)

---

## Next Phase

[Phase 5: Optimization](PHASE_5_OPTIMIZATION.md) - Breaking news fast-path and P0/P1/P2 optimizations.
