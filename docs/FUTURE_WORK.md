# Future Work - 미래 작업 계획

> 현재 구현된 시스템의 다음 단계 개선 방향

---

## 개요

현재 구현 완료:
- [x] 다중 소스 트리거 (GDELT + X + Telegram)
- [x] Anomaly Detection 레이어
- [x] Semantic Clustering 레이어
- [x] LLM 분류 (GPT-4o-mini)

향후 구현 예정:
- [ ] Event-Driven Streaming (폴링 → 푸시)
- [ ] Tiered Autonomy (계층별 자율성)

---

## 1. Event-Driven Streaming

### 현재 상태: Polling

```
현재:
┌──────────────────────────────────────────────────────────────┐
│  15분마다 폴링                                                │
│                                                              │
│  GDELT ──(15분)──► Manager                                   │
│  Twitter ──(15분)──► Manager                                 │
│  Telegram ──(15분)──► Manager                                │
│                                                              │
│  문제: 최대 15분 딜레이                                       │
└──────────────────────────────────────────────────────────────┘
```

### 목표 상태: Event-Driven

```
목표:
┌──────────────────────────────────────────────────────────────┐
│  실시간 스트림                                                │
│                                                              │
│  Telegram (MTProto) ──(실시간)──┐                            │
│  WebSub/RSS (push) ──(실시간)───┼──► Kafka ──► Manager      │
│  X Streaming ──(실시간)─────────┘                            │
│                                                              │
│  GDELT ──(15분, 어쩔 수 없음)──► Batch Layer                 │
│                                                              │
│  결과: 텔레그램/RSS는 실시간, GDELT만 15분 딜레이             │
└──────────────────────────────────────────────────────────────┘
```

### 구현 계획

#### Phase 1: Telegram 실시간 전환

```python
# 현재: 폴링 방식
async def scan(self) -> list[TriggerEvent]:
    for channel in self.channels:
        async for message in self.client.iter_messages(channel, limit=20):
            # 처리

# 목표: 스트리밍 방식
async def stream(self) -> AsyncIterator[TriggerEvent]:
    @self.client.on(events.NewMessage(chats=self.channels))
    async def handler(event):
        yield TriggerEvent(
            title=event.message.text,
            source=TriggerSource.TELEGRAM,
            ...
        )
```

**필요 라이브러리:**
- `telethon` (이미 설치됨)
- MTProto 이벤트 핸들러 활용

#### Phase 2: RSS WebSub 전환

```python
# 목표: WebSub/Superfeedr 사용
from superfeedr import Superfeedr

superfeedr = Superfeedr(api_key="...")

# Push 콜백 등록
@app.post("/webhook/rss")
async def rss_webhook(data: dict):
    event = parse_rss_update(data)
    await manager.process_event(event)
```

**필요 라이브러리:**
- `superfeedr-python` 또는 직접 WebSub 구현
- 웹훅 엔드포인트 필요

#### Phase 3: Message Queue 도입

```python
# 목표: Kafka를 이벤트 백본으로
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

# 프로듀서 (각 소스)
producer = AIOKafkaProducer(bootstrap_servers='localhost:9092')
await producer.send('events', event.to_json())

# 컨슈머 (Manager)
consumer = AIOKafkaConsumer('events', bootstrap_servers='localhost:9092')
async for msg in consumer:
    event = TriggerEvent.from_json(msg.value)
    await process_event(event)
```

**필요 인프라:**
- Apache Kafka 또는 Redis Streams
- Docker Compose 업데이트 필요

### 예상 효과

| 소스 | 현재 딜레이 | 목표 딜레이 |
|------|------------|------------|
| GDELT | 15분 | 15분 (변경 불가) |
| Telegram | 15분 | **< 1초** |
| RSS feeds | 15분 | **< 1분** |
| X/Twitter | 15분 | **< 10초** |

### 기술 스택

| 컴포넌트 | 옵션 1 (간단) | 옵션 2 (확장성) |
|----------|-------------|----------------|
| Message Queue | Redis Streams | Apache Kafka |
| RSS Push | 직접 WebSub 구현 | Superfeedr |
| 배포 | Docker Compose | Kubernetes |

---

## 2. Tiered Autonomy (계층별 자율성)

### 현재 상태: 단일 자율성

```
현재:
┌──────────────────────────────────────────────────────────────┐
│  모든 작업이 동일한 자율성 수준                                │
│                                                              │
│  이벤트 감지 ──► 조사 ──► 리포트 생성 ──► 발행               │
│       ↑           ↑            ↑              ↑               │
│      자율        자율         자율           자율              │
│                                                              │
│  문제: 위험한 작업도 자율 실행                                │
└──────────────────────────────────────────────────────────────┘
```

### 목표 상태: 계층별 자율성

```
목표:
┌──────────────────────────────────────────────────────────────┐
│  TIER 1: 완전 자율 (승인 불필요)                              │
│  ────────────────────────────                                │
│  - 이벤트 감지                                                │
│  - 데이터 수집                                                │
│  - 중복 제거, 클러스터링                                      │
│  - 기본 분류                                                  │
├──────────────────────────────────────────────────────────────┤
│  TIER 2: Human-ON-the-Loop (비동기 검토)                      │
│  ────────────────────────────────────                        │
│  - 조사 계획 수립                                             │
│  - 소스 신뢰도 평가                                           │
│  - 리포트 초안 생성                                           │
│  - 교차 검증                                                  │
│                                                              │
│  작동: 자동 실행, 나중에 사람이 검토                          │
├──────────────────────────────────────────────────────────────┤
│  TIER 3: Human-IN-the-Loop (승인 필수)                        │
│  ────────────────────────────────────                        │
│  - 최종 리포트 발행                                           │
│  - 긴급 알림 발송                                             │
│  - 외부 API 호출                                              │
│  - 높은 확신도 주장 게시                                      │
│                                                              │
│  작동: 승인 대기 큐 → 사람 승인 → 실행                        │
└──────────────────────────────────────────────────────────────┘
```

### 구현 계획

#### Phase 1: 작업 분류 시스템

```python
from enum import Enum

class AutonomyTier(Enum):
    TIER_1 = "fully_autonomous"      # 자동 실행
    TIER_2 = "human_on_the_loop"     # 비동기 검토
    TIER_3 = "human_in_the_loop"     # 승인 필수

class Task:
    def __init__(self, action: str, data: dict):
        self.action = action
        self.data = data
        self.tier = self._determine_tier()

    def _determine_tier(self) -> AutonomyTier:
        if self.action in ["scan", "collect", "deduplicate", "cluster"]:
            return AutonomyTier.TIER_1
        elif self.action in ["investigate", "verify", "draft_report"]:
            return AutonomyTier.TIER_2
        else:
            return AutonomyTier.TIER_3
```

#### Phase 2: 승인 큐 시스템

```python
class ApprovalQueue:
    def __init__(self, db_session):
        self.db = db_session

    async def submit(self, task: Task) -> str:
        """TIER 3 작업 제출"""
        approval_id = str(uuid.uuid4())
        await self.db.execute("""
            INSERT INTO approval_queue (id, action, data, status, created_at)
            VALUES ($1, $2, $3, 'pending', NOW())
        """, approval_id, task.action, json.dumps(task.data))
        return approval_id

    async def approve(self, approval_id: str, user_id: str):
        """승인 처리"""
        await self.db.execute("""
            UPDATE approval_queue
            SET status = 'approved', approved_by = $2, approved_at = NOW()
            WHERE id = $1
        """, approval_id, user_id)

        # 승인된 작업 실행
        task = await self.get_task(approval_id)
        await self.execute_task(task)
```

#### Phase 3: 알림 시스템

```python
class NotificationService:
    async def notify_pending_approval(self, task: Task):
        """TIER 3 작업 승인 요청 알림"""
        await self.send_slack(f"승인 필요: {task.action}")
        await self.send_email(...)

    async def notify_tier2_review(self, task: Task, result: dict):
        """TIER 2 작업 결과 검토 알림"""
        await self.send_slack(f"검토 필요: {task.action} 완료")
```

### 데이터베이스 스키마

```sql
-- 승인 큐 테이블
CREATE TABLE approval_queue (
    id UUID PRIMARY KEY,
    action VARCHAR(100) NOT NULL,
    data JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, approved, rejected
    created_at TIMESTAMPTZ DEFAULT NOW(),
    approved_by VARCHAR(100),
    approved_at TIMESTAMPTZ,
    rejection_reason TEXT
);

-- 작업 로그 테이블
CREATE TABLE task_log (
    id UUID PRIMARY KEY,
    tier VARCHAR(20) NOT NULL,
    action VARCHAR(100) NOT NULL,
    data JSONB NOT NULL,
    result JSONB,
    executed_at TIMESTAMPTZ DEFAULT NOW(),
    reviewed BOOLEAN DEFAULT FALSE,
    reviewer VARCHAR(100)
);
```

### API 엔드포인트

```python
# 승인 대기 작업 목록
@app.get("/api/v1/approvals/pending")
async def list_pending_approvals():
    ...

# 작업 승인
@app.post("/api/v1/approvals/{id}/approve")
async def approve_task(id: str, user: User = Depends(get_current_user)):
    ...

# 작업 거부
@app.post("/api/v1/approvals/{id}/reject")
async def reject_task(id: str, reason: str, user: User = Depends(get_current_user)):
    ...

# TIER 2 작업 검토 목록
@app.get("/api/v1/reviews/pending")
async def list_pending_reviews():
    ...
```

### 예상 효과

| 측면 | 현재 | 목표 |
|------|------|------|
| 안전성 | 낮음 | 높음 (위험 작업 승인 필수) |
| 속도 | 빠름 | TIER 1/2는 빠름, TIER 3만 대기 |
| 투명성 | 낮음 | 높음 (모든 작업 로그) |
| 책임 | 불명확 | 명확 (승인자 기록) |

---

## 우선순위

| 작업 | 우선순위 | 예상 기간 | 이유 |
|------|---------|----------|------|
| Telegram 실시간 | 높음 | 1-2일 | 라이브러리 이미 있음, 효과 큼 |
| Tiered Autonomy | 중간 | 3-5일 | 안전성 향상, UI 필요 |
| RSS WebSub | 낮음 | 2-3일 | 효과 제한적 |
| Kafka 도입 | 낮음 | 5-7일 | 인프라 복잡도 증가 |

---

## 참고 자료

### Event-Driven
- [Superfeedr WebSub](https://superfeedr.com/)
- [Apache Kafka Architecture 2025](https://kafka.apache.org/documentation/)
- [telegram-osint-lib](https://github.com/Postuf/telegram-osint-lib)

### Tiered Autonomy
- [Deloitte: Autonomous AI Agents 2025](https://www.deloitte.com/...)
- [Human-on-the-Loop vs Human-in-the-Loop](https://skywork.ai/blog/...)
- [AI Agent Autonomy Levels](https://arxiv.org/html/2502.02649v3)

---

*작성일: 2026-01-12*
*상태: 계획 단계*
