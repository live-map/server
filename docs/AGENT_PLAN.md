# Livemap 자율 조사 에이전트 설계

> **목표**: 15-30분 주기로 국제 정세 뉴스를 스캔하고, 사건 발생 시 **에이전트가 스스로 판단**하여 필요한 소스를 찾고, 영상/사진/기사를 수집하여 웰메이드한 리포트를 생성하는 자율 조사 에이전트

---

## 1. 핵심 개념: 자율적 조사 에이전트

### 기존 방식 vs 자율 에이전트

```
❌ 기존 방식 (고정 파이프라인):
   사용자가 정의 → Stage 1 → Stage 2 → Stage 3 → 결과
   문제: 유연성 없음, 새로운 소스 대응 불가

✅ 자율 에이전트 방식:
   뉴스 트리거 → 에이전트가 판단 → 필요한 곳 어디든 조사 → 결과
   장점: 에이전트가 상황에 맞게 어디서 뭘 찾을지 결정
```

### 작동 예시: "이란 시위 발생"

```
1. [트리거] NewsAPI에서 "이란 시위" 감지

2. [에이전트 판단] "이란 시위 조사에 필요한 소스는?"
   → Iran International (이란 전문 뉴스)
   → 텔레그램 이란 채널들
   → BBC Persian, VOA Farsi
   → Twitter/X 현지 기자들
   → Reuters, AP (국제 통신사)

3. [실행] 각 소스에서 정보 수집
   → 뉴스 기사 5개
   → 텔레그램 영상 3개
   → 트윗 10개
   → 관련 이미지 7장

4. [검증] 수집된 정보 교차 검증
   → 2개 이상 소스에서 확인된 내용만 채택

5. [리포트] 종합 보고서 생성
   → 요약, 타임라인, 미디어, 출처 명시
```

---

## 2. 검증된 아키텍처: GPT Researcher 패턴

### 2.1 Planner-Executor-Publisher

**GPT Researcher** (카네기멜론 벤치마크 1위, 2분/$0.005)의 핵심 패턴:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    자율 조사 에이전트 아키텍처                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌─────────────────────────────────────────────────────────┐       │
│   │  1. PLANNER (전략 LLM - Claude/GPT-4o)                  │       │
│   │                                                         │       │
│   │  입력: "이란에서 대규모 시위 발생"                       │       │
│   │                                                         │       │
│   │  출력: 조사 계획                                        │       │
│   │  - Q1: 시위 규모와 위치는?                             │       │
│   │  - Q2: 시위 원인은?                                    │       │
│   │  - Q3: 정부 대응은?                                    │       │
│   │  - Q4: 사상자 보고가 있는가?                           │       │
│   │  - Sources: Iran Intl, BBC Persian, Telegram          │       │
│   └─────────────────────────────────────────────────────────┘       │
│                            │                                        │
│                            ▼                                        │
│   ┌─────────────────────────────────────────────────────────┐       │
│   │  2. EXECUTOR (병렬 에이전트들)                          │       │
│   │                                                         │       │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │       │
│   │  │ Web      │ │ Telegram │ │ Twitter  │ │ Video    │   │       │
│   │  │ Searcher │ │ Crawler  │ │ Monitor  │ │ Finder   │   │       │
│   │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘   │       │
│   │       │            │            │            │         │       │
│   │       └────────────┴────────────┴────────────┘         │       │
│   │                            │                            │       │
│   │                   수집된 원시 데이터                     │       │
│   └─────────────────────────────────────────────────────────┘       │
│                            │                                        │
│                            ▼                                        │
│   ┌─────────────────────────────────────────────────────────┐       │
│   │  3. VERIFIER (검증 에이전트)                            │       │
│   │                                                         │       │
│   │  - 2개 이상 독립 소스에서 확인?                         │       │
│   │  - 시간/위치 일관성 체크                               │       │
│   │  - 출처 신뢰도 평가                                    │       │
│   │  - 충돌하는 정보 플래그                                │       │
│   └─────────────────────────────────────────────────────────┘       │
│                            │                                        │
│                            ▼                                        │
│   ┌─────────────────────────────────────────────────────────┐       │
│   │  4. PUBLISHER (리포트 생성)                             │       │
│   │                                                         │       │
│   │  - 종합 요약                                           │       │
│   │  - 타임라인                                            │       │
│   │  - 검증된 미디어 (영상/사진)                           │       │
│   │  - 모든 출처 명시                                      │       │
│   │  - 불확실한 정보 별도 표시                             │       │
│   └─────────────────────────────────────────────────────────┘       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 ReAct 패턴 (자율적 판단의 핵심)

**ReAct** = Reasoning + Acting (할루시네이션 6%로 감소)

```python
# ReAct 루프 - 에이전트가 스스로 다음 행동 결정
while not done:
    # 1. OBSERVE: 현재 상황 파악
    observation = get_current_state()

    # 2. REASON: 다음에 뭘 해야 할지 생각
    thought = llm.reason(f"""
        현재까지 수집한 정보: {observation}
        아직 답하지 못한 질문: {unanswered_questions}

        다음에 무엇을 해야 할까?
        - 더 검색이 필요한가?
        - 어떤 소스를 확인해야 하는가?
        - 충분한 정보가 모였는가?
    """)

    # 3. ACT: 결정된 행동 실행
    if thought.action == "search_telegram":
        result = telegram_tool.search(thought.query)
    elif thought.action == "search_news":
        result = news_tool.search(thought.query)
    elif thought.action == "finish":
        done = True

    # 4. 결과를 바탕으로 다시 OBSERVE
```

---

## 3. 기술 스택 (2026년 기준)

### 3.1 핵심 프레임워크

| 컴포넌트 | 기술 | 이유 |
|----------|------|------|
| **오케스트레이션** | LangGraph | 상태 관리, 체크포인팅, Plan-and-Execute 패턴 |
| **에이전트 협업** | CrewAI (선택) | 역할 기반 에이전트 팀 구성 |
| **도구 통합** | MCP (Model Context Protocol) | 업계 표준, 97M+ 월간 다운로드 |
| **LLM** | Claude 4.5 / GPT-4o | 추론용 (비쌈) |
| **LLM** | GPT-4o-mini / Mistral | 루틴 작업용 (저렴) |

### 3.2 데이터 수집 도구

| 소스 | 도구 | 특징 |
|------|------|------|
| **웹 검색** | [Tavily](https://tavily.com/) | AI 에이전트용 설계, 20개 사이트/1 API |
| **뉴스** | [NewsAPI.ai](https://newsapi.ai/) | 15만+ 글로벌 퍼블리셔 |
| **텔레그램** | Telethon/Pyrogram | 공식 API, 무료 |
| **Twitter/X** | Twscrape (비공식) | 무료, 위험 있음 |
| **영상** | yt-dlp | YouTube, Twitter 영상 다운로드 |
| **이미지** | Google Images API / SerpAPI | 관련 이미지 검색 |

### 3.3 검증 도구

| 기능 | 도구 | 용도 |
|------|------|------|
| **NLI** | mDeBERTa-v3 | 주장-증거 매칭 |
| **중복 감지** | BGE-M3 | 같은 사건 다른 보도 연결 |
| **이미지 검증** | Google Vision / TinEye | 역이미지 검색 |
| **영상 분석** | MMCTAgent 패턴 | 영상 내 정보 추출 |

---

## 4. 구현 설계

### 4.1 15-30분 주기 스캐너

```python
# news_scanner.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

async def scan_breaking_news():
    """15분마다 실행되는 뉴스 스캐너"""

    # 1. 뉴스 API에서 최근 뉴스 가져오기
    news = await news_api.get_latest(
        categories=["conflict", "protest", "military", "terrorism"],
        languages=["en", "fa", "ar", "ru", "uk"],
        since_minutes=30
    )

    # 2. 중요 사건 필터링 (LLM 판단)
    significant_events = await llm.filter_significant(news)

    # 3. 새로운 사건이면 조사 에이전트 트리거
    for event in significant_events:
        if not await is_already_investigated(event):
            await trigger_investigation(event)

scheduler = AsyncIOScheduler()
scheduler.add_job(scan_breaking_news, 'interval', minutes=15)
```

### 4.2 자율 조사 에이전트 (LangGraph)

```python
# investigation_agent.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

class InvestigationState(TypedDict):
    event: str                    # 트리거된 사건
    plan: list[str]              # 조사 계획 (질문들)
    collected_data: list[dict]   # 수집된 데이터
    verified_facts: list[dict]   # 검증된 사실
    report: str                  # 최종 리포트
    iteration: int               # 현재 반복 횟수

def planner(state: InvestigationState) -> InvestigationState:
    """에이전트가 조사 계획을 스스로 수립"""

    plan = llm.generate(f"""
        사건: {state['event']}

        이 사건을 조사하기 위해 답해야 할 핵심 질문들을 생성하세요.
        또한 각 질문에 답하기 위해 어떤 소스를 확인해야 할지 제안하세요.

        출력 형식:
        - 질문: [질문]
          소스: [제안 소스들]
    """)

    state['plan'] = parse_plan(plan)
    return state

def executor(state: InvestigationState) -> InvestigationState:
    """계획에 따라 데이터 수집 (병렬)"""

    tasks = []
    for question in state['plan']:
        # 에이전트가 결정한 소스에서 검색
        for source in question['sources']:
            if source == 'telegram':
                tasks.append(telegram_search(question['query']))
            elif source == 'news':
                tasks.append(news_search(question['query']))
            elif source == 'twitter':
                tasks.append(twitter_search(question['query']))
            # ... 에이전트가 필요하다고 판단한 모든 소스

    results = await asyncio.gather(*tasks)
    state['collected_data'].extend(results)
    return state

def verifier(state: InvestigationState) -> InvestigationState:
    """수집된 데이터 교차 검증"""

    verified = []
    for claim in extract_claims(state['collected_data']):
        # 2개 이상 독립 소스에서 확인
        supporting_sources = find_supporting_sources(claim, state['collected_data'])
        if len(supporting_sources) >= 2:
            verified.append({
                'claim': claim,
                'sources': supporting_sources,
                'confidence': calculate_confidence(supporting_sources)
            })

    state['verified_facts'] = verified
    return state

def should_continue(state: InvestigationState) -> str:
    """더 조사가 필요한지 에이전트가 판단"""

    decision = llm.decide(f"""
        원래 사건: {state['event']}
        수집된 데이터: {len(state['collected_data'])}개
        검증된 사실: {len(state['verified_facts'])}개
        반복 횟수: {state['iteration']}

        충분한 정보가 모였는가?
        아니면 추가 조사가 필요한가?
        (최대 3회 반복)
    """)

    if decision == "enough" or state['iteration'] >= 3:
        return "publish"
    else:
        return "replan"

def publisher(state: InvestigationState) -> InvestigationState:
    """최종 리포트 생성"""

    report = llm.generate(f"""
        검증된 사실들을 바탕으로 종합 리포트를 작성하세요.

        포함 항목:
        1. 요약 (2-3문장)
        2. 상세 내용
        3. 타임라인 (시간순)
        4. 관련 미디어 (영상/사진 링크)
        5. 출처 목록
        6. 불확실한 정보 (검증 안 된 것)

        검증된 사실: {state['verified_facts']}
    """)

    state['report'] = report
    return state

# 그래프 구성
graph = StateGraph(InvestigationState)
graph.add_node("plan", planner)
graph.add_node("execute", executor)
graph.add_node("verify", verifier)
graph.add_node("publish", publisher)

graph.add_edge("plan", "execute")
graph.add_edge("execute", "verify")
graph.add_conditional_edges("verify", should_continue, {
    "replan": "plan",
    "publish": "publish"
})
graph.add_edge("publish", END)

graph.set_entry_point("plan")
agent = graph.compile(checkpointer=MemorySaver())
```

### 4.3 도구 정의 (MCP 스타일)

```python
# tools.py
from langchain.tools import tool

@tool
def search_telegram(query: str, channels: list[str] = None) -> list[dict]:
    """
    텔레그램 채널에서 관련 메시지 검색

    Args:
        query: 검색어
        channels: 검색할 채널 목록 (없으면 에이전트가 자동 선택)

    Returns:
        메시지 목록 (텍스트, 미디어 URL, 날짜, 채널명)
    """
    if not channels:
        # 에이전트가 쿼리 기반으로 관련 채널 자동 선택
        channels = llm.select_channels(query)

    return telegram_client.search(query, channels)

@tool
def search_news(query: str, sources: list[str] = None) -> list[dict]:
    """
    뉴스 기사 검색

    Args:
        query: 검색어
        sources: 특정 소스 (없으면 모든 소스)

    Returns:
        기사 목록 (제목, 본문, URL, 날짜, 소스)
    """
    return news_api.search(query, sources=sources)

@tool
def download_video(url: str) -> dict:
    """
    영상 다운로드 (YouTube, Twitter, Telegram 등)

    Args:
        url: 영상 URL

    Returns:
        로컬 파일 경로, 메타데이터
    """
    return yt_dlp.download(url)

@tool
def reverse_image_search(image_url: str) -> list[dict]:
    """
    역이미지 검색으로 이미지 출처 확인

    Args:
        image_url: 이미지 URL

    Returns:
        유사 이미지 목록 (URL, 날짜, 사이트)
    """
    return tineye.search(image_url)

@tool
def translate(text: str, target_lang: str = "en") -> str:
    """
    텍스트 번역 (페르시아어, 아랍어, 러시아어 등)
    """
    return translator.translate(text, target=target_lang)
```

---

## 5. 참고 오픈소스

### 5.1 GPT Researcher
- **GitHub**: [github.com/assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher)
- **성능**: 2분 조사, $0.005/건, 카네기멜론 벤치마크 1위
- **활용**: 전체 아키텍처 패턴 참고

### 5.2 ByteDance DeerFlow
- **GitHub**: [github.com/bytedance/deer-flow](https://github.com/bytedance/deer-flow)
- **성능**: 93%+ 정확도, 멀티모달 출력 (슬라이드, 팟캐스트)
- **활용**: LangGraph 기반 멀티 에이전트 구조 참고

### 5.3 Stanford STORM
- **GitHub**: [github.com/stanford-oval/storm](https://github.com/stanford-oval/storm)
- **성능**: 84.83% 인용 재현율, 다중 관점 수집
- **활용**: 다양한 관점 수집 방법론 참고

### 5.4 LangGraph Telegram Research Agent
- **글**: [Medium - AI Agent Reads 100s of Telegram Channels](https://medium.com/@gzozulin/my-ai-agent-reads-100s-of-telegram-channels-so-i-dont-have-to-langgraph-s-deep-research-5df41506cb29)
- **활용**: 텔레그램 모니터링 구현 참고

---

## 6. 구현 로드맵

### Phase 1: 핵심 에이전트 (MVP)

| 작업 | 세부 내용 |
|------|-----------|
| 1. 뉴스 스캐너 | NewsAPI.ai + 15분 주기 |
| 2. 기본 조사 에이전트 | LangGraph + ReAct 패턴 |
| 3. 웹 검색 도구 | Tavily 통합 |
| 4. 리포트 생성 | LLM 기반 종합 |

### Phase 2: 소스 확장

| 작업 | 세부 내용 |
|------|-----------|
| 1. 텔레그램 통합 | Telethon, 주요 채널 목록 |
| 2. Twitter/X 통합 | Twscrape (비공식) |
| 3. 영상 수집 | yt-dlp 통합 |
| 4. 이미지 수집 | SerpAPI 이미지 검색 |

### Phase 3: 검증 강화

| 작업 | 세부 내용 |
|------|-----------|
| 1. NLI 검증 | mDeBERTa 통합 |
| 2. 중복 감지 | BGE-M3 임베딩 |
| 3. 역이미지 검색 | TinEye/Google Vision |
| 4. 소스 신뢰도 | 채널/도메인 점수 |

### Phase 4: 프로덕션

| 작업 | 세부 내용 |
|------|-----------|
| 1. 웹 대시보드 | 실시간 리포트 뷰 |
| 2. 알림 시스템 | 중요 사건 푸시 |
| 3. 히스토리 | 과거 조사 아카이브 |
| 4. API | 외부 서비스 연동 |

---

## 7. 비용 추정

| 항목 | 월 비용 | 비고 |
|------|---------|------|
| Claude/GPT-4o (Planner) | $20-50 | 하루 ~20회 조사 기준 |
| GPT-4o-mini (Executor) | $5-10 | 루틴 작업 |
| Tavily API | $0 (무료 티어) or $50 | 1,000회/월 무료 |
| NewsAPI.ai | $0 (무료) or $49 | 비즈니스 플랜 |
| 서버 (VPS) | $20-50 | |
| **총계** | **$45-160/월** | |

---

## 8. 핵심 원칙

1. **에이전트가 결정한다**: 사용자가 프로세스를 정하지 않음
2. **상황에 맞게 적응**: 이란 시위 → Iran International, 우크라이나 → Liveuamap 소스
3. **2개 이상 독립 소스**: 검증 없이 게시하지 않음
4. **불확실성 표시**: 검증 안 된 건 별도 표시
5. **출처 항상 명시**: 모든 정보에 원 출처 포함

---

## 참고 자료

### 프레임워크
- [LangGraph 공식](https://www.langchain.com/langgraph)
- [CrewAI 공식](https://www.crewai.com/)
- [MCP 스펙](https://modelcontextprotocol.io/)

### 논문/블로그
- [ReAct Paper](https://arxiv.org/abs/2210.03629)
- [Plan-and-Execute - LangChain](https://blog.langchain.com/planning-agents/)
- [GPT Researcher 문서](https://gptr.dev/)

### 도구
- [Tavily](https://tavily.com/)
- [NewsAPI.ai](https://newsapi.ai/)
- [Telethon 문서](https://docs.telethon.dev/)

---

*작성일: 2026-01-12*
