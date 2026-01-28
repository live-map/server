# Configuration Reference

Complete reference for all LiveMap backend configuration options.

## Environment Variables

All agent settings use the `AGENT_` prefix.

### LLM Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AGENT_OPENAI_API_KEY` | str | "" | OpenAI API key (required for LLM features) |
| `AGENT_LLM_MODEL` | str | "gpt-4o-mini" | LLM model for verification/generation |
| `AGENT_LLM_TEMPERATURE` | float | 0.3 | LLM temperature (0=deterministic, 1=creative) |
| `AGENT_TAVILY_API_KEY` | str | "" | Tavily API key for web search |

### Trigger Source Settings

#### Tier-1 Sources

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AGENT_GDELT_ENABLED` | bool | true | Enable GDELT news source |
| `AGENT_GDELT_TIMESPAN` | str | "2h" | GDELT search timespan |
| `AGENT_GDELT_ANOMALY_ENABLED` | bool | true | Enable GDELT anomaly detection |
| `AGENT_GDELT_USE_GKG_THEMES` | bool | true | Use GKG themes for anomaly |
| `AGENT_GDELT_TONE_THRESHOLD` | float | -5.0 | Goldstein tone threshold |
| `AGENT_USGS_ENABLED` | bool | false | Enable USGS earthquake source |
| `AGENT_USGS_MIN_MAGNITUDE` | float | 5.0 | Minimum earthquake magnitude |
| `AGENT_NOAA_ENABLED` | bool | false | Enable NOAA weather alerts |
| `AGENT_NOAA_SEVERITY` | str | "Extreme,Severe" | Weather alert severities |

#### Tier-2 Sources

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AGENT_CURRENTS_ENABLED` | bool | false | Enable Currents API |
| `AGENT_CURRENTS_API_KEY` | str | "" | Currents API key |
| `AGENT_WORLDNEWS_ENABLED` | bool | false | Enable World News API |
| `AGENT_WORLDNEWS_API_KEY` | str | "" | World News API key |
| `AGENT_ACLED_ENABLED` | bool | false | Enable ACLED conflict data |
| `AGENT_ACLED_API_KEY` | str | "" | ACLED API key |
| `AGENT_ACLED_EMAIL` | str | "" | ACLED registered email |

#### Tier-3 Sources

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AGENT_REDDIT_ENABLED` | bool | true | Enable Reddit source |
| `AGENT_REDDIT_SUBREDDITS` | str | "worldnews,news,..." | Comma-separated subreddits |
| `AGENT_REDDIT_MIN_SCORE` | int | 50 | Minimum post score |
| `AGENT_BLUESKY_ENABLED` | bool | false | Enable Bluesky source |
| `AGENT_BLUESKY_MIN_LIKES` | int | 10 | Minimum likes |
| `AGENT_GOOGLE_TRENDS_ENABLED` | bool | false | Enable Google Trends |
| `AGENT_GOOGLE_TRENDS_GEO` | str | "US" | Trends geography |
| `AGENT_TWITTER_ENABLED` | bool | false | Enable X/Twitter |
| `AGENT_TWITTER_USERNAME` | str | "" | Twitter username |
| `AGENT_TWITTER_EMAIL` | str | "" | Twitter email |
| `AGENT_TWITTER_PASSWORD` | str | "" | Twitter password |
| `AGENT_TELEGRAM_ENABLED` | bool | false | Enable Telegram |
| `AGENT_TELEGRAM_API_ID` | str | "" | Telegram API ID |
| `AGENT_TELEGRAM_API_HASH` | str | "" | Telegram API hash |
| `AGENT_TELEGRAM_PHONE` | str | "" | Telegram phone number |
| `AGENT_TELEGRAM_CHANNELS` | str | "" | Comma-separated channels |

### Confidence Scoring

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AGENT_MIN_CONFIDENCE_SCORE` | float | 0.70 | Minimum score for publication |
| `AGENT_CROSS_SOURCE_SIMILARITY_THRESHOLD` | float | 0.70 | Similarity for cross-source matching |

### Scanner Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AGENT_SCAN_INTERVAL_MINUTES` | int | 15 | Scan frequency |
| `AGENT_MAX_NEWS_PER_SCAN` | int | 100 | Max events per scan |
| `AGENT_MAX_EVENTS_PER_CATEGORY` | int | 5 | Category limit |
| `AGENT_ENSURE_CATEGORY_DIVERSITY` | bool | true | Enable diversity interleaving |
| `AGENT_RECENCY_FILTER_ENABLED` | bool | **false** | Recency filter (disabled - triggers handle it) |
| `AGENT_MAX_EVENT_AGE_HOURS` | int | 6 | Max event age (fallback) |

### LLM Classifier Settings (Phase 6)

> Replaces Gate 0-2 pattern-based filtering with LLM classification.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AGENT_LLM_CLASSIFIER_ENABLED` | bool | true | Enable LLM classifier |
| `AGENT_DEEPINFRA_API_KEY` | str | "" | Deepinfra API key |
| `AGENT_DEEPINFRA_BASE_URL` | str | "https://api.deepinfra.com/v1/openai" | API endpoint |
| `AGENT_LLM_CLASSIFIER_MODEL` | str | "meta-llama/Meta-Llama-3.1-8B-Instruct" | Model |
| `AGENT_LLM_CLASSIFIER_BATCH_SIZE` | int | 20 | Batch size |
| `AGENT_LLM_CLASSIFIER_TIMEOUT` | float | 30.0 | Timeout (seconds) |
| `AGENT_LLM_CLASSIFIER_FALLBACK_ENABLED` | bool | true | Enable pattern fallback |
| `AGENT_DEDUP_BEFORE_LLM` | bool | true | Title dedup before LLM (cost savings) |

### Temporal Classification Settings (Phase 6.1)

> Automatically filters retrospective/analysis articles and predictions.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AGENT_TEMPORAL_CLASSIFICATION_ENABLED` | bool | true | Enable temporal classification |
| `AGENT_TEMPORAL_FILTER_ENABLED` | bool | true | Auto-reject non-publishable categories |
| `AGENT_TEMPORAL_REJECT_CATEGORIES` | str | "retrospective,predictive" | Categories to reject |
| `AGENT_TEMPORAL_LOG_CLASSIFICATIONS` | bool | true | Log classification results |

**Temporal Classification Categories**:

| Category | Time Range | Publish | Example |
|----------|-----------|---------|---------|
| `breaking` | Within 24h | ✅ Yes | "Russia launches offensive" |
| `developing` | 1-7 days | ✅ Yes | "Day 5 of peace talks" |
| `retrospective` | Past analysis | ❌ No | "Three years of war: Analysis" |
| `predictive` | Future prediction | ❌ No | "What 2027 elections could mean" |
| `timeless` | Timeless | ⚠️ Evaluate | "How sanctions work: Explainer" |

### Domain Whitelist Settings (Phase 6)

> Allow only Tier-1/2 domains to reduce noise.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AGENT_DOMAIN_WHITELIST_ENABLED` | bool | true | Enable whitelist |
| `AGENT_TRUSTED_DOMAINS` | str | "reuters.com,apnews.com,..." | Trusted domains (59) |

### International Affairs Focus

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AGENT_FOCUS_INTERNATIONAL_AFFAIRS` | bool | true | Focus on international categories |
| `AGENT_INTERNATIONAL_AFFAIRS_CATEGORIES` | str | "war,conflict,politics,..." | Allowed categories |

### Significance Scoring

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AGENT_MIN_PUBLISH_SCORE` | int | 40 | Minimum significance score |
| `AGENT_MIN_INVESTIGATE_SCORE` | int | 50 | Score to trigger investigation |
| `AGENT_USE_DETERMINISTIC_SCORING` | bool | true | Use rule-based scoring |
| `AGENT_USE_LLM_SCORING` | bool | true | Use LLM scoring |
| `AGENT_COMBINE_SCORES` | bool | true | Combine both scores |
| `AGENT_LOG_ALL_SCORES` | bool | true | Log all score calculations |

### Content Filtering Gates

#### Gate 0: Event Verification (3-Stage Hybrid)

See [Zero-shot Classification](../architecture/ZERO_SHOT_CLASSIFIER.md) and [Event Verification](../architecture/EVENT_VERIFICATION.md) for details.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AGENT_EVENT_VERIFICATION_ENABLED` | bool | true | Enable Gate 0 (all stages) |
| `AGENT_EVENT_VERIFICATION_USE_ZERO_SHOT` | bool | true | Stage 2: Zero-shot classification |
| `AGENT_EVENT_VERIFICATION_USE_LLM` | bool | true | Stage 3: LLM verification |

#### Gate 1-3: Content Quality

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AGENT_CHECKWORTHINESS_ENABLED` | bool | true | Enable Gate 1 |
| `AGENT_ENTERTAINMENT_PATTERN_THRESHOLD` | int | 2 | Entertainment pattern count |
| `AGENT_SPECULATION_PATTERN_THRESHOLD` | int | 2 | Speculation pattern count |
| `AGENT_HUMAN_INTEREST_PATTERN_THRESHOLD` | int | 3 | Human interest pattern count |
| `AGENT_SPECIFICITY_ENABLED` | bool | true | Enable Gate 2 |
| `AGENT_MIN_SPECIFICITY_SCORE` | float | 0.4 | Minimum specificity (0-1) |
| `AGENT_EVIDENCE_GATE_ENABLED` | bool | true | Enable Gate 3 |
| `AGENT_MIN_SUPPORTED_CLAIMS` | int | 1 | Minimum verified claims |
| `AGENT_MIN_EVIDENCE_RATIO` | float | 0.3 | Minimum evidence ratio |
| `AGENT_LOG_GATE_REJECTIONS` | bool | true | Log rejection reasons |

### Deduplication

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AGENT_DEDUP_ENABLED` | bool | true | Enable deduplication |
| `AGENT_DEDUP_DUPLICATE_THRESHOLD` | float | 0.95 | Exact duplicate threshold |
| `AGENT_DEDUP_POTENTIAL_THRESHOLD` | float | 0.85 | Potential match threshold |
| `AGENT_DEDUP_RELATED_THRESHOLD` | float | 0.70 | Related event threshold |
| `AGENT_DEDUP_TIME_WINDOW_DAYS` | int | 7 | Lookup time window |
| `AGENT_DEDUP_LOG_ALL_SIMILARITIES` | bool | true | Log similarity scores |

### Bilingual Generation

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AGENT_GENERATE_KOREAN` | bool | true | Generate Korean articles |
| `AGENT_KOREAN_STYLE` | str | "formal" | Korean style (formal/informal) |

### Timeouts

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AGENT_LLM_TIMEOUT_SECONDS` | float | 60.0 | LLM call timeout |
| `AGENT_MAX_CONCURRENT_LLM_CALLS` | int | 3 | Max parallel LLM calls |
| `AGENT_INVESTIGATION_TIMEOUT_SECONDS` | float | 300.0 | Investigation timeout |

## Example .env File

```bash
# Required
OPENAI_API_KEY=sk-...

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/livemap

# Agent Configuration
AGENT_GDELT_ENABLED=true
AGENT_GDELT_TIMESPAN=30min
AGENT_REDDIT_ENABLED=false  # Phase 6: Tier-3 disabled
AGENT_MIN_CONFIDENCE_SCORE=0.70
AGENT_SCAN_INTERVAL_MINUTES=15
AGENT_FOCUS_INTERNATIONAL_AFFAIRS=true

# Phase 6: LLM Classifier (Replaces Gate 0-2)
AGENT_LLM_CLASSIFIER_ENABLED=true
AGENT_DEEPINFRA_API_KEY=your_deepinfra_key_here
AGENT_LLM_CLASSIFIER_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
AGENT_DEDUP_BEFORE_LLM=true

# Phase 6.1: Temporal Classification
AGENT_TEMPORAL_CLASSIFICATION_ENABLED=true
AGENT_TEMPORAL_FILTER_ENABLED=true

# Phase 6: Domain Whitelist
AGENT_DOMAIN_WHITELIST_ENABLED=true

# Phase 6: Recency Filter Disabled (triggers handle it)
AGENT_RECENCY_FILTER_ENABLED=false

# Optional: Additional sources
AGENT_CURRENTS_ENABLED=false
AGENT_CURRENTS_API_KEY=
AGENT_WORLDNEWS_ENABLED=false
AGENT_WORLDNEWS_API_KEY=

# Logging
AGENT_LOG_GATE_REJECTIONS=true
AGENT_DEDUP_LOG_ALL_SIMILARITIES=true
```

### Legacy Configuration (Pre-Phase 6)

To use pattern-based Gate system:

```bash
# Disable LLM classifier → Pattern fallback
AGENT_LLM_CLASSIFIER_ENABLED=false
AGENT_EVENT_VERIFICATION_ENABLED=true
AGENT_EVENT_VERIFICATION_USE_ZERO_SHOT=true
AGENT_EVENT_VERIFICATION_USE_LLM=true
```

## Configuration in Code

```python
from app.agent.config import agent_settings

# Access settings
if agent_settings.gdelt_enabled:
    manager.add_gdelt(timespan=agent_settings.gdelt_timespan)

# Check threshold
if confidence >= agent_settings.min_confidence_score:
    publish(event)
```

## Runtime Configuration

Some settings can be overridden at runtime:

```python
# Custom confidence scorer
scorer = MultiSourceConfidenceScorer(
    min_publish_confidence=0.60  # Override default 0.70
)

# Custom cross-source matcher
matcher = CrossSourceMatcher(
    similarity_threshold=0.80,  # Override default 0.70
    time_window_hours=12  # Override default 6
)
```
