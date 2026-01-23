# Data Handling

LiveMap이 데이터를 처리하고 저장하는 방법입니다.

---

## Data Flow

```
External Sources → Collection → Processing → Storage → Output
     │                │             │           │         │
   GDELT          Triggers      Verification   PostgreSQL  API
   Reddit         Scanner       Claim-level    pgvector    Feed
   USGS           Clustering    Generation                 JSON
```

---

## Data Categories

### Source Data

| Type | Retention | Storage |
|------|-----------|---------|
| Event metadata | 7일 | events 테이블 |
| Article content | 영구 | feeds 테이블 |
| Embeddings | 영구 | pgvector |

### Processing Data

| Type | Retention | Storage |
|------|-----------|---------|
| LLM responses | 저장하지 않음 | 메모리에서만 처리 |
| Intermediate claims | 기사와 함께 저장 | feeds의 JSONB |
| Verification results | 기사와 함께 저장 | feeds의 JSONB |

---

## Privacy Considerations

### No Personal Data Collection

LiveMap은 **공개적으로 이용 가능한 뉴스**를 처리하며 다음을 수행하지 않습니다:
- 사용자 개인 데이터 수집
- 개별 사용자 추적
- 쿠키 또는 식별자 저장
- 사용자 행동 프로파일링

### Source Attribution

모든 기사에는 다음이 포함됩니다:
- 출처 URL
- 출처 이름
- 신뢰도 점수
- 검증 방법론 링크

---

## Data Retention

### Default Policies

```python
# config.py
event_retention_days: int = 7      # Raw events
article_retention_days: int = -1    # Permanent (-1 = never delete)
```

### Cleanup Procedures

```sql
-- Manual cleanup of old events
DELETE FROM events
WHERE processed_at < NOW() - INTERVAL '7 days'
AND is_duplicate = true;
```

---

## External API Data

### GDELT

- 퍼블릭 도메인 데이터
- 인증 필요 없음
- 속도 제한 있음 (제한 준수 필요)

### OpenAI

- 프롬프트가 API로 전송됨
- OpenAI의 데이터 정책 적용
- 학습에 사용되지 않음 (API 사용)

### Reddit

- 공개 게시물 데이터만 수집
- 비공개 메시지나 DM 수집 안 함
- robots.txt 준수

---

## Database Security

### Access Control

```sql
-- Restrict database access
GRANT SELECT, INSERT, UPDATE, DELETE ON feeds TO livemap_api;
GRANT SELECT, INSERT ON events TO livemap_api;
REVOKE ALL ON ALL TABLES FROM PUBLIC;
```

### Encryption

- **저장 시(At rest)**: PostgreSQL 디스크 암호화 사용
- **전송 시(In transit)**: 데이터베이스 연결에 SSL 사용

```python
# Secure connection string
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/livemap?ssl=require
```

---

## Logging

### What We Log

- 이벤트 처리 횟수
- 오류 메시지 (내용 제외)
- 성능 메트릭
- API 응답 시간

### What We Don't Log

- 전체 기사 내용
- API 키
- 사용자 쿼리 (있는 경우)
- 원본 문서 본문

### Log Example

```
10:06:47 | INFO | Scanner completed: 95 events processed
10:06:48 | INFO | Event verification: 35/168 passed
10:06:49 | INFO | Investigation started: event_id=123
```

---

## Compliance Notes

### GDPR (해당되는 경우)

- 개인 데이터 처리 없음
- 출처 데이터는 공개 뉴스
- EU 사용자 데이터 수집 없음

### IFCN

- 방법론 투명성
- 출처 표시
- 정정 정책

---

## Related Documentation

- [API Keys](API_KEYS.md) - 자격 증명 보안
- [Configuration](../guides/CONFIGURATION.md) - 설정
- [Database Schema](../reference/DATABASE_SCHEMA.md) - 데이터 구조
