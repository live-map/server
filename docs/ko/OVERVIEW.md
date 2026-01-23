# LiveMap 시스템 개요

> AI 기반 국제 정세 뉴스 검증 플랫폼

---

## LiveMap이란?

LiveMap은 14개 이상의 소스에서 글로벌 이벤트를 모니터링하고, 다중 소스 교차 검증을 통해 정보를 검증하며, 실시간으로 이중 언어(한국어/영어) 뉴스 기사를 생성하는 자율 뉴스 인텔리전스 시스템입니다.

**미션**: *"누구보다 빠르게, 검증된, 편향 없는 국제 정세 뉴스"*

---

## 핵심 차별점

| 특징 | 전통 미디어 | 소셜 미디어 | LiveMap |
|---------|------------------|--------------|---------|
| **감지 속도** | 15-60분 지연 | 실시간 | 실시간 |
| **검증** | 수동 | 없음 | 자동화 다중 소스 |
| **편향** | 편집 결정 | 알고리즘 증폭 | 알고리즘 기반, 중립 |
| **투명성** | 거의 공개 안함 | 블랙박스 | 공개 방법론 + 신뢰도 점수 |
| **소스 비용** | 비싼 구독료 | 무료지만 신뢰 불가 | $0 (모든 무료 소스) |

---

## 작동 방식

### 7단계 파이프라인

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. TRIGGER COLLECTION                                           │
│    GDELT, Reddit, USGS, NOAA → 14개+ 소스 병렬 수집             │
├─────────────────────────────────────────────────────────────────┤
│ 2. SEMANTIC CLUSTERING                                          │
│    Embedding(BGE-M3) 사용하여 유사 이벤트 그룹화                │
├─────────────────────────────────────────────────────────────────┤
│ 3. SOURCE CLASSIFICATION                                        │
│    Tier-1 정부 | Tier-1 뉴스 | Tier-2 | Tier-3 소셜             │
├─────────────────────────────────────────────────────────────────┤
│ 4. EVENT VERIFICATION (Gate 0)                                  │
│    규칙 → Zero-shot ML → LLM (3단계 하이브리드, 91% 비용 절감)  │
├─────────────────────────────────────────────────────────────────┤
│ 5. CONFIDENCE SCORING                                           │
│    Two-Source Rule, Tier 가중치 점수                            │
├─────────────────────────────────────────────────────────────────┤
│ 6. CONTENT GATES (Gate 1-2)                                     │
│    Check-worthiness, Specificity 필터                           │
├─────────────────────────────────────────────────────────────────┤
│ 7. CLAIM VERIFICATION & ARTICLE GENERATION                      │
│    VeriScore 스타일 주장 → QA 검증 → AP Style 기사              │
└─────────────────────────────────────────────────────────────────┘
```

### Source Tier 시스템

| Tier | 소스 | 신뢰도 | 신뢰 수준 |
|------|---------|-------------|-------------|
| **Tier-1 정부** | USGS, NOAA | 0.99 | 즉시 게시 |
| **Tier-1 뉴스** | GDELT (Reuters, AP, BBC) | 0.90 | 게시 가능 |
| **Tier-2 데이터** | ACLED | 0.85 | 추가 확인 필요 |
| **Tier-2 뉴스** | Currents, WorldNews | 0.75 | 추가 확인 필요 |
| **Tier-3 소셜** | Reddit, Bluesky | 0.40 | 신호만 |
| **Tier-3 메시징** | Telegram | 0.35 | 신호만 |

---

## 핵심 원칙

### Two-Source Rule

이벤트는 게시 전 **2개 이상의 독립적인 소스**로부터 검증이 필요합니다.

**예외**:
- Tier-1 정부 소스 (USGS, NOAA)는 즉시 게시 가능
- 신뢰도 ≥ 0.70인 Tier-1 뉴스

### IFCN 준수

International Fact-Checking Network의 5대 원칙을 모두 준수합니다:

1. **비당파성**: 알고리즘 기반, 편집 편향 없음
2. **소스 투명성**: 모든 기사에 모든 소스 인용
3. **자금 투명성**: 광고 또는 후원 콘텐츠 없음
4. **방법론 투명성**: 공개 문서화
5. **정정 정책**: 오류 발견 시 즉시 정정

---

## 국제 정세 집중

현재 7개 카테고리에 집중:

| 카테고리 | 설명 | 예시 |
|----------|-------------|----------|
| **war** | 무력 충돌, 침략 | 러시아-우크라이나, 가자 |
| **conflict** | 지역 분쟁 | 국경 충돌, 내전 |
| **politics** | 정상회담, 제재, 선거 | 미중 정상회담 |
| **security** | 핵, 사이버, 테러 위협 | 이란 핵 협상 |
| **military** | 작전, 배치 | NATO 훈련 |
| **terrorism** | 테러 공격, 조직 | ISIS, 알카에다 |
| **diplomacy** | 조약, 협상 | 평화 협정 |

---

## 기술 스택

| 구성 요소 | 기술 |
|-----------|------------|
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy 2.0 |
| **Database** | PostgreSQL 15+ with pgvector |
| **ML Models** | BART-MNLI (zero-shot), BGE-M3 (embeddings) |
| **LLM** | OpenAI GPT-4o-mini |
| **Agent Framework** | LangGraph |

---

## 빠른 링크

### 투자자용
- [투자자 요약](business/INVESTOR_SUMMARY.md) - 경영진 피치
- [로드맵](business/ROADMAP.md) - 향후 계획

### 사용자용
- [신뢰도 점수](concepts/CONFIDENCE_SCORING.md) - 신뢰 점수 작동 방식
- [국제 정세 집중](concepts/INTERNATIONAL_AFFAIRS.md) - 카테고리 정의

### 기술 전문가용
- [스캐너 파이프라인](architecture/SCANNER_PIPELINE.md) - 전체 파이프라인 상세
- [이벤트 검증](architecture/EVENT_VERIFICATION.md) - Gate 0 하이브리드 시스템
- [주장 검증](architecture/CLAIM_VERIFICATION.md) - v3.0 SOTA 구현

### 개발자용
- [시작하기](getting-started/README.md) - 5분 설정
- [프로젝트 구조](getting-started/PROJECT_STRUCTURE.md) - 코드베이스 가이드
- [API 레퍼런스](api/README.md) - REST 엔드포인트

---

## 비용 구조

### 소스 비용: $0/월

| 소스 | 비용 |
|--------|------|
| GDELT | 무료 |
| Reddit | 무료 |
| USGS/NOAA | 무료 |
| Currents API | 무료 (1,000/일) |
| World News API | 무료 (500/일) |

### 운영 비용: ~$150-250/월

| 구성 요소 | 비용 |
|-----------|------|
| LLM API (GPT-4o-mini) | $40-150/월 |
| 클라우드 호스팅 | $50-100/월 |
| 벡터 데이터베이스 | ~$50/월 |

---

## 성능 지표

| 지표 | 목표 | 상태 |
|--------|--------|--------|
| 감지 지연 | < 15분 | 개발 중 |
| 오탐률 | < 5% | 개발 중 |
| 소스 커버리지 | 14개+ 소스 | 구현 중 |
| 검증 정확도 | > 90% | 개발 중 |
| LLM 비용 절감 | > 80% | **91% 달성** |

---

---

## 참고 자료

### 데이터 소스
- **GDELT Project**: [gdeltproject.org](https://www.gdeltproject.org/) - Global Event, Language, and Tone 데이터베이스
- **ACLED**: [acleddata.com](https://acleddata.com/) - Armed Conflict Location & Event Data Project

### ML 모델
- **BART-MNLI**: [facebook/bart-large-mnli](https://huggingface.co/facebook/bart-large-mnli) - Zero-shot 분류 모델
- **BGE-M3**: [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) - 다국어 Embedding 모델

### 저널리즘 표준
- **IFCN**: [ifcncodeofprinciples.poynter.org](https://www.ifcncodeofprinciples.poynter.org/) - International Fact-Checking Network 원칙 코드

---

*상세 기술 문서는 [아키텍처](architecture/README.md) 참조*
