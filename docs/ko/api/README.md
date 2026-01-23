# LiveMap API Reference

## Base URL
```
/api/v1
```

## Authentication
현재 API는 공개되어 있습니다. 보호된 엔드포인트를 위해 NextAuth를 통한 JWT 인증이 지원됩니다.

---

## Agent Endpoints

### POST /agent/scan
다중 소스 뉴스 스캔을 시작합니다.

**Description:**
설정된 모든 뉴스 소스(GDELT, Reddit 등)를 스캔하고 모든 필터링 게이트를 통과한 중요 이벤트를 반환합니다.

**Request Body:**
```json
{
  "sources": ["gdelt", "reddit"],  // Optional: 스캔할 특정 소스
  "keywords": ["Ukraine", "missile"]  // Optional: 키워드로 필터링
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
특정 주제에 대한 심층 조사를 시작합니다.

**Description:**
LangGraph 기반 조사 에이전트를 사용하여 종합적인 조사를 시작합니다. 이 과정에서 주장 추출, 검증 및 상세 보고서 생성이 수행됩니다.

**Request Body:**
```json
{
  "topic": "Iran attacks US bases in Iraq",
  "category": "military"  // Optional: 분류를 위한 힌트
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
조사 상태와 결과를 조회합니다.

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
헬스 체크 엔드포인트입니다.

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
스캐너 상태와 설정을 조회합니다.

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

모든 엔드포인트는 표준 에러 응답을 반환합니다:

```json
{
  "detail": "Error message here",
  "status_code": 400
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request - 잘못된 파라미터 |
| 404 | Not Found - 리소스가 존재하지 않음 |
| 422 | Validation Error - 요청 본문 검증 실패 |
| 500 | Internal Server Error |
| 503 | Service Unavailable - 외부 API 장애 |

---

## Rate Limiting

현재 Rate Limiting은 구현되어 있지 않습니다. 프로덕션 배포 시 다음 사항을 고려하세요:
- IP별 요청 속도 제한
- API 키 기반 할당량
- 스캔 엔드포인트에 대한 버스트 제한

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

사용 가능한 이벤트 카테고리:

| Category | Description |
|----------|-------------|
| war | 무력 충돌, 군사 작전 |
| conflict | 충돌, 적대 행위, 영토 분쟁 |
| politics | 선거, 정상회담, 정부 활동 |
| security | 사이버 공격, 첩보 활동, 위협 |
| military | 병력 이동, 무기, 국방 |
| terrorism | 테러 공격, 극단주의 활동 |
| diplomacy | 조약, 협상, 외교 행사 |
| natural_disaster | 지진, 기상 이변 |
| other | 미분류 이벤트 |
