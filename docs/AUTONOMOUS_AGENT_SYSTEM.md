# Livemap Autonomous Intelligence System

> **실시간 글로벌 이벤트 감지 및 자율 조사 플랫폼**
>
> 다중 소스 모니터링 + 지능형 감지 레이어 + 자율 조사 에이전트

---

## Executive Summary

| 지표 | 값 |
|------|-----|
| **월 운영 비용** | ~$20 (vs 경쟁사 $10K-$200K) |
| **이벤트 감지 지연** | <15분 (GDELT), 실시간 (X/Telegram) |
| **언어 지원** | 100+ (BGE-M3 다국어 임베딩) |
| **데이터 소스** | 100,000+ 뉴스 소스 + 소셜 미디어 |
| **감지 방식** | 키워드 + 이상 감지 + 의미적 클러스터링 |

**핵심 차별점**: 기존 OSINT 플랫폼(Palantir, Dataminr)은 연간 $200K-$2.4M.
우리 시스템은 **동일 기능을 $240/년**에 제공 (99% 비용 절감).

---

## 1. 시장 기회

### 1.1 OSINT 시장 규모

| 연도 | 시장 규모 | CAGR | 출처 |
|------|----------|------|------|
| 2024 | $18.2B | - | Mordor Intelligence |
| 2030 | $38B | 15.9% | Mordor Intelligence |
| 2035 | $76.8B | 20.7% | Market Research Future |

**주요 성장 동력:**
- 소셜 미디어 분석: 시장 점유율 42.6%
- 클라우드 기반 솔루션: 66.5% 점유율
- 다크웹/딥웹 모니터링: CAGR 23.8%

### 1.2 경쟁사 비용 구조

| 솔루션 | 연간 비용 | 사용자당 비용 | 출처 |
|--------|----------|--------------|------|
| **Palantir** | $141K+ (기본) | - | GSA 가격표 |
| **Dataminr** | $120K-$2.4M | $10K-$20K | Vendr |
| **Recorded Future** | $200K+ | 커스텀 | 공식 사이트 |
| **Meltwater** | $40K-$100K | $5K-$15K | Prowly |
| **우리 시스템** | **$240** | **$20** | 자체 계산 |

---

## 2. 아키텍처 진화 히스토리

### 왜 이렇게 만들었는가?

```
v1 (고정 파이프라인)
    ↓ 문제: "유연성 없음, 새 소스 대응 불가"
v2 (RSS 피드 + 자율 에이전트)
    ↓ 문제: "소스를 내가 정하는 것 = 자율 아님"
v3 (GDELT 키워드 검색)
    ↓ 문제: "뉴스만, 실시간 아님 (15분 딜레이)"
v4 (다중 소스 + 감지 레이어) ← 현재
    ✓ 해결: 다중 소스, 실시간, 키워드 없이도 감지
```

### v1 → v2: 고정 파이프라인의 한계

**문제**: Stage 1 → 2 → 3 순서 고정, 새로운 유형의 사건 대응 불가

**해결**: GPT Researcher 패턴의 자율 에이전트 도입
- Planner-Executor-Publisher 구조
- ReAct (Reasoning + Acting) 루프
- 에이전트가 스스로 소스 선택

### v2 → v3: RSS 피드의 한계

**문제**: Reuters, BBC 같은 고정 소스 = 내가 소스를 정하는 것

**해결**: GDELT DOC API로 전환
- 100,000+ 글로벌 뉴스 소스
- 키워드 기반 자동 검색
- 소스 하드코딩 제거

### v3 → v4: 단일 소스의 한계

**문제**:
- GDELT는 뉴스만 (소셜 미디어 없음)
- 15분 딜레이 (실시간 아님)
- 트럼프가 X에 글 올리면 뉴스 기사 나올 때까지 대기

**해결**: 다중 소스 병렬 트리거
- GDELT (뉴스, 15분)
- X/Twitter (실시간, Twikit)
- Telegram (실시간, Telethon)

### v4 추가: 키워드 매칭의 한계

**문제**:
- "war", "protest" 키워드에 없는 새로운 유형의 사건은?
- 암호화된 언어, 신조어는?
- 예상 못한 방식으로 표현된 사건은?

**해결**: 감지 레이어 추가
- Anomaly Detection: 볼륨/속도 스파이크 감지
- Semantic Clustering: 새로운 주제 클러스터 자동 감지

---

## 3. 시스템 아키텍처

### 3.1 전체 구조

```
┌─────────────────────────────────────────────────────────────────────┐
│                      TRIGGER LAYER                                  │
│                                                                     │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐              │
│   │   GDELT     │   │  X/Twitter  │   │  Telegram   │              │
│   │   (뉴스)    │   │   (Twikit)  │   │ (Telethon)  │              │
│   │  100K+ 소스 │   │   실시간    │   │  OSINT채널  │              │
│   │   무료      │   │   무료      │   │   무료      │              │
│   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘              │
│          │                 │                 │                      │
│          └─────────────────┴─────────────────┘                      │
│                            │                                        │
│                   TriggerManager                                    │
│               (병렬 스캔 + 중복 제거)                                │
├─────────────────────────────────────────────────────────────────────┤
│                    DETECTION LAYER                                  │
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │  Layer 1: Keyword Matching                                   │  │
│   │           "war", "protest", "violence" 등                    │  │
│   │           알려진 위협 감지                                    │  │
│   ├─────────────────────────────────────────────────────────────┤  │
│   │  Layer 2: Anomaly Detection                                  │  │
│   │           볼륨/속도 스파이크 감지 (Z-Score 2.5σ)             │  │
│   │           키워드 없이도 "변화" 감지                          │  │
│   │           연구 결과: AUC 86.6% ~ 98.79%                      │  │
│   ├─────────────────────────────────────────────────────────────┤  │
│   │  Layer 3: Semantic Clustering                                │  │
│   │           BGE-M3 임베딩 (100+ 언어, 1024dim)                │  │
│   │           새 클러스터 = 새로운 주제 출현                     │  │
│   │           연구 결과: ARI 0.57-0.78                           │  │
│   └─────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                   CLASSIFICATION LAYER                              │
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │  LLM Classification (GPT-4o-mini)                           │  │
│   │  - 카테고리: war, protest, terrorism, military, violence    │  │
│   │  - 중요도 평가: significant / not significant               │  │
│   │  - 연구 결과: F1 0.88-0.94                                  │  │
│   └─────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                   INVESTIGATION LAYER                               │
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │  Autonomous Investigation Agent (LangGraph)                  │  │
│   │                                                              │  │
│   │  ReAct Loop:                                                 │  │
│   │  1. Observe → 2. Reason → 3. Act → 4. Observe → ...         │  │
│   │                                                              │  │
│   │  Tools:                                                      │  │
│   │  - search_web (Tavily)                                       │  │
│   │  - search_telegram                                           │  │
│   │  - search_youtube                                            │  │
│   │  - download_video (yt-dlp)                                   │  │
│   │  - translate                                                 │  │
│   └─────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                      OUTPUT LAYER                                   │
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │  Report Generation                                           │  │
│   │  - 요약 (2-3문장)                                           │  │
│   │  - 타임라인                                                  │  │
│   │  - 검증된 미디어 (영상/사진)                                │  │
│   │  - 출처 목록 (최소 2개 독립 소스)                           │  │
│   │  - 불확실한 정보 별도 표시                                  │  │
│   └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 데이터 흐름

```
1. 트리거 발생
   GDELT/X/Telegram → 키워드 매칭 → 이벤트 감지

2. 감지 레이어 실행
   이벤트들 → Anomaly Detection → 볼륨 스파이크?
            → Semantic Clustering → 새 클러스터?

3. LLM 분류
   감지된 이벤트 → GPT-4o-mini → 카테고리 + 중요도

4. 자율 조사 (중요 이벤트만)
   중요 이벤트 → LangGraph Agent → 다중 소스 조사 → 교차 검증

5. 리포트 생성
   검증된 정보 → 종합 리포트 → 발행
```

---

## 4. 핵심 컴포넌트 상세

### 4.1 다중 소스 트리거

| 소스 | 라이브러리 | 커버리지 | 지연 | 비용 |
|------|-----------|---------|------|------|
| **GDELT** | gdeltdoc | 100,000+ 뉴스 소스, 65개 언어 | 15분 | $0 |
| **X/Twitter** | Twikit | 글로벌 실시간 | 실시간 | $0 |
| **Telegram** | Telethon | 가입 채널 | 실시간 | $0 |

**GDELT 상세:**
- 주류 미디어 커버리지: 94.4% (Alexa Top 500)
- 언어: 65개 (98.4% 비영어 볼륨)
- 이벤트 리포팅: 97%+ 24시간 내
- 역사 데이터: 1979년~현재

**X/Twitter (Twikit):**
- 공식 API: $42,000/월 (Enterprise)
- Twikit: $0 (개인 계정 쿠키 사용)
- ToS 위반 위험 → 부계정 권장

**Telegram (Telethon):**
- MTProto API (공식)
- 가입 채널만 검색 가능
- 권장 OSINT 채널: GeoConfirmed, WarMonitor3, IranIntl 등

### 4.2 Anomaly Detection

**알고리즘**: EWMA + Z-Score

```python
# 볼륨 스파이크 감지
z_score = (current - mean) / std
if abs(z_score) >= 2.5:  # 2.5σ 기준
    trigger_anomaly_alert()
```

**성능 벤치마크** (학술 연구):

| 방법 | 데이터셋 | AUC-ROC | 출처 |
|------|---------|---------|------|
| Variational Autoencoders | ECG5000 | 98.79% | SciTePress 2021 |
| DeepAnT | Various | Top performer | TimeEval |
| EncDec-AD | Various | Strong | VLDB 2022 |

**우리 시스템 목표**: AUC 85%+

### 4.3 Semantic Clustering

**임베딩 모델**: BAAI/bge-m3

| 특성 | 값 |
|------|-----|
| 언어 | 100+ |
| 차원 | 1024 |
| 컨텍스트 | 8192 토큰 |
| 방식 | Dense + Sparse + ColBERT |
| 성능 | SOTA on MIRACL/MKQA |

**클러스터링 알고리즘**: Incremental Clustering

```python
similarity = cosine_similarity(embedding, cluster.centroid)
if similarity >= 0.7:
    add_to_cluster()
elif similarity < 0.4:
    create_new_cluster()  # 새로운 주제 발견!
```

**성능 벤치마크** (학술 연구):

| 데이터셋 | 모델 | ARI | NMI | 출처 |
|---------|------|-----|-----|------|
| MR Dataset | BERT Clustering | 0.784 | High | PeerJ 2023 |
| AG News | BERT Clustering | 0.574 | Moderate | PeerJ 2023 |

**우리 시스템 목표**: ARI 0.70+

### 4.4 LLM 분류

**모델**: GPT-4o-mini

| 특성 | 값 |
|------|-----|
| 입력 비용 | $0.15/1M 토큰 |
| 출력 비용 | $0.60/1M 토큰 |
| 정확도 | F1 0.88-0.94 (벤치마크) |

**분류 카테고리**:
- war: 무력 충돌, 군사 작전
- protest: 시위, 민중 봉기
- terrorism: 테러 공격, 폭발
- military: 군사 이동, 훈련
- violence: 일반 폭력, 사상자

### 4.5 자율 조사 에이전트

**프레임워크**: LangGraph

**패턴**: Plan-and-Execute (GPT Researcher 참고)

```
┌─────────────────────────────────────────────────────────────────┐
│                    ReAct Loop                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   1. OBSERVE: 현재까지 수집한 정보 파악                         │
│                    ↓                                            │
│   2. REASON: "다음에 뭘 해야 할까?"                             │
│              - 더 검색이 필요한가?                               │
│              - 어떤 소스를 확인해야 하는가?                      │
│              - 충분한 정보가 모였는가?                           │
│                    ↓                                            │
│   3. ACT: 결정된 행동 실행                                      │
│           - search_web()                                        │
│           - search_telegram()                                   │
│           - download_video()                                    │
│                    ↓                                            │
│   4. OBSERVE: 결과 확인 → 1번으로                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**벤치마크** (GPT Researcher):
- 조사 시간: ~5분
- 비용: ~$0.40/건
- 출력: 5-6페이지 리포트

---

## 5. 성능 지표

### 5.1 속도/지연

| 기능 | 업계 표준 | 우리 목표 |
|------|----------|----------|
| 뉴스 수집 지연 | 15-60분 | <15분 |
| 이벤트 감지 | 수 시간 | <30분 |
| 리포트 생성 | 5-30분 | <10분 |
| 알림 전달 | 분~시간 | 초~분 |

### 5.2 정확도

| 기능 | 업계 벤치마크 | 우리 목표 |
|------|-------------|----------|
| 뉴스 분류 | F1 0.88-0.95 | 0.92+ |
| 개체명 인식 (NER) | F1 0.956 | 0.93+ |
| 가짜 뉴스 감지 | 89-98% | 90%+ |
| 클러스터링 (ARI) | 0.57-0.78 | 0.70+ |
| 인용 정확도 | 93.9% (Perplexity) | 95%+ |

### 5.3 커버리지

| 데이터 소스 | 커버리지 |
|------------|---------|
| 글로벌 뉴스 (GDELT) | 94.4% 주류 미디어 |
| 언어 (BGE-M3) | 100+ |
| 소셜 플랫폼 | X, Telegram, (Bluesky, Mastodon 예정) |
| 뉴스 소스 | 100,000+ |

---

## 6. 비용 분석

### 6.1 경쟁사 대비 비용

| 솔루션 | 연간 비용 | 우리 대비 |
|--------|----------|----------|
| Palantir | $173K+ | 720x |
| Dataminr | $120K-$2.4M | 500-10,000x |
| Recorded Future | $200K+ | 833x |
| Meltwater | $40K-$100K | 167-417x |
| **우리 시스템** | **$240** | 1x |

### 6.2 우리 시스템 비용 상세

| 컴포넌트 | 월 비용 | 연간 비용 | 비고 |
|----------|--------|----------|------|
| GDELT | $0 | $0 | 무료 |
| X/Twitter (Twikit) | $0 | $0 | 무료 (개인계정) |
| Telegram (Telethon) | $0 | $0 | 무료 |
| LLM (GPT-4o-mini) | ~$10 | ~$120 | 하루 100건 기준 |
| Tavily (조사용) | $0-$20 | $0-$240 | 무료 1,000건/월 |
| **총계** | **~$20** | **~$240** | |

### 6.3 스케일업 시 비용

| 일일 처리량 | 월 비용 | 연간 비용 |
|------------|--------|----------|
| 100건 | ~$20 | ~$240 |
| 1,000건 | ~$100 | ~$1,200 |
| 10,000건 | ~$500 | ~$6,000 |
| 100,000건 | ~$2,000 | ~$24,000 |

**비교**: Dataminr 10사용자 = $120K/년 vs 우리 10,000건/일 = $6K/년

---

## 7. 기술적 차별점

### 7.1 vs 기존 OSINT 플랫폼 (Palantir, Dataminr)

| 기능 | Palantir/Dataminr | 우리 시스템 |
|------|-------------------|------------|
| 가격 | $100K+/년 | **$240/년** |
| 자율 조사 | 기본 알림 | **딥 리서치** |
| 커스터마이징 | 제한적 (비용 추가) | **완전 제어** |
| 셋업 시간 | 수 개월 | **수 일** |
| AI 연구 깊이 | 패시브 모니터링 | **자율 조사** |

### 7.2 vs AI 리서치 도구 (GPT Researcher, Perplexity)

| 기능 | GPT Researcher | Perplexity | 우리 시스템 |
|------|---------------|------------|------------|
| 실시간 모니터링 | ❌ | ❌ | **✅** |
| 자동 트리거 | ❌ | ❌ | **✅** |
| 다중 소스 | 웹 검색만 | 웹 검색만 | **뉴스+소셜** |
| 이상 감지 | ❌ | ❌ | **✅** |
| 클러스터링 | ❌ | ❌ | **✅** |

### 7.3 핵심 기술 우위

1. **99% 비용 절감**: 경쟁사 대비 압도적 가격 경쟁력
2. **다중 소스 삼각 검증**: GDELT + X + Telegram 교차 검증
3. **지능형 감지**: 키워드 없이도 새로운 위협 감지
4. **자율 조사**: 패시브 모니터링이 아닌 능동적 조사
5. **다국어 지원**: 100+ 언어 (day one)

---

## 8. 기술 스택

### 8.1 핵심 라이브러리

| 컴포넌트 | 기술 | 역할 |
|----------|------|------|
| **오케스트레이션** | LangGraph | 에이전트 상태 관리 |
| **LLM** | GPT-4o-mini | 분류, 조사, 리포트 |
| **임베딩** | BGE-M3 | 다국어 의미 검색 |
| **뉴스 수집** | gdeltdoc | GDELT API |
| **X/Twitter** | Twikit | 소셜 미디어 |
| **Telegram** | Telethon | 메시징 플랫폼 |
| **웹 검색** | Tavily | AI 에이전트용 검색 |

### 8.2 인프라

| 컴포넌트 | 기술 |
|----------|------|
| Backend | FastAPI (Python) |
| Database | PostgreSQL + pgvector |
| Scheduler | APScheduler |
| Deployment | Docker Compose |

---

## 9. 로드맵

### Phase 1: 현재 (완료)
- [x] 다중 소스 트리거 (GDELT + X + Telegram)
- [x] Anomaly Detection 레이어
- [x] Semantic Clustering 레이어
- [x] LLM 분류

### Phase 2: 단기 (1-2개월)
- [ ] Telegram 실시간 스트리밍 (폴링 → 푸시)
- [ ] 자율 조사 에이전트 고도화
- [ ] 웹 대시보드

### Phase 3: 중기 (3-6개월)
- [ ] Tiered Autonomy (계층별 자율성)
- [ ] Knowledge Graph 통합
- [ ] 알림 시스템 (Slack, Email)

### Phase 4: 장기 (6-12개월)
- [ ] Event-Driven 아키텍처 (Kafka)
- [ ] 다중 에이전트 협업
- [ ] API 서비스화

---

## 10. 리스크 및 완화

| 리스크 | 영향 | 완화 방안 |
|--------|------|----------|
| X/Twitter ToS 위반 | Twikit 차단 | 부계정 사용, 대체 API 준비 |
| GDELT 데이터 정확도 (~55%) | 오탐 | 다중 소스 교차 검증 |
| LLM 비용 상승 | 운영비 증가 | 로컬 모델 대체 (Mistral, Llama) |
| 임베딩 모델 메모리 (~2GB) | 인프라 비용 | 경량화 모델 (Qwen-0.6B) |

---

## 참고 문헌

### 시장 조사
- Mordor Intelligence, "Open Source Intelligence Market" (2024)
- Grand View Research, "Media Monitoring Tools Market" (2024)
- MarketsandMarkets, "Fake Image Detection Market" (2024)

### 기술 벤치마크
- GDELT Project (gdeltproject.org)
- BGE-M3, HuggingFace (huggingface.co/BAAI/bge-m3)
- GPT Researcher (github.com/assafelovic/gpt-researcher)
- Perplexity Deep Research (perplexity.ai)
- Tavily (tavily.com)

### 학술 연구
- NLP-Progress NER Benchmarks (nlpprogress.com)
- TimeEval Anomaly Detection (timeeval.github.io)
- PeerJ Short-text Clustering (peerj.com/articles/cs-2078)
- MIT TACL News Summarization (direct.mit.edu/tacl)

### 경쟁사 가격
- Palantir GSA Price List
- Dataminr via Vendr (vendr.com)
- Meltwater via Prowly (prowly.com)

---

*최종 업데이트: 2026-01-12*
*버전: 4.0 (다중 소스 + 감지 레이어)*
