# Grapoll 배포 전략: Fly.io + Supabase 마이그레이션

> 작성일: 2026-03-06
> 목적: Railway(US) → Fly.io(Tokyo) 마이그레이션, DB 선정 근거 문서화

---

## 1. 마이그레이션 배경

### 문제
- Railway는 US 리전만 제공 → 한국 유저 RTT ~150-200ms
- 10K DAU 기준 월 $35-65 비용
- AI 워커(리서치 에이전트) 상시 가동 시 추가 비용 부담

### 목표
- 한국 유저 레이턴시 150ms → ~30ms (5x 개선)
- 월 운영비 $8-10 (초기) → $30-35 (Pro 전환 시)
- AI 워커 비용 최적화 (idle 시 stopped machine)

---

## 2. 컴퓨트 플랫폼 비교

### 2-1. 비교표

| 기준 | Railway | Fly.io | Render | OCI Free Tier |
|------|---------|--------|--------|---------------|
| **월 비용 (10K DAU)** | $35-65 | $8-25 | $15-50 | $0 |
| **아시아 리전** | US만 | Tokyo (nrt) | US/EU만 | Seoul, Tokyo |
| **한국 RTT** | ~150-200ms | ~30ms | ~150-200ms | ~5ms |
| **MCP/CLI 자동화** | CLI만 | MCP 네이티브 | CLI만 | SSH |
| **pgvector 지원** | 플러그인 | 지원 | 미지원 | Docker 자유 |
| **per-second 과금** | O | O | X (고정) | N/A |
| **stopped machine** | X | O (rootfs만 과금) | X | N/A |
| **배포 방식** | git push / CLI | flyctl deploy / GH Actions | git push | Docker + SSH |
| **스케일링** | 수동 | 자동 (auto_stop/start) | 수동 | 수동 |

### 2-2. 플랫폼별 분석

#### Railway
- **장점**: 간편한 설정, git push 배포, 환경변수 UI
- **단점**: US 리전만 제공, 한국 유저 고레이턴시, 유휴 시에도 과금
- **비용**: Hobby $5/mo + 사용량 기반 (vCPU $0.000463/min, RAM $0.000231/min/GB)

#### Fly.io (선정)
- **장점**: Tokyo(nrt) 리전, per-second 과금, stopped machine으로 AI 워커 비용 최적화, MCP 네이티브 지원
- **단점**: 학습 곡선(flyctl), 네트워킹 설정 복잡도
- **비용**: shared-cpu-2x 1GB = ~$5.35/mo, stopped machine은 rootfs 저장비만 과금
- **핵심**: `auto_stop_machines = "stop"` + `auto_start_machines = true`로 트래픽 없을 때 자동 정지, 요청 시 자동 시작 (cold start ~300ms)

#### Render
- **장점**: 간편한 UI, 무료 티어 존재
- **단점**: US/EU 리전만, 고정 과금(per-second 아님), pgvector 미지원, 15분 무활동 시 sleep(Free)
- **비용**: Starter $7/mo (고정), Standard $25/mo

#### OCI Free Tier
- **장점**: 무료, Seoul 리전(최저 레이턴시), 완전한 인프라 제어
- **단점**: 관리 부담 극대(OS, Docker, 네트워크, SSL, 백업 모두 수동), Free Tier 제한(2 VM, 1GB RAM), 스케일링 불가
- **비용**: $0 (Always Free 범위 내)
- **참고**: 현재 OCI SSH 기반 배포 경험 있음 (deploy-backend.yml)

### 2-3. 선정 근거: Fly.io

1. **레이턴시**: Tokyo(nrt) 리전으로 한국 유저 ~30ms RTT 달성
2. **비용 효율**: stopped machine으로 AI 리서치 워커를 idle 시 정지 → 월 $2-5 수준
3. **운영 편의**: managed platform이라 OS/네트워크 관리 불필요 (OCI 대비)
4. **자동화**: flyctl MCP, GitHub Actions 네이티브 지원
5. **확장성**: 멀티 리전 배포, 자동 스케일링 지원

---

## 3. 데이터베이스 플랫폼 비교

### 3-1. 비교표

| 기준 | Neon Serverless | Supabase | Fly Postgres (Community) | Fly Managed PG |
|------|----------------|----------|--------------------------|----------------|
| **가격** | Free 0.5GB / Scale $19 | Free 500MB / Pro $25 | 컴퓨트비만 (~$5-10) | $38+ |
| **Tokyo 리전** | X (Singapore가 최근접) | O (Tokyo) | O (Tokyo) | O (Tokyo) |
| **한국→DB 레이턴시** | ~60-100ms (Singapore) | ~1-5ms (같은 AWS Tokyo) | ~1-5ms (같은 Tokyo) | ~1-5ms |
| **pgvector** | O | O | O | O |
| **Cold start** | 300-500ms (auto-suspend) | 1주 비활성 시 pause (Free) | 없음 (always-on) | 없음 |
| **Connection pooling** | 내장 (serverless driver) | Supavisor (PgBouncer 기반) | 없음 (직접 설정) | 내장 |
| **asyncpg 호환** | O (direct connection) | O (direct connection) | O | O |
| **백업** | 자동 (PITR) | 자동 (daily, Pro는 PITR) | 수동 (Tigris bucket) | 자동 |
| **HA/Failover** | 자동 | Pro에서 지원 | 수동 설정 | 자동 |
| **관리 부담** | 최소 | 최소 | 높음 | 최소 |

### 3-2. 플랫폼별 심층 분석

#### Neon Serverless
- **아키텍처**: Compute와 Storage 분리, serverless auto-scaling
- **장점**: PITR, branching(개발/스테이징 DB 복제), serverless 드라이버로 edge 배포 호환
- **단점**: Tokyo 리전 없음. Singapore가 최근접인데 한국→싱가포르 네트워크 경로 불안정 (60-100ms). Fly.io Tokyo에서 Neon Singapore 접근 시에도 ~30-50ms DB 레이턴시 추가
- **결론**: 컴퓨트(Tokyo)와 DB(Singapore)가 다른 리전이면 모든 쿼리에 30-50ms 오버헤드. 이는 API 전체 레이턴시를 60-80ms로 올려 마이그레이션 효과를 반감시킴

#### Supabase (선정)
- **아키텍처**: AWS 기반 managed PostgreSQL + PostgREST + Auth + Storage
- **장점**: Tokyo 리전 존재(AWS ap-northeast-1), Fly.io Tokyo(nrt)와 같은 AWS 가용영역으로 DB 레이턴시 ~1-5ms, pgvector 네이티브, Supavisor connection pooling 내장
- **단점**: Free tier 1주 비활성 시 pause (10K DAU면 해당 없음), PostgREST/Auth 등 불필요 기능 포함
- **비용**: Free(500MB, 2 프로젝트) → Pro($25/mo, 8GB, daily backup)
- **asyncpg 호환**: Direct connection string 사용 시 asyncpg 완전 호환. Supavisor transaction mode도 asyncpg와 호환

#### Fly Postgres (Community Edition)
- **아키텍처**: Fly.io VM 위에 직접 PostgreSQL 실행
- **장점**: 최저 비용(VM 비용만), 같은 Fly.io 내부 네트워크로 최저 레이턴시
- **단점**: **Unmanaged** - Fly.io 공식 지원 없음. 백업(Tigris S3 수동), HA(Stolon 수동 설정), 업그레이드(수동), 모니터링(직접 구축) 모두 직접 관리. 장애 시 복구 책임도 본인
- **결론**: 1인 개발 환경에서 DB 운영까지 직접 관리하는 것은 리스크 대비 이점이 부족

#### Fly Managed PostgreSQL
- **아키텍처**: Fly.io가 관리하는 PostgreSQL (Supabase 파트너십 기반)
- **장점**: 자동 백업, HA, Fly.io 내부 네트워크 최적화
- **단점**: $38/mo 시작 → 10K DAU 초기 스테이지에선 과도한 비용
- **결론**: 트래픽이 충분히 성장한 후(~50K DAU) 고려

### 3-3. 선정 근거: Supabase

1. **리전 일치**: Fly.io Tokyo(nrt)와 Supabase Tokyo(AWS ap-northeast-1) 동일 리전 → DB 레이턴시 ~1-5ms
2. **관리형**: 백업, 모니터링, connection pooling 내장 → 1인 개발자 운영 부담 최소화
3. **비용**: Free tier(500MB)로 시작 → 필요 시 Pro($25/mo) 전환
4. **pgvector**: `CREATE EXTENSION vector;` 한 줄로 활성화, AI 리서치 임베딩 저장 대비
5. **asyncpg 호환**: Direct connection + Supavisor transaction mode 모두 asyncpg와 호환

---

## 4. 최종 아키텍처

```
[한국 유저] → [Vercel Edge (프론트)] → [Fly.io Tokyo nrt (FastAPI)] → [Supabase Tokyo (PostgreSQL)]
                                              |
                                              ├─ [OpenAI API] (리서치 에이전트)
                                              ├─ [Anthropic API] (리서치 에이전트)
                                              ├─ [Tavily API] (웹 검색)
                                              └─ [AWS S3] (미디어 스토리지)
```

### 레이턴시 비교

| 구간 | Before (Railway US) | After (Fly.io Tokyo) |
|------|-------------------|---------------------|
| 유저 → API | ~150-200ms | ~30ms |
| API → DB | ~5ms (Railway 내부) | ~1-5ms (같은 AWS Tokyo) |
| **전체 RTT** | **~160-210ms** | **~35-40ms** |

### 예상 월 비용

| 항목 | 초기 (Free DB) | Pro DB 전환 시 |
|------|---------------|---------------|
| Fly.io API Machine (shared-cpu-2x, 1GB) | ~$5.35 | ~$5.35 |
| Fly.io AI Worker (stopped when idle) | ~$2-5 | ~$2-5 |
| Supabase | $0 (Free 500MB) | $25 (Pro 8GB) |
| **합계** | **~$8-10/mo** | **~$30-35/mo** |

vs Railway 현재: **$35-65/mo**

---

## 5. 마이그레이션 체크리스트

### Phase 1: 인프라 준비
- [x] Fly.io 앱 생성 (`flyctl launch --no-deploy`) → `grapoll-api` (nrt)
- [x] Supabase 프로젝트 생성 (Tokyo 리전, AWS ap-northeast-1)
- [x] pgvector extension 활성화
- [x] fly.toml 설정 및 커밋

### Phase 2: 데이터 마이그레이션
- [x] Railway DB pg_dump
- [x] Supabase에 pg_restore
- [x] 데이터 무결성 검증 (row count, 샘플 데이터 비교)

### Phase 3: 환경변수 & 배포
- [x] `flyctl secrets set` 으로 환경변수 설정
- [x] GitHub Actions 워크플로우 업데이트 → `.github/workflows/fly-deploy.yml`
- [x] `flyctl deploy` 초기 배포 → grapoll-api.fly.dev
- [x] 헬스체크 확인 (`/health`)

### Phase 4: DNS & 트래픽 전환
- [x] Fly.io 배포 URL: grapoll-api.fly.dev
- [x] Vercel 프론트엔드 API_URL 변경 (grapoll.vercel.app → grapoll-api.fly.dev)
- [x] Railway 서비스 중지
- [x] 레이턴시 확인 완료

### Phase 5: 정리
- [x] Railway 프로젝트 정리
- [x] OCI 관련 GitHub Secrets 정리
- [x] 문서 업데이트 (CLAUDE.md, README, project-context.md)

---

## 6. 리스크 & 대응

| 리스크 | 영향 | 대응 |
|--------|------|------|
| Fly.io cold start (~300ms) | 첫 요청 느림 | `min_machines_running = 1`로 최소 1대 상시 가동 |
| Supabase Free tier pause | DB 연결 실패 | 10K DAU면 pause 안 됨; 보험으로 크론잡 핑 |
| 데이터 마이그레이션 중 다운타임 | 서비스 중단 | 점검 공지 후 진행 (야간 시간대) |
| Supabase connection limit | 동시 접속 초과 | Supavisor pooling 사용, Pro 전환 시 200 connections |
| asyncpg + Supavisor 호환성 | 연결 오류 | transaction mode 사용 (session mode 대신) |

---

## 7. Fly.io 설정 상세

### fly.toml 핵심 설정

```toml
app = "grapoll-api"
primary_region = "nrt"  # Tokyo

[http_service]
  auto_stop_machines = "stop"    # 트래픽 없으면 VM 정지
  auto_start_machines = true     # 요청 오면 자동 시작
  min_machines_running = 1       # 최소 1대 상시 가동 (cold start 방지)

[[vm]]
  memory = "1gb"
  cpu_kind = "shared"
  cpus = 2
```

### Supabase 연결 설정

```
# Direct connection (asyncpg용)
DATABASE_URL=postgresql+asyncpg://{user}:{pass}@db.{ref}.supabase.co:5432/postgres

# Supavisor transaction mode (connection pooling)
DATABASE_URL=postgresql+asyncpg://{user}:{pass}@{ref}.pooler.supabase.com:6543/postgres?pgbouncer=true
```

**참고**: asyncpg는 prepared statements를 사용하므로, Supavisor 사용 시 transaction mode + `prepared_statement_cache_size=0` 설정 필요.

---

*마이그레이션 완료 (2026-03-06). 모든 Phase 완료, 서비스 정상 운영 중.*
