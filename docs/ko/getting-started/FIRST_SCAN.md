# Your First Scan Tutorial

이 튜토리얼은 LiveMap으로 첫 번째 뉴스 스캔을 실행하는 과정을 안내합니다.

## 사전 요구사항

시작하기 전에 다음을 확인하세요:
- [Getting Started](README.md) 설정 완료
- 서버가 `http://localhost:8000`에서 실행 중
- OpenAI API 키 설정 완료

## Step 1: 서버 시작

```bash
cd livemap/backend
uv run uvicorn app.main:app --reload
```

서버가 실행 중인지 확인:
```bash
curl http://localhost:8000/health
# 예상: {"status": "healthy"}
```

## Step 2: 수동 스캔 트리거

스캐너는 활성화된 모든 소스(GDELT, Reddit 등)에서 이벤트를 수집합니다.

```bash
curl -X POST http://localhost:8000/api/v1/agent/scan \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 예상 응답

```json
{
  "status": "success",
  "events_found": 109,
  "events_verified": 35,
  "events_publishable": 28,
  "scan_duration_seconds": 12.5
}
```

## Step 3: 파이프라인 출력 이해하기

스캔은 7단계를 거칩니다. 로그에서 볼 수 있는 내용:

### Stage 1: 수집
```
10:06:36 | INFO | USGS scan: 3 earthquakes found (M5.0+)
10:06:37 | INFO | GDELT scan: 50 articles found
10:06:38 | INFO | Reddit scan: 14 posts found
10:06:39 | INFO | Total events: 67, unique: 58
```

### Stage 2: 클러스터링
```
10:06:40 | INFO | New cluster detected: eb719719d08a (3 docs)
10:06:40 | INFO | New cluster detected: 3017d6e3fd2e (2 docs)
10:06:40 | INFO | Clustering complete: 39 clusters from 58 events
```

### Stage 3.5: 이벤트 검증 (Gate 0)
```
10:06:41 | INFO | [GATE0-REJECT] NOT_EVENT: pattern 'movie' matched
10:06:41 | INFO | [GATE0-PASS] ZERO_SHOT: military conflict (0.87)
10:06:42 | INFO | Event verification: 35/58 passed (39% passed)
```

### Stage 4: 신뢰도 점수화
```
10:06:43 | INFO | [CONFIDENCE] usgs: 0.74 (immediate_publish)
10:06:43 | INFO | [CONFIDENCE] gdelt: 0.70 (publishable)
10:06:43 | INFO | Confidence filter: 28 events passed (threshold=0.70)
```

## Step 4: 스캔 결과 보기

게시 가능한 이벤트 목록 가져오기:

```bash
curl http://localhost:8000/api/v1/agent/events
```

### 예시 이벤트 출력

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

## Step 5: 조사 시작

이벤트에 대한 기사를 생성하려면:

```bash
curl -X POST http://localhost:8000/api/v1/agent/investigate \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Federal agents arrest protesters at Minnesota church",
    "category": "protest"
  }'
```

### 예상 응답

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

## Step 6: 신뢰도 점수 이해하기

| 점수 | 수준 | 의미 |
|-------|-------|---------|
| 0.90+ | 매우 높음 | 다중 Tier-1 소스 |
| 0.70-0.89 | 높음 | 게시 가능, 검증됨 |
| 0.50-0.69 | 중간 | 추가 검증 필요 |
| < 0.50 | 낮음 | 신호만, 게시 안 함 |

## Step 7: 스캔 설정

`.env`에서 설정 조정:

```bash
# 소스 활성화/비활성화
AGENT_GDELT_ENABLED=true
AGENT_REDDIT_ENABLED=true
AGENT_USGS_ENABLED=false  # 지진 모니터링 비활성화

# 임계값 조정
AGENT_MIN_CONFIDENCE_SCORE=0.70  # 게시 임계값

# 필터 설정
AGENT_EVENT_VERIFICATION_ENABLED=true
AGENT_EVENT_VERIFICATION_USE_ZERO_SHOT=true
```

## 문제 해결

### 이벤트를 찾을 수 없음

1. 소스가 활성화되어 있는지 확인:
```bash
cat .env | grep ENABLED
```

2. GDELT 접근 가능 여부 확인:
```bash
curl "https://api.gdeltproject.org/api/v2/doc/doc?query=war&mode=artlist&maxrecords=10"
```

3. 테스트를 위해 신뢰도 임계값 낮추기:
```bash
AGENT_MIN_CONFIDENCE_SCORE=0.50
```

### 모든 이벤트가 Gate 0에서 필터링됨

무엇이 필터링되는지 확인:
```bash
AGENT_LOG_GATE_REJECTIONS=true
```

로그에서 패턴 확인:
```
[GATE0-REJECT] NOT_EVENT: pattern 'game' matched
```

정상적인 이벤트가 필터링되고 있다면 `app/agent/event_verifier.py`의 패턴을 검토하세요.

### LLM 오류

API 키가 유효한지 확인:
```bash
echo $OPENAI_API_KEY
```

타임아웃 설정 확인:
```bash
AGENT_LLM_TIMEOUT_SECONDS=60
```

## 다음 단계

- [추가 소스 설정](../guides/CONFIGURATION.md)
- [신뢰도 점수화 이해](../concepts/CONFIDENCE_SCORING.md)
- [커스텀 트리거 추가](../guides/TRIGGER_GUIDE.md)
- [API 참조 검토](../api/README.md)

---

*관련 문서:*
- [Getting Started](README.md)
- [Scanner Pipeline](../architecture/SCANNER_PIPELINE.md)
- [Event Verification](../architecture/EVENT_VERIFICATION.md)
