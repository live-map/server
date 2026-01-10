# Livemap Backend

실시간 글로벌 분쟁/뉴스 지도 서비스를 위한 데이터 수집 백엔드

## 빠른 시작

### 1. 의존성 설치

```bash
cd backend
uv sync
```

### 2. Telegram API 설정

1. https://my.telegram.org/apps 접속
2. API 발급 (api_id, api_hash)
3. `.env` 파일 생성:

```bash
cp .env.example .env
```

```env
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=your_api_hash_here
TELEGRAM_PHONE=+821012345678
```

### 3. 테스트 실행

```bash
# Telethon 직접 테스트 (먼저 이걸로 로그인)
uv run python -m tests.mcp.test_telegram_direct

# MCP 서버 테스트
uv run python -m tests.mcp.test_telegram_mcp
```

## MCP 서버 도구

| 도구 | 설명 |
|------|------|
| `list_channels` | 참여한 채널/그룹 목록 |
| `get_channel_messages` | 채널 최근 메시지 수집 |
| `search_channel` | 채널 내 키워드 검색 |
| `get_channel_info` | 채널 상세 정보 |

## Claude Desktop 설정

```json
{
  "mcpServers": {
    "telegram": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/backend", "python", "-m", "app.mcp.telegram_server"],
      "env": {
        "TELEGRAM_API_ID": "your_id",
        "TELEGRAM_API_HASH": "your_hash",
        "TELEGRAM_PHONE": "+821012345678"
      }
    }
  }
}
```
