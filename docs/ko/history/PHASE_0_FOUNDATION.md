# Phase 0: Foundation

**Date**: January 10, 2026

---

## Overview

뉴스 이벤트 수집을 위한 기본 인프라를 구축하는 초기 프로젝트 설정입니다.

---

## Key Achievements

### 1. Telegram MCP Integration

Telegram 채널 모니터링을 위해 Model Context Protocol (MCP)을 사용한 첫 번째 데이터 소스 통합입니다.

```python
# Basic Telegram trigger
class TelegramTrigger(BaseTrigger):
    async def scan(self) -> list[TriggerEvent]:
        messages = await self.client.get_channel_messages()
        return [TriggerEvent(...) for msg in messages]
```

### 2. GDELT Trigger

글로벌 뉴스 모니터링을 위한 GDELT DOC API 통합입니다.

```python
# GDELT API query
url = "https://api.gdeltproject.org/api/v2/doc/doc"
params = {
    "query": "war OR conflict OR earthquake",
    "mode": "artlist",
    "maxrecords": 100,
}
```

### 3. Basic Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI entry
│   ├── agent/
│   │   └── triggers/        # Data source triggers
│   └── models/              # Database models
└── docs/                    # Documentation
```

---

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Web framework | FastAPI | 비동기 지원, 자동 문서화 |
| Database | PostgreSQL | 안정성, pgvector 지원 |
| Package manager | uv | 빠르고 현대적인 Python 도구 |

---

## Lessons Learned

1. **GDELT rate limiting**: API 제한을 준수해야 합니다
2. **Telegram complexity**: MCP 접근 방식이 통합을 단순화했습니다
3. **Async-first**: 처음부터 비동기로 설계해야 합니다

---

## Next Phase

[Phase 1: Verification](PHASE_1_VERIFICATION.md) - 검증 파이프라인 추가
