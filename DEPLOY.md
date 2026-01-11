# Livemap Backend - Oracle Cloud 배포 가이드

## Oracle Cloud Free Tier 스펙

- **Compute**: 4 OCPU (ARM64 Ampere A1)
- **Memory**: 24GB RAM
- **Storage**: 200GB Block Volume
- **Network**: 10TB/월 Outbound
- **비용**: 영구 무료

> 참고: AWS EC2 Free Tier (t2.micro)는 1GB RAM으로 ML 모델 로딩이 불가능합니다.
> Livemap은 ~2.8GB RAM이 필요합니다 (spaCy, DeBERTa NLI 모델).

---

## 1. Oracle Cloud 계정 생성

1. [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/) 접속
2. "Start for free" 클릭
3. 계정 정보 입력 (신용카드 필요, 청구되지 않음)
4. Home Region 선택: **Seoul (ap-seoul-1)** 권장

---

## 2. VM 인스턴스 생성

### Oracle Cloud Console에서:

1. **Compute > Instances > Create Instance**

2. **Image and shape**:
   - Image: **Ubuntu 22.04** (Canonical)
   - Shape: **VM.Standard.A1.Flex** (ARM64)
   - OCPUs: **2** (Free Tier 최대 4개 중 2개 사용)
   - Memory: **12GB** (Free Tier 최대 24GB 중 12GB 사용)

3. **Networking**:
   - VCN: 새로 생성 또는 기존 사용
   - Subnet: Public subnet
   - Public IPv4 address: **Assign**

4. **Add SSH keys**:
   - 새 키 생성 또는 기존 공개키 업로드
   - 생성한 경우 프라이빗 키 다운로드 (`.key` 파일)

5. **Boot volume**:
   - Size: **50GB** (기본값 충분)

6. **Create** 클릭

### Security List (방화벽) 설정:

1. **Networking > Virtual Cloud Networks > [VCN 선택] > Security Lists**
2. **Default Security List** 선택
3. **Add Ingress Rules**:

| Source CIDR | Protocol | Destination Port | Description |
|-------------|----------|------------------|-------------|
| 0.0.0.0/0 | TCP | 8000 | FastAPI |
| 0.0.0.0/0 | TCP | 80 | HTTP (Nginx) |
| 0.0.0.0/0 | TCP | 443 | HTTPS |

---

## 3. 서버 초기 설정

### SSH 접속:

```bash
# 프라이빗 키 권한 설정
chmod 400 ~/Downloads/ssh-key-*.key

# SSH 접속
ssh -i ~/Downloads/ssh-key-*.key ubuntu@<PUBLIC_IP>
```

### 시스템 업데이트:

```bash
sudo apt update && sudo apt upgrade -y
```

### Docker 설치:

```bash
# Docker 공식 설치
curl -fsSL https://get.docker.com | sudo sh

# 현재 사용자를 docker 그룹에 추가
sudo usermod -aG docker $USER

# 재로그인 (SSH 재접속)
exit
# 다시 SSH 접속
```

### Docker Compose 설치:

```bash
# Docker Compose v2 (plugin)
sudo apt install docker-compose-plugin -y

# 확인
docker compose version
```

---

## 4. 프로젝트 배포

### 프로젝트 클론:

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/livemap.git
cd livemap/backend
```

### 환경 변수 설정:

```bash
# .env 파일 생성
cat > .env << 'EOF'
# Database
DB_PASSWORD=your_secure_password_here

# SearXNG
SEARXNG_SECRET=your_random_secret_here

# Telegram (필수)
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=+82xxxxxxxxxx

# API Keys (선택)
GOOGLE_API_KEY=your_google_api_key
MISTRAL_API_KEY=your_mistral_api_key
EOF

# 권한 설정
chmod 600 .env
```

### SearXNG 설정 디렉토리:

```bash
mkdir -p docker/searxng
```

`docker/searxng/settings.yml` 이 이미 있는지 확인:

```bash
ls -la docker/searxng/
```

### Docker 이미지 빌드 및 실행:

```bash
# 빌드 (ARM64, 처음에는 10-15분 소요)
docker compose build

# 실행
docker compose up -d

# 로그 확인
docker compose logs -f api
```

### 상태 확인:

```bash
# 컨테이너 상태
docker compose ps

# 헬스체크
curl http://localhost:8000/health

# API 테스트
curl "http://localhost:8000/api/v1/feeds?limit=5"
```

---

## 5. 데이터베이스 마이그레이션

```bash
# 컨테이너 내에서 Alembic 실행
docker compose exec api uv run alembic upgrade head
```

---

## 6. Nginx 리버스 프록시 (선택)

### Nginx 설치:

```bash
sudo apt install nginx -y
```

### 설정:

```bash
sudo tee /etc/nginx/sites-available/livemap << 'EOF'
server {
    listen 80;
    server_name your-domain.com;  # 또는 IP 주소

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/livemap /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

### SSL 인증서 (Let's Encrypt):

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d your-domain.com
```

---

## 7. 모니터링

### 리소스 사용량 확인:

```bash
# 실시간 모니터링
docker stats

# 디스크 사용량
df -h

# 메모리 사용량
free -h
```

### 로그 확인:

```bash
# API 로그
docker compose logs -f api

# 모든 서비스 로그
docker compose logs -f

# 최근 100줄
docker compose logs --tail 100 api
```

---

## 8. 유지보수 명령어

```bash
# 서비스 재시작
docker compose restart api

# 전체 재시작
docker compose down && docker compose up -d

# 이미지 업데이트 후 재빌드
git pull
docker compose build --no-cache
docker compose up -d

# 사용하지 않는 이미지 정리
docker system prune -a
```

---

## 9. 트러블슈팅

### 컨테이너가 시작되지 않는 경우:

```bash
# 로그 확인
docker compose logs api

# 컨테이너 상태
docker compose ps -a
```

### 메모리 부족:

```bash
# 현재 메모리 사용량
free -h

# swap 추가 (필요시)
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 데이터베이스 연결 오류:

```bash
# PostgreSQL 컨테이너 상태
docker compose logs db

# 직접 접속 테스트
docker compose exec db psql -U livemap -d livemap
```

### SearXNG 오류:

```bash
# SearXNG 로그
docker compose logs searxng

# API 테스트
curl http://localhost:8888/search?q=test&format=json
```

---

## 10. 비용 요약

| 항목 | 비용 |
|------|------|
| Oracle Cloud VM | **무료** (Free Tier) |
| PostgreSQL | **무료** (Docker) |
| SearXNG | **무료** (Self-hosted) |
| Stage 1 NLP | **무료** (Local models) |
| Stage 2 RAG | **무료** (SearXNG + NLI) |
| Stage 3 LLM | **~$2/월** (Mistral Small, 15-20%만 호출) |
| **총계** | **~$2/월** |

---

## 다음 단계

1. 텔레그램 세션 인증 (최초 1회)
2. 프론트엔드 배포 (Vercel 무료)
3. 도메인 연결 및 SSL 설정
4. 모니터링 대시보드 구축 (Grafana, 선택)
