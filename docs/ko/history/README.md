# 프로젝트 히스토리

이 섹션은 LiveMap 시스템의 초기 컨셉부터 현재 구현까지의 발전 과정을 문서화합니다.

---

## 타임라인 개요

```
2026년 1월 10일 ──────────────────────────────────────────────────► 1월 27일
    │
    ├── Phase 0: Foundation (1월 10일)
    │   └── Telegram MCP, GDELT 트리거, 기본 인프라
    │
    ├── Phase 1: 검증 진화 (1월 10-14일)
    │   └── 3단계 → RAG → GDELT → Claim-level SOTA
    │
    ├── Phase 2: 보안 및 품질 (1월 15-19일)
    │   └── JWT → JWE 마이그레이션, 중요도 점수
    │
    ├── Phase 3: 인텔리전스 레이어 (1월 19-23일)
    │   └── Zero-shot ML, 91% 비용 절감, 게이트 시스템
    │
    ├── Phase 4: 소스 관리 (1월 23-24일)
    │   └── 최신성 필터, 카테고리 분류
    │
    ├── Phase 5: 최적화 (1월 24일)
    │   └── 속보 패스트패스, P0/P1/P2 최적화
    │
    └── Phase 6: LLM 분류기 (1월 25-27일)
        └── 패턴 → LLM 대체, Recency 제거, Pre-LLM Dedup
```

---

## 버전 히스토리

| 버전 | 날짜 | 마일스톤 |
|------|------|----------|
| v0.1 | 1월 10일 | 기본 트리거 시스템 |
| v1.0 | 1월 11일 | 3단계 검증 |
| v2.0 | 1월 13일 | 심층 검증 에이전트 |
| v3.0 | 1월 14일 | Claim-level 검증 (SOTA) |
| v3.1 | 1월 14일 | 프로덕션 준비 완료 품질 |
| v3.2 | 1월 21일 | Gate 시스템 통합 |
| v3.3 | 1월 23일 | Zero-shot ML 분류기 |
| v3.4 | 1월 24일 | 속보 패스트패스 |
| v3.5 | 1월 24일 | P0/P1/P2 최적화 |
| v3.6 | 1월 27일 | **LLM 분류기 + 파이프라인 최적화** |

---

## Phase 문서

### 현재 아키텍처 (Phase 6)

시스템은 현재 LLM 기반 분류와 최적화된 deduplication을 사용합니다:

| Phase | 문서 | 요약 |
|-------|------|------|
| 0 | [Foundation](PHASE_0_FOUNDATION.md) | Telegram MCP, GDELT, 기본 설정 |
| 1 | [검증 진화](PHASE_1_VERIFICATION_EVOLUTION.md) | 3단계 → Claim-level SOTA |
| 2 | [보안 및 품질](PHASE_2_SECURITY_AND_QUALITY.md) | JWE 인증, 중요도 점수 |
| 3 | [인텔리전스 레이어](PHASE_3_INTELLIGENCE_LAYER.md) | Zero-shot ML, 91% 비용 절감 |
| 4 | [소스 관리](PHASE_4_SOURCE_MANAGEMENT.md) | 최신성 필터, 카테고리 |
| 5 | [최적화](PHASE_5_OPTIMIZATION.md) | 속보, P0/P1/P2 |
| **6** | [**LLM 분류기**](PHASE_6_LLM_CLASSIFIER.md) | **패턴→LLM, Recency 제거, Pre-LLM Dedup** |

---

## 주요 지표

| 지표 | 초기 | Phase 5 | Phase 6 (현재) | 개선 |
|------|------|---------|----------------|------|
| LLM 비용/일 | $16.13 | $1.44 | **$0.10-0.17** | -99% |
| 검증 시간 | 45초 | 8초 평균 | 5초 평균 | -89% |
| 속보 지연 | N/A | 5초 | 5초 | - |
| 패턴 규칙 | 600+ | 600+ | **1개 프롬프트** | -99% |
| 데이터 소스 | 1 | 12+ | **59개 도메인** (화이트리스트) | 품질↑ |
| 거짓 양성률 | ~20% | ~5% | ~5% (예상) | - |

---

## 아카이브 문서

더 이상 사용하지 않는 접근 방식에 대한 문서:

- [Phase 7 Zero-Shot (원본)](archive/PHASE_7_ZERO_SHOT.md) - Phase 3에 통합됨
- [Deep Verification v2.0](archive/DEEP_VERIFICATION_V2.md) - v3.0 주장 수준 검증으로 대체됨
- [Claim Verification Plan](archive/CLAIM_VERIFICATION_PLAN.md) - 완료된 계획 문서
- [Methodology](archive/METHODOLOGY.md) - 원본 방법론

---

## 주요 결정 타임라인

| 날짜 | 결정 | 근거 | ADR |
|------|------|------|-----|
| 1월 10일 | Two-Source Rule | IFCN 규정 준수 | [ADR-001](../adr/ADR-001-two-source-rule.md) |
| 1월 11일 | Tier 시스템 (트리거) | 소스 신뢰도 차별화 | [ADR-003](../adr/ADR-003-tier-system.md) |
| 1월 13일 | VeriScore claims | 2026 SOTA 구현 | - |
| 1월 15일 | Gate 순서 | 저렴한 것 → 비싼 것 순 | [ADR-002](../adr/ADR-002-gate-ordering.md) |
| 1월 21일 | 하이브리드 검증 | LLM 비용 70% 절감 | [ADR-004](../adr/ADR-004-hybrid-verification.md) |
| 1월 23일 | Zero-shot 분류기 | 추가 70% 절감 | [ADR-004](../adr/ADR-004-hybrid-verification.md) |
| 1월 23일 | 국제 문제 집중 | 양보다 질 | - |
| 1월 24일 | 속보 패스트패스 | Tier-1 소스 속도 | [ADR-007](../adr/ADR-007-breaking-news.md) |
| 1월 24일 | 도메인 티어 시스템 | 도메인별 신뢰도 | [ADR-011](../adr/ADR-011-domain-tiers.md) |
| 1월 24일 | Goldstein Scale 중요도 | 다차원 점수 | [ADR-008](../adr/ADR-008-importance-scoring.md) |
| 1월 27일 | **LLM 분류기** | 패턴 600개 → 프롬프트 1개 | [ADR-012](../adr/ADR-012-llm-classifier.md) |
| 1월 27일 | **Recency 필터 제거** | 트리거 레벨에서 이미 처리 | - |
| 1월 27일 | **Pre-LLM Dedup** | LLM 비용 25% 절감 | - |

---

## Changelog

상세 버전 기록은 [CHANGELOG.md](CHANGELOG.md)를 참조하세요.

---

## 관련 문서

- [아키텍처 결정](../adr/README.md) - ADRs
- [아키텍처](../architecture/README.md) - 현재 설계
- [알고리즘](../algorithms/README.md) - 핵심 알고리즘
