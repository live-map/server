# PM 읽기 가이드

> 프로젝트 매니저를 위한 LiveMap 시스템 이해 가이드

---

## 대상 독자 및 읽기 경로

| 역할 | 소요 시간 | 필수 문서 |
|------|----------|----------|
| **투자자** | 20분 | OVERVIEW → INVESTOR_SUMMARY → COMPETITIVE_ANALYSIS |
| **프로젝트 매니저** | 90분 | 전체 경로 (아래 참조) |
| **개발자** | 60분 | getting-started → architecture → guides |
| **일반 사용자** | 10분 | OVERVIEW → getting-started/README |

---

## PM 읽기 경로 (90분)

### 1. 시작하기 (5분)

📖 **[OVERVIEW.md](./OVERVIEW.md)**: 시스템 한눈에 보기
- LiveMap이란?
- 핵심 차별점
- 전체 아키텍처

---

### 2. 비즈니스 이해 (15분)

📖 **[business/INVESTOR_SUMMARY.md](./business/INVESTOR_SUMMARY.md)**: 왜 이 프로젝트가 필요한가
- 문제 정의
- 시장 기회
- 수익 모델

📖 **[business/VALUE_PROPOSITION.md](./business/VALUE_PROPOSITION.md)**: 경쟁 우위
- 대안 대비 비용 비교
- 고유 역량
- 타겟 고객

📖 **[business/COMPETITIVE_ANALYSIS.md](./business/COMPETITIVE_ANALYSIS.md)**: 시장 포지셔닝
- 경쟁사 현황
- 차별화 전략
- 해결하는 시장 격차

---

### 3. 핵심 개념 (20분)

📖 **[concepts/TWO_SOURCE_RULE.md](./concepts/TWO_SOURCE_RULE.md)**: 검증의 기본 원칙
- 왜 2개 소스가 필요한가
- 예외 케이스
- 구현 세부사항

📖 **[concepts/SOURCE_TIERS.md](./concepts/SOURCE_TIERS.md)**: 소스 신뢰도 체계
- Tier-1 정부 소스
- Tier-1/2 뉴스 소스
- Tier-3 소셜 신호

📖 **[concepts/CONFIDENCE_SCORING.md](./concepts/CONFIDENCE_SCORING.md)**: 신뢰도 점수 계산
- 점수 계산 공식
- 소스 가중치
- 발행 임계값

---

### 4. 시스템 아키텍처 (30분)

📖 **[architecture/SCANNER_PIPELINE.md](./architecture/SCANNER_PIPELINE.md)**: 7단계 이벤트 처리
- 트리거 수집
- 클러스터링 및 중복 제거
- 이벤트 검증 (Gate 0)
- 신뢰도 점수 계산
- 콘텐츠 게이트

📖 **[architecture/EVENT_VERIFICATION.md](./architecture/EVENT_VERIFICATION.md)**: Gate 0 검증
- 3단계 하이브리드 접근법
- 규칙 기반 필터링
- Zero-shot 분류
- LLM 검증

📖 **[architecture/ZERO_SHOT_CLASSIFIER.md](./architecture/ZERO_SHOT_CLASSIFIER.md)**: ML 기반 분류
- BART-large-MNLI 모델
- CAMEO/ACLED 레이블
- 확신도 임계값

📖 **[architecture/CLAIM_VERIFICATION.md](./architecture/CLAIM_VERIFICATION.md)**: Claim-level 검증 v3
- 5단계 파이프라인
- VeriScore 주장 추출
- QA 기반 검증
- AP Style 기사 생성

---

### 5. 의사결정 기록 (15분)

📖 **[adr/README.md](./adr/README.md)**: 아키텍처 결정 기록(ADR) 개요
- ADR이란?
- 읽는 방법

📖 **핵심 ADR 목록:**
- [ADR-001: Two-Source Rule](./adr/ADR-001-two-source-rule.md) - 핵심 검증 원칙
- [ADR-002: Gate Ordering](./adr/ADR-002-gate-ordering.md) - 파이프라인 설계 근거
- [ADR-003: Tier System](./adr/ADR-003-tier-system.md) - 소스 분류 체계
- [ADR-004: Hybrid Verification](./adr/ADR-004-hybrid-verification.md) - 이벤트 검증 접근법
- [ADR-005: Bilingual Generation](./adr/ADR-005-bilingual-generation.md) - 한국어/영어 출력
- [ADR-006: Deduplication](./adr/ADR-006-deduplication.md) - 중복 이벤트 처리

---

### 6. [선택] 개발자 가이드

기술적 심화가 필요한 경우:

📖 **[getting-started/README.md](./getting-started/README.md)**: 빠른 시작 가이드
- 설치 단계
- 서버 실행
- 첫 스캔

📖 **[guides/CONFIGURATION.md](./guides/CONFIGURATION.md)**: 시스템 설정
- 환경 변수
- 기능 플래그
- 튜닝 파라미터

---

### 7. [선택] 프로젝트 히스토리

현재까지의 발전 과정 이해:

📖 **[history/CHANGELOG.md](./history/CHANGELOG.md)**: 버전 이력
- 주요 마일스톤
- 기능 추가
- Breaking changes

📖 **[history/PHASE_7_ZERO_SHOT.md](./history/PHASE_7_ZERO_SHOT.md)**: Zero-shot 분류기 구현
- 설계 결정
- 성능 벤치마크

---

## 빠른 참조

### 시스템 개요 다이어그램

```
┌─────────────────────────────────────────────────────────────────────┐
│                      TRIGGER LAYER                                   │
│   GDELT (100K+ 소스) + Telegram (OSINT) + X/Twitter                  │
├─────────────────────────────────────────────────────────────────────┤
│                    DETECTION LAYER                                   │
│   키워드 매칭 → 이상 탐지 → 시맨틱 클러스터링                           │
├─────────────────────────────────────────────────────────────────────┤
│                   VERIFICATION LAYER                                 │
│   Gate 0 (이벤트) → Gate 1 (검증가치) → Gate 2 (구체성)               │
├─────────────────────────────────────────────────────────────────────┤
│                   INVESTIGATION LAYER                                │
│   주장 추출 → 증거 검색 → QA 검증                                     │
├─────────────────────────────────────────────────────────────────────┤
│                      OUTPUT LAYER                                    │
│   AP Style 기사 (한/영) + 주장별 분석                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 핵심 지표

| 지표 | 값 |
|------|-----|
| 월 운영 비용 | ~$20 (경쟁사 $10K-$200K 대비) |
| 이벤트 감지 지연 | <15분 (GDELT), 실시간 (Telegram) |
| 조사 시간 | ~65초 (Deep Verification) |
| 언어 지원 | 100개+ (BGE-M3 다국어 임베딩) |
| 데이터 소스 | 100,000+ 뉴스 소스 + 소셜 미디어 |

### 비용 비교

| 솔루션 | 연간 비용 | LiveMap 대비 |
|--------|----------|-------------|
| Palantir | $173K+ | 720배 |
| Dataminr | $120K-$2.4M | 500-10,000배 |
| Recorded Future | $200K+ | 833배 |
| **LiveMap** | **$240** | 1배 |

---

## 질문이 있으신가요?

문서를 읽은 후 질문이 있다면:
1. [guides/TROUBLESHOOTING.md](./guides/TROUBLESHOOTING.md)에서 일반적인 문제 확인
2. [ADR 인덱스](./adr/README.md)에서 설계 결정 확인
3. 개발팀에 문의

---

*이 가이드는 이중 언어 문서 구조의 일부로 유지관리됩니다.*
