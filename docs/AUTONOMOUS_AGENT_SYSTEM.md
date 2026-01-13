# Livemap Autonomous Intelligence System

> **실시간 글로벌 이벤트 감지 및 자율 조사 플랫폼**
>
> 다중 소스 모니터링 + 지능형 감지 레이어 + Deep Verification 에이전트

---

## 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 4.0 | 2026-01-12 | 다중 소스 + 감지 레이어 |
| **5.0** | **2026-01-13** | **Production-Ready Deep Verification Agent** |

### v5.0 주요 변경사항
- Deep Verification Agent v2.0 (Perplexity + GPT-Researcher 스타일)
- 병렬 서브토픽 리서치 (`asyncio.gather()`)
- Rate Limiting, Retry, Timeout 프로덕션 기능
- 레거시 파이프라인 완전 제거 (Stage 0-3)

---

## Executive Summary

| 지표 | 값 |
|------|-----|
| **월 운영 비용** | ~$20 (vs 경쟁사 $10K-$200K) |
| **이벤트 감지 지연** | <15분 (GDELT), 실시간 (Telegram) |
| **조사 시간** | ~65초 (Deep Verification) |
| **언어 지원** | 100+ (BGE-M3 다국어 임베딩) |
| **데이터 소스** | 100,000+ 뉴스 소스 + 소셜 미디어 |

**핵심 차별점**: 기존 OSINT 플랫폼(Palantir, Dataminr)은 연간 $200K-$2.4M.
우리 시스템은 **동일 기능을 $240/년**에 제공 (99% 비용 절감).

---

## 1. 시스템 아키텍처

### 1.1 전체 구조

```
┌─────────────────────────────────────────────────────────────────────┐
│                      TRIGGER LAYER                                   │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐              │
│   │   GDELT     │   │  Telegram   │   │  X/Twitter  │              │
│   │  100K+ 소스 │   │  OSINT채널  │   │   (Twikit)  │              │
│   │   무료      │   │   무료      │   │   무료      │              │
│   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘              │
│          └─────────────────┴─────────────────┘                      │
│                            │                                        │
│                   TriggerManager                                    │
│               (병렬 스캔 + 중복 제거)                                │
├─────────────────────────────────────────────────────────────────────┤
│                    DETECTION LAYER                                   │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │  Layer 1: Keyword Matching (알려진 위협)                      │  │
│   │  Layer 2: Anomaly Detection (볼륨 스파이크)                   │  │
│   │  Layer 3: Semantic Clustering (새로운 주제)                   │  │
│   └─────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                   CLASSIFICATION LAYER                               │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │  LLM Classification (GPT-4o-mini)                            │  │
│   │  카테고리: war, protest, terrorism, military, violence       │  │
│   └─────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                   INVESTIGATION LAYER                                │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │  Deep Verification Agent v2.0 (Production-Ready)             │  │
│   │                                                              │  │
│   │  DECOMPOSER → PARALLEL_RESEARCHER → VERIFIER → SYNTHESIZER  │  │
│   │                      ↓                                       │  │
│   │              asyncio.gather()                                │  │
│   │              Rate Limiting                                   │  │
│   │              Retry + Timeout                                 │  │
│   └─────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                      OUTPUT LAYER                                    │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │  Verified Report                                             │  │
│   │  - 요약 + 타임라인                                           │  │
│   │  - Verified Facts (2+ 소스)                                  │  │
│   │  - Disputed Claims (충돌 정보)                               │  │
│   │  - 출처 목록 (URL)                                           │  │
│   └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 데이터 흐름

```
1. 트리거 발생
   GDELT/Telegram → 키워드 매칭 → 이벤트 감지

2. 감지 레이어 실행
   이벤트들 → Anomaly Detection → 볼륨 스파이크?
            → Semantic Clustering → 새 클러스터?

3. LLM 분류
   감지된 이벤트 → GPT-4o-mini → 카테고리 + 중요도

4. Deep Verification (중요 이벤트만)
   중요 이벤트 → 쿼리 분해 → 병렬 리서치 → 교차 검증 → 리포트

5. 리포트 발행
   검증된 정보 → 종합 리포트 → Feed DB 저장
```

---

## 2. Deep Verification Agent

### 2.1 아키텍처 (Perplexity + GPT-Researcher 스타일)

```
┌───────────────┐
│  DECOMPOSER   │  쿼리를 3-5개 서브토픽으로 분해
└───────┬───────┘
        ▼
┌───────────────────────────────────────────────────────────────────┐
│                    PARALLEL RESEARCHER                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │
│  │ Subtopic 1  │  │ Subtopic 2  │  │ Subtopic 3  │               │
│  │   ReAct     │  │   ReAct     │  │   ReAct     │               │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │
│         └────────────────┴────────────────┘                       │
│                   asyncio.gather()                                 │
└───────────────────────────┬───────────────────────────────────────┘
                            ▼
┌───────────────┐
│   VERIFIER    │  교차 검증 + 충돌 탐지
└───────┬───────┘
        ▼
┌───────────────┐
│  SYNTHESIZER  │  최종 리포트 생성
└───────────────┘
```

### 2.2 프로덕션 기능

| 기능 | 구현 | 설명 |
|------|------|------|
| **Rate Limiting** | `asyncio.Semaphore` | 동시 검색 5개, LLM 3개 제한 |
| **Retry** | `tenacity` | 최대 3회, Exponential Backoff |
| **Timeout** | `asyncio.wait_for()` | Tool 30초, LLM 60초 |
| **Deduplication** | URL 정규화 + MD5 | 중복 소스 제거 |

### 2.3 성능

| 지표 | v1.0 (Sequential) | v2.0 (Production) |
|------|-------------------|-------------------|
| 실행 시간 | 125.6 sec | **64.9 sec** (-48%) |
| Verified Facts | 9 | 9 |
| Unique Sources | 60 (중복) | 31 (고유) |
| Rate Limit 처리 | Crash | Retry |
| Timeout 처리 | Hang | Graceful |

---

## 3. 데이터 소스

### 3.1 다중 소스 트리거

| 소스 | 라이브러리 | 커버리지 | 지연 | 비용 |
|------|-----------|---------|------|------|
| **GDELT** | gdeltdoc | 100,000+ 뉴스 소스 | 15분 | $0 |
| **Telegram** | Telethon | OSINT 채널 | 실시간 | $0 |
| **X/Twitter** | Twikit | 글로벌 실시간 | 실시간 | $0 |

### 3.2 검색 도구 우선순위

```python
ALL_TOOLS = [
    # FREE - 우선 사용
    search_news_gdelt,   # GDELT 뉴스 검색
    search_web_free,     # DuckDuckGo (무료)
    search_telegram,     # Telegram 채널
    search_youtube,      # YouTube 영상

    # PAID - Fallback
    search_web,          # Tavily (유료)
]
```

---

## 4. 비용 분석

### 4.1 경쟁사 대비

| 솔루션 | 연간 비용 | 우리 대비 |
|--------|----------|----------|
| Palantir | $173K+ | 720x |
| Dataminr | $120K-$2.4M | 500-10,000x |
| Recorded Future | $200K+ | 833x |
| **우리 시스템** | **$240** | 1x |

### 4.2 우리 시스템 비용 상세

| 컴포넌트 | 월 비용 | 비고 |
|----------|--------|------|
| GDELT | $0 | 무료 |
| Telegram | $0 | 무료 |
| DuckDuckGo | $0 | 무료 |
| LLM (GPT-4o-mini) | ~$10 | 하루 100건 기준 |
| Tavily (fallback) | $0-$20 | 무료 1,000건/월 |
| **총계** | **~$20** | |

---

## 5. 기술 스택

### 5.1 핵심 라이브러리

| 컴포넌트 | 기술 | 버전 |
|----------|------|------|
| **오케스트레이션** | LangGraph | >=0.2.0 |
| **LLM** | langchain-openai | >=0.2.0 |
| **뉴스 수집** | gdeltdoc | latest |
| **Telegram** | Telethon | >=1.42.0 |
| **웹 검색** | duckduckgo-search | >=7.0.0 |
| **Retry** | tenacity | >=8.2.0 |

### 5.2 인프라

| 컴포넌트 | 기술 |
|----------|------|
| Backend | FastAPI (Python 3.11+) |
| Database | PostgreSQL + pgvector |
| Deployment | Docker Compose |

---

## 6. 프로젝트 구조

```
app/
├── core/                      # 공유 인프라
│   ├── config.py              # 환경변수 설정
│   ├── database.py            # DB 연결
│   └── lifespan.py            # 앱 시작/종료
├── agent/                     # 자율 에이전트 시스템
│   ├── graph/                 # LangGraph 상태
│   │   └── state.py
│   ├── tools/                 # 검색 도구
│   │   ├── search.py          # GDELT, Tavily, DuckDuckGo
│   │   ├── social.py          # Telegram, YouTube
│   │   └── media.py           # Video download
│   ├── triggers/              # 다중 소스 트리거
│   │   ├── gdelt.py
│   │   ├── telegram.py
│   │   └── manager.py
│   ├── scanner.py             # 이벤트 스캐너
│   ├── investigator.py        # V1 에이전트
│   └── investigator_v2.py     # V2 Deep Verification
├── api/v1/
│   └── routes/
│       ├── feeds.py           # Feed CRUD
│       └── agent.py           # Agent API
├── models/
│   └── feed.py
└── schemas/
    ├── feed.py
    └── agent.py
```

---

## 7. API 엔드포인트

### 7.1 Agent API

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/agent/investigate` | 주제 조사 시작 |
| GET | `/api/v1/agent/status/{id}` | 조사 상태 확인 |
| POST | `/api/v1/agent/scan` | 다중 소스 스캔 |

### 7.2 Feed API

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/v1/feeds` | 피드 목록 |
| GET | `/api/v1/feeds/{id}` | 피드 상세 |
| POST | `/api/v1/feeds` | 피드 생성 |

---

## 참고 문헌

### 아키텍처 참고
- [Perplexity Deep Research](https://www.perplexity.ai/hub/blog/introducing-perplexity-deep-research)
- [GPT-Researcher](https://github.com/assafelovic/gpt-researcher)
- [LangGraph ReAct](https://langchain-ai.github.io/langgraph/concepts/agentic_concepts/)

### 프로덕션 패턴
- [AWS Exponential Backoff](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
- [Python asyncio Semaphore](https://docs.python.org/3/library/asyncio-sync.html)
- [tenacity Documentation](https://tenacity.readthedocs.io/)

### 시장 조사
- Mordor Intelligence, "Open Source Intelligence Market" (2024)
- Vendr, "Dataminr Pricing" (2024)

---

*최종 업데이트: 2026-01-13*
*버전: 5.0 (Production-Ready Deep Verification)*
