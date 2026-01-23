# API Key Management

Guide for securely managing API credentials.

---

## Required API Keys

| API | Required | Purpose |
|-----|----------|---------|
| OpenAI | **Yes** | LLM for verification & generation |
| Tavily | Optional | Web search for evidence |
| Reddit | Optional | Reddit API (for higher limits) |

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

**Important**: Never commit `.env` to git!

### Production

Use environment variables or secret managers:

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

- **AWS**: Secrets Manager or Parameter Store
- **GCP**: Secret Manager
- **Azure**: Key Vault

---

## Key Rotation

### When to Rotate

- Suspected compromise
- Team member leaves
- Regular schedule (quarterly recommended)

### Rotation Steps

1. Generate new key from provider
2. Update secret storage
3. Deploy new key
4. Verify functionality
5. Revoke old key

---

## API Key Security Practices

### Do

- Use environment variables
- Use secret managers in production
- Rotate keys regularly
- Use minimal permissions
- Monitor API usage

### Don't

- Commit keys to git
- Log API keys
- Share keys via chat/email
- Use production keys in development
- Hardcode keys in source code

---

## Monitoring Usage

### OpenAI

Monitor usage at: https://platform.openai.com/usage

Set usage limits:
- Soft limit: Alert threshold
- Hard limit: Maximum spend

### Rate Limits

Configure rate limiting in `config.py`:

```python
max_concurrent_llm_calls: int = 3
llm_timeout_seconds: float = 60.0
```

---

## If Keys Are Compromised

1. **Immediately** revoke the key at the provider
2. Generate new key
3. Update all deployments
4. Audit logs for unauthorized usage
5. Review access to determine breach source

---

## Related Documentation

- [Configuration](../guides/CONFIGURATION.md) - All settings
- [Deployment](../guides/DEPLOYMENT.md) - Production setup
