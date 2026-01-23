# Future Work - Roadmap

> Next-stage improvement directions for the currently implemented system

---

## Overview

Currently implemented:
- [x] Multi-source triggers (GDELT + X + Telegram)
- [x] Anomaly Detection layer
- [x] Semantic Clustering layer
- [x] LLM classification (GPT-4o-mini)

Planned for future implementation:
- [ ] Event-Driven Streaming (polling → push)
- [ ] Tiered Autonomy (autonomy levels by tier)

---

## 1. Event-Driven Streaming

### Current State: Polling

```
Current:
┌──────────────────────────────────────────────────────────────┐
│  Polling every 15 minutes                                    │
│                                                              │
│  GDELT ──(15min)──► Manager                                  │
│  Twitter ──(15min)──► Manager                                │
│  Telegram ──(15min)──► Manager                               │
│                                                              │
│  Problem: Up to 15 minute delay                              │
└──────────────────────────────────────────────────────────────┘
```

### Target State: Event-Driven

```
Target:
┌──────────────────────────────────────────────────────────────┐
│  Real-time stream                                            │
│                                                              │
│  Telegram (MTProto) ──(real-time)──┐                         │
│  WebSub/RSS (push) ──(real-time)───┼──► Kafka ──► Manager    │
│  X Streaming ──(real-time)─────────┘                         │
│                                                              │
│  GDELT ──(15min, unavoidable)──► Batch Layer                 │
│                                                              │
│  Result: Telegram/RSS real-time, only GDELT has 15min delay  │
└──────────────────────────────────────────────────────────────┘
```

### Implementation Plan

#### Phase 1: Telegram Real-time Conversion

```python
# Current: Polling approach
async def scan(self) -> list[TriggerEvent]:
    for channel in self.channels:
        async for message in self.client.iter_messages(channel, limit=20):
            # processing

# Target: Streaming approach
async def stream(self) -> AsyncIterator[TriggerEvent]:
    @self.client.on(events.NewMessage(chats=self.channels))
    async def handler(event):
        yield TriggerEvent(
            title=event.message.text,
            source=TriggerSource.TELEGRAM,
            ...
        )
```

**Required libraries:**
- `telethon` (already installed)
- Utilize MTProto event handlers

#### Phase 2: RSS WebSub Conversion

```python
# Target: Use WebSub/Superfeedr
from superfeedr import Superfeedr

superfeedr = Superfeedr(api_key="...")

# Register push callback
@app.post("/webhook/rss")
async def rss_webhook(data: dict):
    event = parse_rss_update(data)
    await manager.process_event(event)
```

**Required libraries:**
- `superfeedr-python` or implement WebSub directly
- Webhook endpoint needed

#### Phase 3: Message Queue Introduction

```python
# Target: Kafka as event backbone
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

# Producer (each source)
producer = AIOKafkaProducer(bootstrap_servers='localhost:9092')
await producer.send('events', event.to_json())

# Consumer (Manager)
consumer = AIOKafkaConsumer('events', bootstrap_servers='localhost:9092')
async for msg in consumer:
    event = TriggerEvent.from_json(msg.value)
    await process_event(event)
```

**Required infrastructure:**
- Apache Kafka or Redis Streams
- Docker Compose update needed

### Expected Benefits

| Source | Current Delay | Target Delay |
|--------|---------------|--------------|
| GDELT | 15 min | 15 min (unchangeable) |
| Telegram | 15 min | **< 1 sec** |
| RSS feeds | 15 min | **< 1 min** |
| X/Twitter | 15 min | **< 10 sec** |

### Technology Stack

| Component | Option 1 (Simple) | Option 2 (Scalable) |
|-----------|-------------------|---------------------|
| Message Queue | Redis Streams | Apache Kafka |
| RSS Push | Implement WebSub directly | Superfeedr |
| Deployment | Docker Compose | Kubernetes |

---

## 2. Tiered Autonomy

### Current State: Single Autonomy Level

```
Current:
┌──────────────────────────────────────────────────────────────┐
│  All tasks at the same autonomy level                        │
│                                                              │
│  Event Detection ──► Investigation ──► Report Gen ──► Publish│
│       ↑                  ↑                ↑            ↑     │
│   Autonomous         Autonomous       Autonomous   Autonomous│
│                                                              │
│  Problem: Risky tasks also run autonomously                  │
└──────────────────────────────────────────────────────────────┘
```

### Target State: Tiered Autonomy

```
Target:
┌──────────────────────────────────────────────────────────────┐
│  TIER 1: Fully Autonomous (no approval needed)               │
│  ──────────────────────────────────────────                  │
│  - Event detection                                           │
│  - Data collection                                           │
│  - Deduplication, clustering                                 │
│  - Basic classification                                      │
├──────────────────────────────────────────────────────────────┤
│  TIER 2: Human-ON-the-Loop (async review)                    │
│  ─────────────────────────────────────────                   │
│  - Investigation plan development                            │
│  - Source credibility assessment                             │
│  - Report draft generation                                   │
│  - Cross-verification                                        │
│                                                              │
│  Behavior: Auto-execute, human reviews later                 │
├──────────────────────────────────────────────────────────────┤
│  TIER 3: Human-IN-the-Loop (approval required)               │
│  ─────────────────────────────────────────────               │
│  - Final report publication                                  │
│  - Urgent alert dispatch                                     │
│  - External API calls                                        │
│  - High-confidence claim posting                             │
│                                                              │
│  Behavior: Wait in approval queue → Human approves → Execute │
└──────────────────────────────────────────────────────────────┘
```

### Implementation Plan

#### Phase 1: Task Classification System

```python
from enum import Enum

class AutonomyTier(Enum):
    TIER_1 = "fully_autonomous"      # Auto-execute
    TIER_2 = "human_on_the_loop"     # Async review
    TIER_3 = "human_in_the_loop"     # Approval required

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

#### Phase 2: Approval Queue System

```python
class ApprovalQueue:
    def __init__(self, db_session):
        self.db = db_session

    async def submit(self, task: Task) -> str:
        """Submit TIER 3 task"""
        approval_id = str(uuid.uuid4())
        await self.db.execute("""
            INSERT INTO approval_queue (id, action, data, status, created_at)
            VALUES ($1, $2, $3, 'pending', NOW())
        """, approval_id, task.action, json.dumps(task.data))
        return approval_id

    async def approve(self, approval_id: str, user_id: str):
        """Process approval"""
        await self.db.execute("""
            UPDATE approval_queue
            SET status = 'approved', approved_by = $2, approved_at = NOW()
            WHERE id = $1
        """, approval_id, user_id)

        # Execute approved task
        task = await self.get_task(approval_id)
        await self.execute_task(task)
```

#### Phase 3: Notification System

```python
class NotificationService:
    async def notify_pending_approval(self, task: Task):
        """Notification for TIER 3 task approval request"""
        await self.send_slack(f"Approval needed: {task.action}")
        await self.send_email(...)

    async def notify_tier2_review(self, task: Task, result: dict):
        """Notification for TIER 2 task result review"""
        await self.send_slack(f"Review needed: {task.action} completed")
```

### Database Schema

```sql
-- Approval queue table
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

-- Task log table
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

### API Endpoints

```python
# List pending approval tasks
@app.get("/api/v1/approvals/pending")
async def list_pending_approvals():
    ...

# Approve task
@app.post("/api/v1/approvals/{id}/approve")
async def approve_task(id: str, user: User = Depends(get_current_user)):
    ...

# Reject task
@app.post("/api/v1/approvals/{id}/reject")
async def reject_task(id: str, reason: str, user: User = Depends(get_current_user)):
    ...

# List pending TIER 2 reviews
@app.get("/api/v1/reviews/pending")
async def list_pending_reviews():
    ...
```

### Expected Benefits

| Aspect | Current | Target |
|--------|---------|--------|
| Safety | Low | High (approval required for risky tasks) |
| Speed | Fast | TIER 1/2 fast, only TIER 3 waits |
| Transparency | Low | High (all tasks logged) |
| Accountability | Unclear | Clear (approver recorded) |

---

## Priority

| Task | Priority | Estimated Duration | Reason |
|------|----------|-------------------|--------|
| Telegram real-time | High | 1-2 days | Library already available, high impact |
| Tiered Autonomy | Medium | 3-5 days | Improved safety, UI needed |
| RSS WebSub | Low | 2-3 days | Limited impact |
| Kafka introduction | Low | 5-7 days | Increased infrastructure complexity |

---

## References

### Event-Driven
- [Superfeedr WebSub](https://superfeedr.com/)
- [Apache Kafka Architecture 2025](https://kafka.apache.org/documentation/)
- [telegram-osint-lib](https://github.com/Postuf/telegram-osint-lib)

### Tiered Autonomy
- [Deloitte: Autonomous AI Agents 2025](https://www.deloitte.com/...)
- [Human-on-the-Loop vs Human-in-the-Loop](https://skywork.ai/blog/...)
- [AI Agent Autonomy Levels](https://arxiv.org/html/2502.02649v3)

---

*Created: 2026-01-12*
*Status: Planning stage*
