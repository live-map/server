# API Key Management

API 자격 증명을 안전하게 관리하기 위한 가이드입니다.

---

## Required API Keys

| API | Required | Purpose |
|-----|----------|---------|
| OpenAI | **필수** | 검증 및 생성을 위한 LLM |
| Tavily | 선택 | 증거 수집을 위한 웹 검색 |
| Reddit | 선택 | Reddit API (더 높은 제한 허용) |

---

## Secure Storage

### Local Development

```bash
# Create .env file
cp .env.example .env

# Add your keys
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
```

**중요**: `.env` 파일을 git에 커밋하지 마세요!

### Production

환경 변수 또는 시크릿 매니저를 사용하세요:

#### Docker Compose

```yaml
services:
  api:
    env_file: .env.production  # Not committed to git
```

#### Kubernetes Secrets

```bash
kubectl create secret generic livemap-secrets \
  --from-literal=OPENAI_API_KEY=sk-...
```

#### Cloud Provider Secrets

- **AWS**: Secrets Manager 또는 Parameter Store
- **GCP**: Secret Manager
- **Azure**: Key Vault

---

## Key Rotation

### When to Rotate

- 유출 의심 시
- 팀원 퇴사 시
- 정기 스케줄 (분기별 권장)

### Rotation Steps

1. 제공업체에서 새 키 생성
2. 시크릿 스토리지 업데이트
3. 새 키 배포
4. 기능 확인
5. 이전 키 폐기

---

## API Key Security Practices

### Do

- 환경 변수 사용
- 프로덕션에서 시크릿 매니저 사용
- 정기적으로 키 로테이션
- 최소 권한 사용
- API 사용량 모니터링

### Don't

- 키를 git에 커밋
- API 키 로깅
- 채팅/이메일로 키 공유
- 개발 환경에서 프로덕션 키 사용
- 소스 코드에 키 하드코딩

---

## Monitoring Usage

### OpenAI

사용량 모니터링: https://platform.openai.com/usage

사용량 제한 설정:
- Soft limit: 알림 임계값
- Hard limit: 최대 지출

### Rate Limits

`config.py`에서 속도 제한 설정:

```python
max_concurrent_llm_calls: int = 3
llm_timeout_seconds: float = 60.0
```

---

## If Keys Are Compromised

1. **즉시** 제공업체에서 키 폐기
2. 새 키 생성
3. 모든 배포 환경 업데이트
4. 무단 사용에 대한 로그 감사
5. 침해 원인 파악을 위한 접근 검토

---

## Related Documentation

- [Configuration](../guides/CONFIGURATION.md) - 모든 설정
- [Deployment](../guides/DEPLOYMENT.md) - 프로덕션 설정
