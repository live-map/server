# Your First Scan Tutorial

This tutorial walks you through running your first news scan with LiveMap.

## Prerequisites

Before starting, ensure you have:
- Completed the [Getting Started](README.md) setup
- Server running at `http://localhost:8000`
- OpenAI API key configured

## Step 1: Start the Server

```bash
cd livemap/backend
uv run uvicorn app.main:app --reload
```

Verify the server is running:
```bash
curl http://localhost:8000/health
# Expected: {"status": "healthy"}
```

## Step 2: Trigger a Manual Scan

The scanner collects events from all enabled sources (GDELT, Reddit, etc.).

```bash
curl -X POST http://localhost:8000/api/v1/agent/scan \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Expected Response

```json
{
  "status": "success",
  "events_found": 109,
  "events_verified": 35,
  "events_publishable": 28,
  "scan_duration_seconds": 12.5
}
```

## Step 3: Understanding the Pipeline Output

The scan runs through 7 stages. Here's what the logs show:

### Stage 1: Collection
```
10:06:36 | INFO | USGS scan: 3 earthquakes found (M5.0+)
10:06:37 | INFO | GDELT scan: 50 articles found
10:06:38 | INFO | Reddit scan: 14 posts found
10:06:39 | INFO | Total events: 67, unique: 58
```

### Stage 2: Clustering
```
10:06:40 | INFO | New cluster detected: eb719719d08a (3 docs)
10:06:40 | INFO | New cluster detected: 3017d6e3fd2e (2 docs)
10:06:40 | INFO | Clustering complete: 39 clusters from 58 events
```

### Stage 3.5: Event Verification (Gate 0)
```
10:06:41 | INFO | [GATE0-REJECT] NOT_EVENT: pattern 'movie' matched
10:06:41 | INFO | [GATE0-PASS] ZERO_SHOT: military conflict (0.87)
10:06:42 | INFO | Event verification: 35/58 passed (39% passed)
```

### Stage 4: Confidence Scoring
```
10:06:43 | INFO | [CONFIDENCE] usgs: 0.74 (immediate_publish)
10:06:43 | INFO | [CONFIDENCE] gdelt: 0.70 (publishable)
10:06:43 | INFO | Confidence filter: 28 events passed (threshold=0.70)
```

## Step 4: View Scan Results

Get the list of publishable events:

```bash
curl http://localhost:8000/api/v1/agent/events
```

### Example Event Output

```json
{
  "events": [
    {
      "description": "M5.2 Earthquake - 120 km SSE of Sand Point, Alaska",
      "category": "natural_disaster",
      "sources": ["USGS"],
      "confidence_score": 0.74,
      "is_tier1_govt": true,
      "recommendation": "immediate_publish"
    },
    {
      "description": "Federal agents arrest 3 protesters at Minnesota church",
      "category": "protest",
      "sources": ["kunr.org"],
      "confidence_score": 0.70,
      "is_tier1_govt": false,
      "recommendation": "publishable"
    }
  ]
}
```

## Step 5: Start an Investigation

To generate an article for an event:

```bash
curl -X POST http://localhost:8000/api/v1/agent/investigate \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Federal agents arrest protesters at Minnesota church",
    "category": "protest"
  }'
```

### Expected Response

```json
{
  "status": "success",
  "investigation_id": "inv_abc123",
  "article_en": "Federal authorities arrested three individuals...",
  "article_ko": "연방 당국이 미네소타 교회에서...",
  "claims_verified": 5,
  "claims_refuted": 0,
  "overall_reliability": 0.85,
  "sources_used": ["kunr.org", "reuters.com", "apnews.com"]
}
```

## Step 6: Understanding Confidence Scores

| Score | Level | Meaning |
|-------|-------|---------|
| 0.90+ | Very High | Multiple Tier-1 sources |
| 0.70-0.89 | High | Publishable, verified |
| 0.50-0.69 | Medium | Needs more verification |
| < 0.50 | Low | Signal only, not published |

## Step 7: Configure Your Scan

Adjust settings in `.env`:

```bash
# Enable/disable sources
AGENT_GDELT_ENABLED=true
AGENT_REDDIT_ENABLED=true
AGENT_USGS_ENABLED=false  # Disable earthquake monitoring

# Adjust thresholds
AGENT_MIN_CONFIDENCE_SCORE=0.70  # Publication threshold

# Filter settings
AGENT_EVENT_VERIFICATION_ENABLED=true
AGENT_EVENT_VERIFICATION_USE_ZERO_SHOT=true
```

## Troubleshooting

### No Events Found

1. Check if sources are enabled:
```bash
cat .env | grep ENABLED
```

2. Verify GDELT is accessible:
```bash
curl "https://api.gdeltproject.org/api/v2/doc/doc?query=war&mode=artlist&maxrecords=10"
```

3. Lower confidence threshold for testing:
```bash
AGENT_MIN_CONFIDENCE_SCORE=0.50
```

### All Events Filtered by Gate 0

Check what's being filtered:
```bash
AGENT_LOG_GATE_REJECTIONS=true
```

Look for patterns in logs:
```
[GATE0-REJECT] NOT_EVENT: pattern 'game' matched
```

If legitimate events are being filtered, review patterns in `app/agent/event_verifier.py`.

### LLM Errors

Ensure your API key is valid:
```bash
echo $OPENAI_API_KEY
```

Check timeout settings:
```bash
AGENT_LLM_TIMEOUT_SECONDS=60
```

## Next Steps

- [Configure additional sources](../guides/CONFIGURATION.md)
- [Understand confidence scoring](../concepts/CONFIDENCE_SCORING.md)
- [Add custom triggers](../guides/TRIGGER_GUIDE.md)
- [Review API reference](../api/README.md)

---

*Related documents:*
- [Getting Started](README.md)
- [Scanner Pipeline](../architecture/SCANNER_PIPELINE.md)
- [Event Verification](../architecture/EVENT_VERIFICATION.md)
