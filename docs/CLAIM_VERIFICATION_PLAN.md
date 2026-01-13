# Claim-Level Verification System Implementation Plan

> **목표**: Event-level 검증을 Claim-level 검증으로 업그레이드하여 정확도 향상
>
> **근거**: 연구 결과 Claim decomposition으로 +7.5% 정확도, 복잡한 주장에서 최대 +8.31% 개선

---

## 2026 최신 연구 기반 결정 사항

### 1. 아키텍처 선택: AIC CTU + HerO 2 하이브리드 (2026 SOTA)

| 시스템 | 성과 | 핵심 특징 | 채택 |
|--------|------|----------|------|
| **[AIC CTU](https://arxiv.org/html/2508.04390)** | FEVER 8 1위 (0.50) | Simple RAG + Qwen3-14b | **O** |
| **[HerO 2](https://arxiv.org/html/2507.11004)** | AVeriTeC 2025 2위 | 4-stage + Document summarization | **O** |
| SAFE (2024) | NeurIPS 2024 | 웹 검색 + decontextualization | 일부 |
| VeriScore (2024) | - | 검증 가능한 주장만 추출 | **O** |

**최종 선택**: AIC CTU의 RAG 파이프라인 + HerO 2의 Document Summarization + VeriScore의 Claim 추출

### 2. 검증 모델 선택 (2026 업데이트)

| 방식 | 모델 | 성능 | 선택 |
|------|------|------|------|
| **LLM-based** | GPT-4o-mini (Qwen3 대안) | SOTA | **Primary** |
| NLI-based | DeBERTa-v3-mnli-fever | 91.2% MNLI | Backup/Fast |

**근거**: 2026 FEVER 8 우승 시스템(AIC CTU)과 AVeriTeC 상위 시스템 모두 LLM 기반 검증 사용

### 3. 검색 전략 (2026 업데이트)

| 항목 | 이전 (2024) | 2026 SOTA |
|------|------------|-----------|
| 검색 단위 | Sentence-level | **Document-level (60K chars)** |
| 임베딩 | 미지정 | **mxbai-embed-large-v1** |
| Reranking | 없음 | **MMR (λ=0.75)** |
| Vector DB | 없음 | **FAISS** |

### 4. LangGraph 패턴 선택

| 패턴 | LLM 호출 | 병렬 처리 | 선택 |
|------|---------|----------|------|
| ReAct | 많음 | 제한적 | X |
| **Plan-and-Execute** | 적음 | 우수 | **O** |

**선택**: Plan-and-Execute + Send API (Map-Reduce)

**LangGraph 1.0 신기능 활용**:
- `addSequence()` - 간소화된 그래프 정의
- Node-level caching - 중복 연산 방지
- Durable state - 실패 시 재시작 지점 저장

---

## 시스템 아키텍처 (2026 SOTA 기반)

### 전체 파이프라인

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              CLAIM-LEVEL VERIFICATION PIPELINE (2026 SOTA)                   │
│                   Based on: AIC CTU + HerO 2 + VeriScore                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INPUT: Event Text ("이란에서 대규모 시위가 발생했다...")                       │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ STAGE 1: CLAIM EXTRACTION (VeriScore 스타일)                          │   │
│  │                                                                       │   │
│  │  - 검증 가능한 주장만 추출 (의견, 추측, 미래 예측 제외)                    │   │
│  │  - Decontextualization (대명사 → 명사 치환)                            │   │
│  │  - Atomic fact 분해                                                   │   │
│  │                                                                       │   │
│  │  Output:                                                              │   │
│  │    Claim 1: "테헤란에서 2026년 1월 1일 시위가 발생했다"                  │   │
│  │    Claim 2: "시위 참가자 수는 10만명이다"                               │   │
│  │    Claim 3: "이란 정부가 인터넷을 차단했다"                              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ STAGE 2: DOCUMENT RETRIEVAL + SUMMARIZATION (AIC CTU + HerO 2)        │   │
│  │                                                                       │   │
│  │  Step 2a: Document-level Retrieval                                    │   │
│  │    - Embedding: mxbai-embed-large-v1                                 │   │
│  │    - Vector DB: FAISS (exact search)                                 │   │
│  │    - Reranking: MMR (k=40, l=10, λ=0.75)                            │   │
│  │    - Context: ~60,000 chars per claim                                │   │
│  │                                                                       │   │
│  │  Step 2b: Document Summarization (HerO 2)                            │   │
│  │    - 긴 문서를 핵심 정보로 압축                                         │   │
│  │    - 관련성 높은 증거 추출                                              │   │
│  │                                                                       │   │
│  │  Tools: GDELT → DuckDuckGo → Tavily (fallback)                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ STAGE 3: QA-BASED VERIFICATION (2026 SOTA)                            │   │
│  │                                                                       │   │
│  │  Step 3a: Question Generation                                        │   │
│  │    - Claim → 검증 질문 생성                                            │   │
│  │    - "시위가 테헤란에서 발생했는가?"                                     │   │
│  │    - "시위 참가자 수는 얼마인가?"                                       │   │
│  │                                                                       │   │
│  │  Step 3b: Answer Extraction + Verification                           │   │
│  │    - LLM (GPT-4o-mini): Evidence → Answer → Verdict                  │   │
│  │    - Likert-scale confidence (1-5)                                   │   │
│  │    - Output: SUPPORTED / REFUTED / NOT_ENOUGH_INFO                   │   │
│  │                                                                       │   │
│  │  ※ Backup: NLI (DeBERTa-v3) for fast/offline verification           │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ STAGE 4: VERDICT AGGREGATION                                          │   │
│  │                                                                       │   │
│  │  Method: Confidence-Weighted Voting                                   │   │
│  │                                                                       │   │
│  │  Output:                                                              │   │
│  │    - verified_claims: [Claim 1, Claim 3]                             │   │
│  │    - refuted_claims: [Claim 2]                                       │   │
│  │    - unverifiable_claims: [Claim 4]                                  │   │
│  │    - overall_score: 0.75 (3/4 verified)                              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ STAGE 5: ARTICLE SYNTHESIS (AP Style)                                 │   │
│  │                                                                       │   │
│  │  Structure:                                                           │   │
│  │    - Lead: WHO + WHAT + WHEN (25-40 words)                           │   │
│  │    - Nut Graph: Why this matters                                      │   │
│  │    - Body: Verified facts with attribution                           │   │
│  │    - Hedging: "reportedly" for unverified, "according to" for single │   │
│  │    - Metadata: AI-generated disclosure, verification stats           │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  OUTPUT: Verified Article + Per-Claim Breakdown                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## LangGraph State Schema

```python
from typing import Annotated, TypedDict, List, Optional, Literal
from datetime import datetime
import operator

class Claim(TypedDict):
    """추출된 개별 주장"""
    id: str
    text: str                          # Decontextualized claim
    original_span: str                 # 원본 텍스트에서의 위치
    claim_type: Literal["factual", "opinion", "prediction"]
    is_verifiable: bool

class EvidenceSource(TypedDict):
    """검색된 증거 소스"""
    url: str
    title: str
    snippet: str
    source_name: str                   # GDELT, DuckDuckGo, Tavily
    relevance_score: float
    retrieved_at: str

class ClaimVerdict(TypedDict):
    """개별 주장에 대한 판정"""
    claim_id: str
    verdict: Literal["SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"]
    confidence: float
    method: Literal["nli", "llm"]      # NLI or LLM fallback
    evidence_used: List[EvidenceSource]
    nli_scores: dict                   # {entailment, neutral, contradiction}

class ArticleMetadata(TypedDict):
    """기사 메타데이터 (AP Style 준수)"""
    word_count: int
    flesch_kincaid_grade: float
    source_count: int
    claims_verified: int
    claims_refuted: int
    claims_unverifiable: int
    ai_generated: bool
    human_reviewed: bool

class ClaimVerificationState(TypedDict):
    """전체 파이프라인 상태"""
    # === INPUT ===
    original_text: str
    event_category: str

    # === STAGE 1: EXTRACTION ===
    claims: Annotated[List[Claim], operator.add]

    # === STAGE 2: RESEARCH ===
    evidence_results: Annotated[List[dict], operator.add]

    # === STAGE 3: VERIFICATION ===
    verdicts: Annotated[List[ClaimVerdict], operator.add]

    # === STAGE 4: AGGREGATION ===
    verified_claims: List[Claim]
    refuted_claims: List[Claim]
    unverifiable_claims: List[Claim]
    overall_reliability_score: float

    # === STAGE 5: SYNTHESIS ===
    article: str
    article_metadata: ArticleMetadata

    # === WORKFLOW ===
    current_stage: str
    errors: Annotated[List[str], operator.add]
```

---

## 구현 상세

### Stage 1: Claim Extraction

**Prompt (VeriScore 기반)**:
```
Extract verifiable factual claims from the following text.

RULES:
1. Only extract claims that can be verified against external sources
2. EXCLUDE: opinions, predictions, hypotheticals, subjective statements
3. Decontextualize: Replace pronouns with proper nouns
4. Make each claim atomic and self-contained

INPUT TEXT:
{text}

OUTPUT FORMAT (JSON):
{
  "claims": [
    {
      "text": "Decontextualized claim text",
      "original_span": "Original text from input",
      "claim_type": "factual|opinion|prediction",
      "is_verifiable": true|false
    }
  ]
}
```

### Stage 2: Evidence Retrieval

**검색 우선순위** (비용 최적화):
1. GDELT (무료, 뉴스 특화)
2. DuckDuckGo (무료, 일반)
3. Tavily (유료, Fallback)

**병렬 처리**:
```python
async def research_claims_parallel(claims: List[Claim]) -> List[dict]:
    tasks = [search_for_claim(claim) for claim in claims]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

### Stage 3: QA-Based Verification (2026 SOTA)

**Primary**: LLM (GPT-4o-mini) - AIC CTU, HerO 2 방식
**Backup**: NLI (DeBERTa-v3) - 오프라인/빠른 검증용

**QA-Based Verification Pipeline** (AIC CTU 방식):
```python
async def verify_claim_qa_based(claim: str, evidence_docs: list[str]) -> dict:
    """
    2026 SOTA: QA-based verification using LLM
    Reference: AIC CTU (FEVER 8 Winner), HerO 2 (AVeriTeC Runner-up)
    """
    # Step 1: Generate verification questions
    questions = await generate_questions(claim)
    # Example: "Did protests occur in Tehran?" "How many protesters?"

    # Step 2: Extract answers from evidence
    context = "\n\n".join(evidence_docs)  # ~60,000 chars

    # Step 3: LLM verdict with Likert-scale confidence
    prompt = f"""
Based on the evidence below, verify the following claim.

CLAIM: {claim}

EVIDENCE:
{context}

QUESTIONS TO VERIFY:
{questions}

Respond with:
1. VERDICT: SUPPORTED | REFUTED | NOT_ENOUGH_INFO
2. CONFIDENCE: 1-5 (1=very uncertain, 5=very certain)
3. EVIDENCE_QUOTES: Key quotes supporting your verdict
4. REASONING: Brief explanation
"""

    response = await llm.ainvoke(prompt)
    return parse_verification_response(response)
```

**NLI Backup** (for fast/offline verification):
```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification

def verify_with_nli(evidence: str, claim: str) -> dict:
    """Backup: Fast NLI-based verification using DeBERTa-v3"""
    inputs = tokenizer(evidence, claim, return_tensors="pt", truncation=True)
    outputs = model(**inputs)
    probs = torch.softmax(outputs.logits, dim=-1)[0]

    labels = ["entailment", "neutral", "contradiction"]
    verdict_map = {
        "entailment": "SUPPORTED",
        "neutral": "NOT_ENOUGH_INFO",
        "contradiction": "REFUTED"
    }

    return {
        "verdict": verdict_map[labels[probs.argmax()]],
        "confidence": probs.max().item(),
        "method": "nli"
    }
```

### Stage 4: Aggregation

**Confidence-Weighted Voting**:
```python
def aggregate_verdicts(verdicts: List[ClaimVerdict]) -> dict:
    supported = [v for v in verdicts if v["verdict"] == "SUPPORTED"]
    refuted = [v for v in verdicts if v["verdict"] == "REFUTED"]
    nei = [v for v in verdicts if v["verdict"] == "NOT_ENOUGH_INFO"]

    total = len(verdicts)
    reliability_score = len(supported) / total if total > 0 else 0

    return {
        "verified_claims": supported,
        "refuted_claims": refuted,
        "unverifiable_claims": nei,
        "overall_reliability_score": reliability_score,
        "summary": f"{len(supported)}/{total} claims verified"
    }
```

### Stage 5: Article Synthesis

**AP Style 준수 사항**:
1. Lead: WHO + WHAT + WHEN (25-40 words)
2. Nut Graph: Why this matters
3. Attribution: "said", "according to"
4. Hedging: "reportedly" for unverified
5. Disclosure: AI-generated 표시

**출력 예시**:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VERIFIED REPORT: Iran Protests
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TEHRAN — Anti-government protests erupted across Iran
on January 1, 2024, according to multiple news sources.

✓ VERIFIED (3/4 claims):
  • Protests occurred in Tehran - SUPPORTED (conf: 0.92)
  • Government blocked internet - SUPPORTED (conf: 0.89)
  • Security forces deployed - SUPPORTED (conf: 0.87)

✗ REFUTED (1/4 claims):
  • 100,000 protesters participated - REFUTED (conf: 0.84)
    Evidence suggests ~10,000-20,000 participants

SOURCES: Reuters, BBC, Al Jazeera, GDELT

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
METADATA
AI-Generated: Yes | Human Review: Pending
Claims: 3/4 verified (75%) | Sources: 12
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 파일 구조 변경

```
app/agent/
├── investigator_v3.py          # NEW: Claim-Level Verification Agent
├── claim_extraction.py         # NEW: Claim extraction logic
├── nli_verifier.py             # NEW: NLI model wrapper
├── article_generator.py        # NEW: AP Style article generation
├── graph/
│   ├── state.py                # UPDATE: Add ClaimVerificationState
│   └── nodes.py                # NEW: Individual stage nodes
├── investigator_v2.py          # KEEP: Backup/comparison
└── investigator.py             # DELETE: Legacy v1
```

---

## 의존성 추가

```toml
# pyproject.toml
[project.dependencies]
# NLI Model
transformers = ">=4.40.0"
torch = ">=2.0.0"
accelerate = ">=0.27.0"

# 이미 있음
tenacity = ">=8.2.0"
langgraph = ">=0.2.0"
```

---

## 성능 예상

| 메트릭 | 현재 (v2) | 예상 (v3) | 개선 |
|--------|----------|----------|------|
| 정확도 | ~85% | ~92% | +7% |
| 실행 시간 | 65초 | 80-100초 | -15초 (NLI 추가) |
| Partial Truth 탐지 | 없음 | 있음 | NEW |
| Per-Claim Breakdown | 없음 | 있음 | NEW |
| Article Quality | 기본 | AP Style | 개선 |

---

## 참고 자료

### 2026 SOTA 시스템 (Primary References)
- **[AIC CTU - FEVER 8 Winner](https://arxiv.org/html/2508.04390)** - Simple RAG achieves SOTA (AVeriTeC 0.50)
- **[HerO 2 - AVeriTeC 2025 Runner-up](https://arxiv.org/html/2507.11004)** - 4-stage pipeline, 29s/claim
- **[FEVER9 Workshop (EACL 2026)](https://fever.ai/workshop.html)** - AVerImaTeC multimodal task

### 구현 참고
- [Google DeepMind SAFE](https://github.com/google-deepmind/long-form-factuality) - Decontextualization
- [VeriScore](https://github.com/Yixiao-Song/VeriScore) - Verifiable claim extraction
- [LangGraph 1.0 Docs](https://docs.langchain.com/oss/python/langgraph/overview) - Official documentation
- [LangGraph Plan-and-Execute](https://langchain-ai.github.io/langgraph/tutorials/plan-and-execute/)
- [DeBERTa-v3-mnli-fever](https://huggingface.co/MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli) - NLI backup

### 논문
- AIC CTU@FEVER 8: On-premise fact checking through long context RAG (2026)
- HerO 2: Efficient Fact Verification (AVeriTeC 2025)
- SAFE: Search-Augmented Factuality Evaluator (NeurIPS 2024)
- VeriScore: Evaluating Long-form Factuality (2024)
- Decomposition Dilemmas (NAACL 2025)
- AVeriTeC: A Dataset for Real-World Claim Verification

### 저널리즘 표준
- AP Stylebook AI Guidelines (2024-2026)
- California AI Transparency Act (Effective Jan 2026)
- Reuters AI Principles
- BBC Editorial Guidelines

---

## 구현 순서

1. **Phase 1**: `nli_verifier.py` 구현 (NLI 모델 래퍼)
2. **Phase 2**: `claim_extraction.py` 구현 (VeriScore 스타일)
3. **Phase 3**: `article_generator.py` 구현 (AP Style)
4. **Phase 4**: `investigator_v3.py` 통합 (LangGraph Pipeline)
5. **Phase 5**: 테스트 및 v1 삭제

---

*작성일: 2026-01-13*
*버전: 1.0*
*상태: 승인 대기*
