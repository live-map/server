# Event Verification System (Gate 0)

## 1. Problem Definition

### Limitations of Keyword Matching

The current system collects content through keyword matching:

```python
keywords = ["war", "missile", "invasion", "airstrike", "protest", ...]
```

**Problem**: Content that contains keywords but is not an actual event is still collected.

### False Positive Examples

| Collected Content | Keyword | Is Real Event? |
|--------------|--------|----------|
| "Iran attacks US bases in Iraq" | attack | O Real event |
| "New war movie 'Invasion' releases" | war, invasion | X Movie |
| "Call of Duty: Modern Warfare review" | war | X Game |
| "In 1945, the war ended..." | war | X History |
| "If Russia invades, NATO might..." | invasion, might | X Speculation |
| "World Cup final: epic battle" | battle | X Sports |

### Impact

- **Resource waste**: LLM costs consumed on movie/game articles
- **Quality degradation**: Real news gets pushed back in the queue
- **Reliability decline**: Risk of publishing incorrect articles

---

## 2. 3-Stage Hybrid Solution

### Overview

```
Collected events (168)
    ↓
[Stage 1: Rule-based filter] - $0, ~1ms
- NOT_EVENT_PATTERNS matching
- Multilingual sports patterns (Korean/Arabic/Chinese)
    ↓ (~50 pass, 70% removed)
[Stage 2: Zero-shot classification] - $0, ~50ms
- BART-large-MNLI local model
- Confidence ≥ 0.8 → immediate decision
- Confidence < 0.8 → forward to Stage 3
    ↓ (~40 pass or forwarded to LLM)
[Stage 3: LLM verification] - $0.001/item, ~300ms
- Handles only edge cases
- PASS/REJECT + REASON
    ↓
Verified events (~35)
```

### 2.1 Stage 1: Rule-based Filter

**Purpose**: Quickly remove 70% through clear pattern matching

#### NOT_EVENT_PATTERNS List

```python
NOT_EVENT_PATTERNS = [
    # Entertainment
    r"\b(movie|film|tv show|series|drama|actor|actress|celebrity)\b",
    r"\b(box office|premiere|trailer|sequel|franchise|streaming)\b",
    r"\b(grammy|oscar|emmy|golden globe|award show)\b",

    # Gaming
    r"\b(video game|gaming|esports|playstation|xbox|nintendo|steam)\b",
    r"\b(call of duty|battlefield|fortnite|minecraft|league of legends)\b",
    r"\b(game update|patch notes|dlc|expansion pack)\b",

    # History/Past
    r"\b(in \d{4}|years ago|historically|last century|decades ago)\b",
    r"\b(world war (i|ii|1|2)|civil war|cold war)\s+(?!fears|concerns|tensions)",
    r"\b(anniversary of|commemorat|memorial)\b",

    # Speculation/Hypotheticals
    r"\b(if .* would|could potentially|might happen|hypothetically)\b",
    r"\bif .* (might|could|may) ",
    r"\b(what if|scenario|simulation|thought experiment)\b",
    r"\b(prediction|forecast|speculation)\b",

    # Reviews/Opinions/Analysis
    r"\b(review|opinion|editorial|commentary)\b",
    r"\b(my thoughts on|i think|in my opinion)\b",
    r"\bwhy \S{1,50} (is|are|isn't|not)\b",
    r"\bhow \S{1,50} (can|could|should|will)\b",
    r"\bwhat \S{1,50} (means|tells|shows)\b",
    r"\b(explained|breakdown|deep dive|explainer)\b",

    # Sports (English)
    r"\b(football|soccer|basketball|baseball|tennis|golf|cricket|rugby)\b",
    r"\b(olympics|world cup|championship|tournament|league|playoffs)\b",
    r"\b(match|game score|win|lose|defeat|victory)\s+(?!military|war)",
    r"\b(nba|nfl|mlb|nhl|fifa|uefa)\b",

    # Sports (Multilingual - Korean)
    r"(레알 마드리드|바르셀로나|맨체스터|리버풀|첼시|아스널|토트넘)",
    r"(손흥민|황희찬|이강인|김민재)",
    r"(프리미어리그|라리가|분데스리가|세리에A|K리그)",

    # Sports (Multilingual - Arabic)
    r"(ريال مدريد|برشلونة|مانشستر|ليفربول)",

    # Sports (Multilingual - Chinese)
    r"(皇马|巴萨|曼联|利物浦|拜仁|切尔西)",

    # Ads/Promotions
    r"\b(sale|discount|buy now|limited time|sponsored|ad)\b",
    r"\b(promo code|coupon|offer expires|flash sale|limited offer)\b",

    # Fiction/Novels
    r"\b(novel|fiction|story|tale|book review)\b",
    r"\b(chapter|episode|season \d+)\b",
]
```

#### Filtering Logic

```python
def is_likely_real_event(text: str) -> tuple[bool, str | None]:
    """
    Rule-based primary filter

    Returns:
        (pass status, rejection reason)
    """
    text_lower = text.lower()

    for pattern in COMPILED_PATTERNS:
        match = pattern.search(text_lower)
        if match:
            return False, f"NOT_EVENT: pattern matched '{match.group()}'"

    return True, None
```

### 2.2 Stage 2: Zero-shot Classification

**Purpose**: Classify with local model after rule filter, before LLM call

#### Model: facebook/bart-large-mnli

- Provides **Zero-shot classification** capability
- Runs locally (API cost $0)
- Processing time: ~50ms/item

#### Classification Labels (CAMEO/ACLED-based)

```python
# International affairs labels (pass)
INTERNATIONAL_AFFAIRS_LABELS = [
    "military conflict",
    "diplomatic relations",
    "political crisis",
    "terrorism",
    "humanitarian crisis",
    "international sanctions",
    "protest and civil unrest",
]

# Non-international affairs labels (reject)
REJECT_LABELS = [
    "sports",
    "entertainment",
    "local news",
    "opinion and analysis",
    "advertisement",
]
```

#### Confidence Thresholds

```python
ZERO_SHOT_HIGH_CONFIDENCE = 0.8  # Above this, decide immediately
ZERO_SHOT_LOW_CONFIDENCE = 0.5   # Below this, LLM verification
```

| Confidence | Action |
|--------|------|
| ≥ 0.8 | Immediate decision (PASS or REJECT) |
| 0.5-0.8 | Forward to LLM |
| < 0.5 | Forward to LLM |

### 2.3 Stage 3: LLM Verification

**Purpose**: Precisely verify only edge cases where Zero-shot is uncertain

#### Prompt Design (PASS/REJECT Format)

```python
EVENT_VERIFY_PROMPT = """Today's date: {today}

## Task
Determine if this text reports an INTERNATIONAL AFFAIRS event.

## Definition
International affairs = events involving 2+ countries OR global security implications.

## Classification

PASS if ANY of these:
- Military conflict between nations
- Diplomatic meeting/negotiation between countries
- International sanctions, treaties, agreements
- UN/NATO/international organization actions
- Cross-border humanitarian crisis
- Terrorism with international implications
- Protests with international significance

REJECT if ANY of these:
- Single country domestic politics
- Sports (any language)
- Entertainment, celebrities
- Opinion/analysis articles
- Local crime, accidents

## Input
Text: {text}

## Output (exactly this format)
VERDICT: PASS or REJECT
REASON: brief explanation"""
```

#### Decision Criteria

| Criteria | PASS | REJECT |
|------|------|--------|
| Scope | Involves 2+ countries | Single country domestic issue |
| Tense | Current/recent | Past/hypothetical future |
| Context | Real world | Virtual world (movies, games) |
| Source | News article citation | Personal opinion, review |

### 2.4 Cost Efficiency (3-Stage Pipeline)

| Stage | Throughput | Cost | Time |
|------|--------|------|------|
| Stage 1 (Rules) | 168 → 50 (70% removed) | $0 | ~1ms |
| Stage 2 (Zero-shot) | 50 → 15 forwarded to LLM (70% decided) | $0 | ~50ms |
| Stage 3 (LLM) | 15 → 10 pass | $0.015/scan | ~300ms |
| **Total Cost** | | **$1.44/day** | |

**Comparison (LLM-only approach)**:
- 168 × $0.001 = $0.168/scan
- $16.13/day (11x cost savings!)

---

## 3. Implementation Details

### 3.1 event_verifier.py Structure

```python
"""
Event Verifier - 3-stage hybrid approach
Stage 1: Rule-based filter (70% removal, $0)
Stage 2: Zero-shot classification (local model, decides if high confidence)
Stage 3: LLM-based verification (edge cases only, $0.001/item)
"""

async def verify_event_hybrid(
    text: str,
    llm: "ChatOpenAI | None" = None,
    use_llm: bool = True,
    use_zero_shot: bool = True
) -> tuple[bool, str]:
    """
    Hybrid event verification (3 stages)
    """
    # Stage 1: Rule-based filter
    passed_rules, rejection_reason = is_likely_real_event(text)
    if not passed_rules:
        return False, rejection_reason

    # Stage 2: Zero-shot classification (optional)
    if use_zero_shot:
        is_intl, confidence, label = classify_with_zero_shot(text)
        if is_intl is not None and confidence >= ZERO_SHOT_HIGH_CONFIDENCE:
            if is_intl:
                return True, f"ZERO_SHOT: {label} ({confidence:.2f})"
            else:
                return False, f"ZERO_SHOT_REJECT: {label} ({confidence:.2f})"

    # Stage 3: LLM verification (only for uncertain cases)
    if use_llm and llm:
        return await verify_event_with_llm(text, llm)

    return True, "PASSED_RULES_ONLY"
```

### 3.2 scanner.py Gate 0 Integration

```python
# Inside _classify_and_group() method

# Step 3.5: Event verification (Gate 0)
if agent_settings.event_verification_enabled:
    verified_events = []

    for item in publishable_events:
        event = item["event"]
        text = f"{event.title} {event.content[:300]}"

        is_event, reason = await verify_event_hybrid(
            text,
            self.llm if agent_settings.event_verification_use_llm else None,
            use_llm=agent_settings.event_verification_use_llm,
            use_zero_shot=agent_settings.event_verification_use_zero_shot
        )

        if is_event:
            verified_events.append(item)
        else:
            logger.info(f"[GATE0-REJECT] {reason}: {event.title[:50]}...")

    publishable_events = verified_events
```

### 3.3 config.py Settings

```python
class AgentSettings(BaseSettings):
    # Event verification settings
    event_verification_enabled: bool = True
    event_verification_use_llm: bool = True
    event_verification_use_zero_shot: bool = True  # Enable Zero-shot classification
```

---

## 4. Test Cases

### Cases That Should Pass (PASS)

| Input | Expected Result | Reason |
|------|----------|------|
| "Iran attacks US bases in Iraq, 3 soldiers injured" | PASS | Actual military event |
| "North Korea fires ballistic missile toward Sea of Japan" | PASS | Actual missile launch |
| "Protesters clash with police in Paris over pension reform" | PASS | International protest |
| "Putin and Xi meet in Beijing for summit talks" | PASS | Actual summit meeting |
| "TikTok deal between China and White House finalized" | PASS | US-China trade/tech negotiation |
| "Anti-ICE protest erupts at federal building" | PASS | Protest event |

### Cases That Should Be Rejected (REJECT)

| Input | Expected Result | Processing Stage |
|------|----------|----------|
| "New war movie 'Invasion' releases this Friday" | REJECT | Stage 1 (movie pattern) |
| "Call of Duty: Modern Warfare gets new update" | REJECT | Stage 1 (game pattern) |
| "In 1945, World War II ended with Japan's surrender" | REJECT | Stage 1 (history pattern) |
| "If Russia invades, NATO might respond with..." | REJECT | Stage 1 (speculation pattern) |
| "World Cup final: France defeats Argentina" | REJECT | Stage 1 (sports pattern) |
| "Son Heung-min scores hat-trick for Tottenham" | REJECT | Stage 1 (Korean sports) |
| "Why the Ukraine war is changing global politics" | REJECT | Stage 1 (analysis article) |

### Edge Cases (Processed in Stage 2 or 3)

| Input | Expected Result | Processing Stage |
|------|----------|----------|
| "Olympics security breach: intruder arrested" | PASS | Stage 2/3 (LLM) |
| "Game-changing sanctions imposed on Russia" | PASS | Stage 2/3 (LLM) |
| "World War III fears grow as tensions rise" | PASS | Stage 2/3 (LLM) |

---

## 5. Log Output Examples

```
10:06:47 | INFO | [GATE0-RULES] Rejected: NOT_EVENT: pattern 'movie' matched
10:06:47 | INFO | [GATE0-RULES] Rejected: NOT_EVENT: pattern 'game' matched
10:06:47 | INFO | [GATE0-ZEROSHOT] Passed: military conflict (0.87)
10:06:48 | INFO | [GATE0-ZEROSHOT] Rejected: sports (0.92)
10:06:48 | INFO | [GATE0-ZEROSHOT] Uncertain: protest and civil unrest (0.65), forwarding to LLM
10:06:49 | INFO | [GATE0-LLM] Passed: International protest with diplomatic implications
10:06:49 | INFO | Event verification: 35/168 passed (79% filtered)
```

---

## 6. Performance Metrics

| Metric | Target | Stage 1 | Stage 2 | Stage 3 |
|------|------|---------|---------|---------|
| Latency | < 500ms | ~1ms | ~50ms | ~300ms |
| Cost/event | Minimize | $0 | $0 | $0.001 |
| Accuracy | > 90% | ~85% | ~90% | ~95% |
| Filter Rate | Higher is better | ~70% | ~70% of remaining | ~10% |

### Overall Pipeline

| Metric | Target | Current |
|------|------|------|
| True Positive Rate | > 95% | Needs measurement |
| False Positive Rate | < 5% | Needs measurement |
| Total Processing Time | < 500ms | ~350ms |
| LLM Cost Savings | > 80% | ~90% |

---

## 7. Error Handling

### Stage-wise Graceful Degradation

```python
# Stage 2 failure → Stage 3 (Zero-shot model loading failure)
try:
    from app.agent.zero_shot_classifier import get_zero_shot_classifier
    classifier = get_zero_shot_classifier()
except ImportError:
    logger.warning("Zero-shot classifier not available, skipping")
    # Forward directly to LLM

# Stage 3 failure → Reject (conservative approach)
except Exception as e:
    logger.error(f"LLM verification error: {e}")
    return False, f"LLM_ERROR: verification failed"
```

---

## Change History

| Date | Changes |
|------|----------|
| 2025-01-23 | Initial document creation (2-stage pipeline) |
| 2025-01-23 | Updated to 3-stage pipeline (Zero-shot added) |

---

*Related documents:*
- [ADR-004: Hybrid Event Verification](./adr/ADR-004-hybrid-verification.md)
- [Zero-shot Classification](./ZERO_SHOT_CLASSIFIER.md)
