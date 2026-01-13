# Deep Verification Architecture (방안 C)

> Perplexity Deep Research 스타일의 깊은 검증 시스템

## 개요

기존 V1 에이전트의 문제점을 해결하기 위해 Perplexity Deep Research 아키텍처를 참고하여 구현.

### V1 문제점
- 소스 다양성 부족 (3개 소스)
- 핵심 정보 누락 (사망자, 경제적 원인 등)
- 검증 깊이 부족 (단순 "여러 소스에서 언급됨")
- 충돌 정보 탐지 없음

### V2 개선점
- 쿼리 분해로 다각적 조사
- 서브토픽별 독립 검색
- 중간 노트 합성
- 명시적 충돌 탐지
- 소스별/클레임별 신뢰도 점수
- 인용 추적 전체 파이프라인

---

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                    DEEP VERIFICATION PIPELINE                    │
└─────────────────────────────────────────────────────────────────┘

┌───────────────┐
│  DECOMPOSER   │  쿼리를 3-5개 서브토픽으로 분해
│               │  "이란 시위" → [원인, 규모, 대응, 피해, 국제반응]
└───────┬───────┘
        │
        ▼
┌───────────────┐     ┌─────────┐
│   RETRIEVER   │────▶│  TOOLS  │  서브토픽별 독립 검색
│  (per topic)  │◀────│         │  GDELT → DDG → Tavily
└───────┬───────┘     └─────────┘
        │
        ▼
┌───────────────┐
│    NOTER      │  서브토픽별 중간 노트 생성
│               │  - 발견 사실
│               │  - 충돌 정보
│               │  - 신뢰도 평가
└───────┬───────┘
        │ (모든 서브토픽 완료까지 반복)
        ▼
┌───────────────┐
│   VERIFIER    │  교차 검증 + 충돌 탐지
│               │  - 2+ 소스: VERIFIED
│               │  - 1 소스: UNVERIFIED
│               │  - 충돌: DISPUTED
└───────┬───────┘
        │
        ▼
┌───────────────┐
│  SYNTHESIZER  │  최종 리포트 생성
│               │  - 인용 포함
│               │  - 신뢰도 명시
│               │  - 충돌/미검증 라벨링
└───────────────┘
```

---

## 상태 정의

```python
class DeepVerificationState(InvestigationState):
    subtopics: list[str] = []           # 분해된 서브토픽
    structured_notes: list[dict] = []    # 서브토픽별 노트
    source_items: list[dict] = []        # 수집된 소스
    conflicts_detected: list[dict] = []  # 탐지된 충돌
```

---

## 노드 상세

### 1. DECOMPOSER
주제를 3-5개 독립적인 서브토픽으로 분해

```
INPUT: "Protests in Iran against government"

OUTPUT:
- What happened? (timeline and facts)
- Who is involved? (actors and casualties)
- Where exactly? (locations affected)
- Why/causes? (economic triggers)
- What is the response? (government, international)
```

### 2. RETRIEVER
각 서브토픽에 대해 독립적으로 검색

```
서브토픽 1: "What happened?"
  → search_news_gdelt("Iran protest timeline facts")
  → search_web_free("Iran protest January 2026 events")

서브토픽 2: "Who is involved?"
  → search_news_gdelt("Iran protest casualties death toll")
  → search_web_free("Iran protest arrests")
```

### 3. NOTER
서브토픽별 중간 노트 생성

```python
{
    "subtopic": "What happened?",
    "findings": [
        "Protests began in late December 2024",
        "Started with shopkeeper strikes in Tehran",
        "Spread to 185 cities across 31 provinces"
    ],
    "sources": ["CNN", "Al Jazeera", "BBC"],
    "conflicts": [],
    "confidence": 0.9
}
```

### 4. VERIFIER
교차 검증 및 충돌 탐지

```python
# VERIFIED (2+ 소스)
{
    "claim": "Death toll exceeds 500",
    "supporting_sources": ["CNN", "HRANA", "Al Jazeera"],
    "confidence": 0.9,
    "is_disputed": False
}

# DISPUTED (충돌 정보)
{
    "claim": "Government response",
    "conflict": "Government says 'under control' vs protesters say 'spreading'",
    "sources": ["Tasnim (pro-gov)", "HRANA (opposition)"]
}
```

### 5. SYNTHESIZER
최종 리포트 생성

```
SUMMARY: Iran faces largest protests in years, with death toll
exceeding 500 according to human rights groups (CNN, HRANA).
Protests began in late December over economic grievances...

TIMELINE:
- Late December: Shopkeeper strikes begin in Tehran
- January 8: Nationwide internet blackout
- January 11: Death toll exceeds 500

KEY FACTS:
✅ 500+ deaths (high confidence, 3 sources)
✅ 10,000+ arrests (high confidence, 2 sources)
✅ 185 cities affected (medium confidence, 2 sources)

DISPUTED:
⚠️ Government control status (conflicting reports)

UNVERIFIED:
⚠️ Specific military involvement (single source)
```

---

## 사용법

```python
from app.agent import DeepVerificationAgent

agent = DeepVerificationAgent()

report = await agent.investigate(
    event="Large protests in Iran against government",
    category="protest"
)

print(f"Summary: {report.event_summary}")
print(f"Verified Facts: {len(report.verified_facts)}")
print(f"Confidence: {report.confidence_score}")
print(f"Sources: {len(report.sources)}")
```

---

## V1 vs V2 비교

| 항목 | V1 (기존) | V2 (Deep Verification) |
|------|----------|------------------------|
| 쿼리 분해 | ❌ | ✅ 3-5개 서브토픽 |
| 검색 횟수 | 5회 고정 | 서브토픽 × 2~3회 |
| 중간 합성 | ❌ | ✅ 서브토픽별 노트 |
| 충돌 탐지 | ❌ | ✅ 명시적 플래그 |
| 신뢰도 점수 | high/med/low | 0.0~1.0 수치 |
| 인용 추적 | 도구명 | 실제 URL |

---

## 평가 지표

### 검색 품질
- **Hit Rate**: 관련 문서 포함 여부
- **Source Diversity**: 고유 소스 수
- **Subtopic Coverage**: 서브토픽별 결과 수

### 검증 품질
- **Verification Rate**: 검증된 클레임 비율
- **Conflict Detection**: 탐지된 충돌 수
- **Confidence Accuracy**: 신뢰도 점수 정확도

### 생성 품질
- **Faithfulness**: 소스와 일치도
- **Citation Accuracy**: 인용 정확도
- **Completeness**: 핵심 정보 포함 여부

---

## 참고 자료

- [Perplexity Deep Research](https://www.perplexity.ai/hub/blog/introducing-perplexity-deep-research)
- [RAG Evaluation Survey (arXiv)](https://arxiv.org/html/2405.07437v2)
- [Deep Research Agents Survey](https://arxiv.org/html/2508.12752v1)

---

*작성일: 2026-01-13*
*브랜치: feature/deep-verification*
