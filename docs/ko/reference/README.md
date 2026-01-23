# Reference Documentation

개발자를 위한 기술 참조 자료입니다.

---

## Contents

- **[Database Schema](DATABASE_SCHEMA.md)** - SQLAlchemy 모델 및 데이터베이스 구조
- **[Glossary](GLOSSARY.md)** - 용어 및 정의

---

## Quick Reference

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | 상태 확인 |
| `/api/v1/agent/scan` | POST | 스캔 실행 |
| `/api/v1/agent/status` | GET | 에이전트 상태 |
| `/api/v1/agent/investigate` | POST | 조사 시작 |
| `/api/v1/feeds` | GET | 기사 목록 |

전체 문서는 [API Reference](../api/README.md)를 참조하세요.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | - | LLM에 필요 |
| `DATABASE_URL` | - | PostgreSQL 연결 |
| `AGENT_GDELT_ENABLED` | true | GDELT 활성화 |
| `AGENT_SCAN_INTERVAL_MINUTES` | 15 | 스캔 주기 |

전체 목록은 [Configuration](../guides/CONFIGURATION.md)을 참조하세요.

### Source Tiers

| Tier | Credibility | Sources |
|------|-------------|---------|
| Tier-1 Govt | 0.99 | USGS, NOAA |
| Tier-1 News | 0.90 | GDELT |
| Tier-2 | 0.75-0.85 | ACLED, Currents |
| Tier-3 | 0.30-0.40 | Reddit, Telegram |

자세한 내용은 [Source Tiers](../concepts/SOURCE_TIERS.md)를 참조하세요.

---

## Related Documentation

- [Architecture](../architecture/README.md) - 시스템 설계
- [Algorithms](../algorithms/README.md) - 알고리즘 상세
- [Guides](../guides/README.md) - 사용 가이드
