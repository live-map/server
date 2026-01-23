# Deployment Guide

이 가이드는 LiveMap을 프로덕션 환경에 배포하는 방법을 다룹니다.

---

## Deployment Options

| 옵션 | 복잡도 | 비용 | 적합한 용도 |
|------|--------|------|-------------|
| Docker Compose | 낮음 | $50-100/월 | 개발, 소규모 |
| Cloud Run | 중간 | $100-200/월 | 서버리스, 자동 스케일링 |
| Kubernetes | 높음 | $200-500/월 | 대규모, 고가용성 |

---

## Option 1: Docker Compose (Recommended for Start)

### Prerequisites

- Docker와 Docker Compose 설치됨
- 2+ CPU 코어, 4GB+ RAM을 갖춘 서버
- 도메인 이름 (선택 사항이지만 권장)

### Deployment Steps

```bash
# 1. 저장소 클론
git clone https://github.com/your-org/livemap.git
cd livemap/backend

# 2. 프로덕션 환경 파일 생성
cp .env.example .env.production

# 3. 프로덕션 설정 편집
nano .env.production
```

프로덕션 `.env.production`:
```bash
# 필수
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql+asyncpg://livemap:secure_password@db:5432/livemap

# 프로덕션 설정
DEBUG=false
LOG_LEVEL=INFO
WORKERS=4

# Agent 설정
AGENT_GDELT_ENABLED=true
AGENT_SCAN_INTERVAL_MINUTES=15
AGENT_MIN_CONFIDENCE_SCORE=0.70
```

```bash
# 4. 서비스 시작
docker compose -f docker-compose.prod.yml up -d

# 5. 마이그레이션 실행
docker compose exec api alembic upgrade head

# 6. 배포 확인
curl http://localhost:8000/health
```

### docker-compose.prod.yml

```yaml
version: '3.8'
services:
  api:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
    env_file: .env.production
    ports:
      - "8000:8000"
    depends_on:
      - db
    restart: always

  db:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_USER: livemap
      POSTGRES_PASSWORD: secure_password
      POSTGRES_DB: livemap
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always

volumes:
  postgres_data:
```

---

## Option 2: Google Cloud Run

### Prerequisites

- Google Cloud 계정
- `gcloud` CLI 설치됨
- Cloud SQL 인스턴스 (pgvector가 포함된 PostgreSQL)

### Setup Steps

```bash
# 1. gcloud 구성
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# 2. 필요한 서비스 활성화
gcloud services enable run.googleapis.com
gcloud services enable sqladmin.googleapis.com

# 3. Cloud SQL 인스턴스 생성
gcloud sql instances create livemap-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1

# 4. 컨테이너 빌드 및 푸시
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/livemap-api

# 5. Cloud Run에 배포
gcloud run deploy livemap-api \
  --image gcr.io/YOUR_PROJECT_ID/livemap-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "OPENAI_API_KEY=sk-..." \
  --add-cloudsql-instances YOUR_PROJECT_ID:us-central1:livemap-db
```

---

## Option 3: Kubernetes

### Prerequisites

- Kubernetes 클러스터 (GKE, EKS 또는 자체 관리)
- `kubectl` 구성됨
- Helm (선택 사항이지만 권장)

### Deployment with kubectl

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: livemap-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: livemap-api
  template:
    metadata:
      labels:
        app: livemap-api
    spec:
      containers:
      - name: api
        image: livemap/api:latest
        ports:
        - containerPort: 8000
        envFrom:
        - secretRef:
            name: livemap-secrets
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2"
---
apiVersion: v1
kind: Service
metadata:
  name: livemap-api
spec:
  selector:
    app: livemap-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

```bash
# Secret 생성
kubectl create secret generic livemap-secrets \
  --from-literal=OPENAI_API_KEY=sk-... \
  --from-literal=DATABASE_URL=postgresql+asyncpg://...

# 배포 적용
kubectl apply -f k8s/deployment.yaml
```

---

## Reverse Proxy (Nginx)

프로덕션에서는 Nginx를 리버스 프록시로 사용합니다:

```nginx
# /etc/nginx/sites-available/livemap
server {
    listen 80;
    server_name api.livemap.example.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### SSL with Let's Encrypt

```bash
# certbot 설치
sudo apt install certbot python3-certbot-nginx

# 인증서 발급
sudo certbot --nginx -d api.livemap.example.com
```

---

## Monitoring

### Health Checks

```bash
# Liveness probe
curl http://localhost:8000/health

# Readiness probe
curl http://localhost:8000/api/v1/agent/status
```

### Logging

```bash
# 로그 보기
docker compose logs -f api

# Kubernetes에서
kubectl logs -f deployment/livemap-api
```

### Metrics (Prometheus)

메트릭 수집에 추가합니다:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'livemap'
    static_configs:
      - targets: ['localhost:8000']
```

---

## Scaling Considerations

### Horizontal Scaling

| 컴포넌트 | 스케일 전략 |
|----------|-------------|
| API 서버 | 로드 밸런서 뒤에 레플리카 추가 |
| 데이터베이스 | 읽기 레플리카, 커넥션 풀링 |
| Scanner | 단일 인스턴스 (상태 저장) |

### Vertical Scaling

| 단계 | CPU | RAM | 처리량 |
|------|-----|-----|--------|
| Phase A | 2 코어 | 4GB | 5 기사/15분 |
| Phase B | 4 코어 + GPU | 16GB | 10 기사/15분 |
| Phase C | 8+ 코어 | 32GB | 50+ 기사/15분 |

---

## Security Checklist

- [ ] 환경 변수 보안 (git에 포함하지 않음)
- [ ] 데이터베이스 비밀번호가 강력하고 고유함
- [ ] 모든 엔드포인트에 SSL/TLS 활성화
- [ ] 방화벽 구성 (필요한 포트만 노출)
- [ ] API 속도 제한 활성화
- [ ] 정기적인 보안 업데이트 예약
- [ ] 백업 전략 구현

---

## Related Documentation

- [Installation](../getting-started/INSTALLATION.md) - 개발 환경 설정
- [Configuration](CONFIGURATION.md) - 모든 설정
- [Troubleshooting](TROUBLESHOOTING.md) - 일반적인 문제
