# Architecture Documentation

이 섹션은 LiveMap 시스템 아키텍처에 대한 상세 기술 문서를 포함합니다.

---

## 개요

LiveMap은 뉴스 이벤트를 수집에서 게시까지 처리하기 위해 7단계 파이프라인 아키텍처를 사용합니다:

```
Triggers → Clustering → Classification → Verification → Scoring → Gates → Output
```

---

## 핵심 컴포넌트

### 파이프라인 아키텍처

- **[Scanner Pipeline](SCANNER_PIPELINE.md)** - 완전한 7단계 파이프라인 문서
  - Stage 1: Trigger 수집
  - Stage 2: 시맨틱 클러스터링
  - Stage 3: 소스 분류
  - Stage 3.5: 이벤트 검증 (Gate 0)
  - Stage 4: 신뢰도 점수화
  - Stage 5: 콘텐츠 게이트
  - Stage 6-7: 최종 필터링 & 출력

### 검증 시스템

- **[Event Verification](EVENT_VERIFICATION.md)** - Gate 0: 3단계 하이브리드 검증
  - Stage 1: 규칙 기반 패턴 ($0)
  - Stage 2: Zero-shot 분류 (BART-MNLI, $0)
  - Stage 3: LLM 검증 (엣지 케이스만)

- **[Claim Verification](CLAIM_VERIFICATION.md)** - v3.0 주장 수준 검증
  - VeriScore 스타일 주장 추출
  - QA 기반 LLM 검증
  - AP 스타일 기사 생성

### ML 컴포넌트

- **[Zero-shot Classifier](ZERO_SHOT_CLASSIFIER.md)** - BART-MNLI 분류
  - CAMEO/ACLED 기반 레이블
  - 국제 정세 감지
  - 70% LLM 비용 절감

### 지원 시스템

- **중복 제거** - [algorithms/DEDUPLICATION.md](../algorithms/DEDUPLICATION.md) 참조
- **이중 언어 생성** - 한국어/영어 기사 생성

---

## 시스템 다이어그램

```
┌───────────────────────────────────────────────────────────────────────────┐
│                              DATA SOURCES                                  │
├─────────────┬─────────────┬─────────────┬─────────────┬──────────────────┤
│    GDELT    │    USGS     │    NOAA     │   Reddit    │    Telegram      │
│  (Tier-1)   │  (Tier-1)   │  (Tier-1)   │  (Tier-3)   │    (Tier-3)      │
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴────────┬─────────┘
       │             │             │             │               │
       └─────────────┴─────────────┴─────────────┴───────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │      TRIGGER MANAGER        │
                    │   병렬 이벤트 수집          │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │     SEMANTIC CLUSTERING     │
                    │   BGE-M3 + HDBSCAN         │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │     EVENT VERIFICATION      │
                    │   Rules → Zero-shot → LLM   │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │    CONFIDENCE SCORING       │
                    │  Two-Source Rule + Tiers    │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │      CONTENT GATES          │
                    │ 검증 가치 + 구체성         │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │   CLAIM VERIFICATION        │
                    │  추출 → 검증 → 작성        │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │       ARTICLE OUTPUT        │
                    │   이중 언어 (KO/EN) + DB    │
                    └─────────────────────────────┘
```

---

## 주요 설계 결정

아키텍처 선택에 대한 근거는 다음을 참조하세요:

- [ADR-001: Two-Source Rule](../adr/ADR-001-two-source-rule.md)
- [ADR-002: Gate Ordering](../adr/ADR-002-gate-ordering.md)
- [ADR-003: Tier System](../adr/ADR-003-tier-system.md)
- [ADR-004: Hybrid Verification](../adr/ADR-004-hybrid-verification.md)
- [ADR-005: Bilingual Generation](../adr/ADR-005-bilingual-generation.md)
- [ADR-006: Deduplication](../adr/ADR-006-deduplication.md)

---

## 성능 특성

| 컴포넌트 | 지연 시간 | 비용 | 정확도 |
|-----------|---------|------|----------|
| Trigger 스캔 | 8-10초 | $0 | N/A |
| 클러스터링 | 1-3초 | $0 | ~95% |
| 이벤트 검증 | 350ms | $1.44/일 | ~90% |
| 주장 검증 | 60-120초 | ~$50/월 | ~90% |

---

## 관련 문서

- [Algorithms](../algorithms/README.md) - 상세 알고리즘 문서
- [API Reference](../api/README.md) - REST 엔드포인트
- [Configuration](../guides/CONFIGURATION.md) - 모든 설정
