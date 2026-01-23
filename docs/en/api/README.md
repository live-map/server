# LiveMap API Reference

## Base URL
```
/api/v1
```

## Authentication
Currently, the API is open. JWT authentication support via NextAuth is available for protected endpoints.

---

## Agent Endpoints

### POST /agent/scan
Trigger a multi-source news scan.

**Description:**
Initiates a scan across all configured news sources (GDELT, Reddit, etc.) and returns significant events that pass all filtering gates.

**Request Body:**
```json
{
  "sources": ["gdelt", "reddit"],  // Optional: specific sources to scan
  "keywords": ["Ukraine", "missile"]  // Optional: filter by keywords
}
```

**Response:**
```json
{
  "status": "success",
  "events": [
    {
      "description": "Russian forces launch missile strike on Kyiv",
      "category": "war",
      "sources": ["reuters.com", "r/worldnews"],
      "source_count": 2,
      "trigger_source": "gdelt",
      "keywords": ["missile", "strike", "Kyiv"],
      "url": "https://reuters.com/article/...",
      "confidence_score": 0.785,
      "confidence_level": "high",
      "two_source_satisfied": true,
      "recommendation": "publishable",
      "is_tier1_govt": false
    }
  ],
  "scan_time": "2024-01-20T10:30:00Z"
}
```

**Example (curl):**
```bash
curl -X POST http://localhost:8000/api/v1/agent/scan \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Example (Python):**
```python
import httpx

async def trigger_scan():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/agent/scan",
            json={}
        )
        return response.json()
```

---

### POST /agent/investigate
Start a deep investigation into a specific topic.

**Description:**
Initiates a comprehensive investigation using the LangGraph-based investigator agent. This performs claim extraction, verification, and generates a detailed report.

**Request Body:**
```json
{
  "topic": "Iran attacks US bases in Iraq",
  "category": "military"  // Optional: hint for categorization
}
```

**Response:**
```json
{
  "status": "started",
  "investigation_id": "550e8400-e29b-41d4-a716-446655440000",
  "topic": "Iran attacks US bases in Iraq",
  "estimated_duration": "2-5 minutes"
}
```

**Example (curl):**
```bash
curl -X POST http://localhost:8000/api/v1/agent/investigate \
  -H "Content-Type: application/json" \
  -d '{"topic": "Iran attacks US bases in Iraq"}'
```

---

### GET /agent/investigation/{investigation_id}
Get investigation status and results.

**Response (in progress):**
```json
{
  "status": "in_progress",
  "investigation_id": "550e8400-e29b-41d4-a716-446655440000",
  "topic": "Iran attacks US bases in Iraq",
  "progress": {
    "stage": "claim_verification",
    "claims_verified": 3,
    "claims_total": 5
  }
}
```

**Response (completed):**
```json
{
  "status": "completed",
  "investigation_id": "550e8400-e29b-41d4-a716-446655440000",
  "topic": "Iran attacks US bases in Iraq",
  "result": {
    "summary": "Confirmed: Iranian-backed forces attacked US bases...",
    "claims": [
      {
        "claim": "3 US soldiers were injured",
        "verdict": "SUPPORTED",
        "evidence": ["Pentagon statement", "Local reports"]
      }
    ],
    "confidence": 0.85,
    "sources_used": 7
  }
}
```

---

## Status Endpoints

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-20T10:30:00Z",
  "version": "1.0.0"
}
```

---

### GET /agent/status
Get scanner status and configuration.

**Response:**
```json
{
  "last_scan": "2024-01-20T10:15:00Z",
  "triggers": {
    "gdelt": {"status": "active", "last_scan": "2024-01-20T10:15:00Z"},
    "reddit": {"status": "active", "last_scan": "2024-01-20T10:15:00Z"}
  },
  "configuration": {
    "scan_interval_minutes": 15,
    "min_confidence_score": 0.70,
    "event_verification_enabled": true
  }
}
```

---

## Error Responses

All endpoints return standard error responses:

```json
{
  "detail": "Error message here",
  "status_code": 400
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid parameters |
| 404 | Not Found - Resource doesn't exist |
| 422 | Validation Error - Request body validation failed |
| 500 | Internal Server Error |
| 503 | Service Unavailable - External API failure |

---

## Rate Limiting

Currently no rate limiting is implemented. For production deployments, consider:
- Request rate limiting per IP
- API key-based quotas
- Burst limiting for scan endpoints

---

## Confidence Score Reference

| Score Range | Level | Recommendation |
|-------------|-------|----------------|
| 0.85 - 0.99 | very_high | immediate_publish |
| 0.70 - 0.84 | high | publishable |
| 0.50 - 0.69 | medium | review_required |
| 0.00 - 0.49 | low | do_not_publish |

---

## Source Tiers

| Tier | Sources | Weight |
|------|---------|--------|
| tier1_govt | USGS, NOAA | 0.99 |
| tier1_news | GDELT | 0.90 |
| tier2_data | ACLED | 0.85 |
| tier2_news | Currents, WorldNews | 0.75 |
| tier3_social | Reddit, Twitter, Bluesky | 0.40 |
| tier3_msg | Telegram | 0.35 |
| tier3_trend | Google Trends | 0.30 |

---

## Categories

Available event categories:

| Category | Description |
|----------|-------------|
| war | Armed conflicts, military operations |
| conflict | Clashes, hostilities, territorial disputes |
| politics | Elections, summits, government actions |
| security | Cyber attacks, espionage, threats |
| military | Troop movements, weapons, defense |
| terrorism | Terror attacks, extremist activities |
| diplomacy | Treaties, negotiations, diplomatic events |
| natural_disaster | Earthquakes, weather events |
| other | Uncategorized events |
