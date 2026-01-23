# Deployment Guide

This guide covers deploying LiveMap to production environments.

---

## Deployment Options

| Option | Complexity | Cost | Best For |
|--------|------------|------|----------|
| Docker Compose | Low | $50-100/mo | Development, small scale |
| Cloud Run | Medium | $100-200/mo | Serverless, auto-scaling |
| Kubernetes | High | $200-500/mo | Large scale, high availability |

---

## Option 1: Docker Compose (Recommended for Start)

### Prerequisites

- Docker and Docker Compose installed
- Server with 2+ CPU cores, 4GB+ RAM
- Domain name (optional but recommended)

### Deployment Steps

```bash
# 1. Clone repository
git clone https://github.com/your-org/livemap.git
cd livemap/backend

# 2. Create production environment file
cp .env.example .env.production

# 3. Edit production settings
nano .env.production
```

Production `.env.production`:
```bash
# Required
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql+asyncpg://livemap:secure_password@db:5432/livemap

# Production settings
DEBUG=false
LOG_LEVEL=INFO
WORKERS=4

# Agent settings
AGENT_GDELT_ENABLED=true
AGENT_SCAN_INTERVAL_MINUTES=15
AGENT_MIN_CONFIDENCE_SCORE=0.70
```

```bash
# 4. Start services
docker compose -f docker-compose.prod.yml up -d

# 5. Run migrations
docker compose exec api alembic upgrade head

# 6. Verify deployment
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

- Google Cloud account
- `gcloud` CLI installed
- Cloud SQL instance (PostgreSQL with pgvector)

### Setup Steps

```bash
# 1. Configure gcloud
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# 2. Enable required services
gcloud services enable run.googleapis.com
gcloud services enable sqladmin.googleapis.com

# 3. Create Cloud SQL instance
gcloud sql instances create livemap-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1

# 4. Build and push container
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/livemap-api

# 5. Deploy to Cloud Run
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

- Kubernetes cluster (GKE, EKS, or self-managed)
- `kubectl` configured
- Helm (optional but recommended)

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
# Create secrets
kubectl create secret generic livemap-secrets \
  --from-literal=OPENAI_API_KEY=sk-... \
  --from-literal=DATABASE_URL=postgresql+asyncpg://...

# Apply deployment
kubectl apply -f k8s/deployment.yaml
```

---

## Reverse Proxy (Nginx)

For production, use Nginx as a reverse proxy:

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
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
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
# View logs
docker compose logs -f api

# In Kubernetes
kubectl logs -f deployment/livemap-api
```

### Metrics (Prometheus)

Add to your metrics collection:

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

| Component | Scale Strategy |
|-----------|---------------|
| API servers | Add replicas behind load balancer |
| Database | Read replicas, connection pooling |
| Scanner | Single instance (stateful) |

### Vertical Scaling

| Phase | CPU | RAM | Throughput |
|-------|-----|-----|------------|
| Phase A | 2 cores | 4GB | 5 articles/15min |
| Phase B | 4 cores + GPU | 16GB | 10 articles/15min |
| Phase C | 8+ cores | 32GB | 50+ articles/15min |

---

## Security Checklist

- [ ] Environment variables secured (not in git)
- [ ] Database password is strong and unique
- [ ] SSL/TLS enabled for all endpoints
- [ ] Firewall configured (only expose necessary ports)
- [ ] API rate limiting enabled
- [ ] Regular security updates scheduled
- [ ] Backup strategy implemented

---

## Related Documentation

- [Installation](../getting-started/INSTALLATION.md) - Development setup
- [Configuration](CONFIGURATION.md) - All settings
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues
