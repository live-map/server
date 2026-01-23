# Project History

이 섹션은 LiveMap 시스템의 초기 컨셉부터 현재 구현까지의 발전 과정을 문서화합니다.

---

## Timeline Overview

```
Jan 10, 2026 ──────────────────────────────────────────────────────────────────►
    │
    ├── Phase 0: Foundation (Jan 10)
    │   └── Telegram MCP, 기본 트리거 시스템
    │
    ├── Phase 1: Verification (Jan 10-11)
    │   └── 3단계 검증 파이프라인
    │
    ├── Phase 2: Autonomous Agent (Jan 11-13)
    │   └── 다중 소스 조사, 주장 검증
    │
    ├── Phase 3: Parallel Processing (Jan 13)
    │   └── LangGraph 에이전트, 병렬 증거 수집
    │
    ├── Phase 4: Content Filtering (Jan 15-21)
    │   └── Gate 0-2, 이벤트 검증, 검토가치 판단
    │
    ├── Phase 5: Integration (Jan 21-22)
    │   └── Scanner-Agent 통합, DB 영속화
    │
    ├── Phase 6: International Focus (Jan 23)
    │   └── 7개 카테고리 집중, 리소스 최적화
    │
    └── Phase 7: Zero-shot ML (Jan 23)
        └── BART-MNLI 분류기, 91% 비용 절감
```

---

## Version History

| Version | Date | Milestone |
|---------|------|-----------|
| v0.1 | Jan 10 | 기본 트리거 시스템 |
| v1.0 | Jan 11 | 3단계 검증 |
| v2.0 | Jan 13 | 심층 검증 에이전트 |
| v3.0 | Jan 14 | 주장 수준 검증 (SOTA) |
| v3.1 | Jan 14 | 프로덕션 준비 완료 품질 |
| v3.2 | Jan 21 | Gate 시스템 통합 |
| v3.3 | Jan 23 | Zero-shot ML 분류기 |

---

## Phase Documentation

### Current Architecture (Phase 7)

시스템은 현재 3단계 하이브리드 검증을 포함한 7단계 파이프라인을 사용합니다:

1. [Phase 0: Foundation](PHASE_0_FOUNDATION.md) - 초기 Telegram MCP
2. [Phase 1: Verification](PHASE_1_VERIFICATION.md) - 3단계 파이프라인
3. [Phase 2: Autonomous Agent](PHASE_2_AUTONOMOUS.md) - 다중 소스 조사
4. [Phase 3: Parallel Processing](PHASE_3_PARALLEL.md) - LangGraph 에이전트
5. [Phase 4: Content Filtering](PHASE_4_FILTERING.md) - Gate 시스템
6. [Phase 5: Integration](PHASE_5_INTEGRATION.md) - 전체 파이프라인
7. [Phase 6: International Focus](PHASE_6_INTERNATIONAL.md) - 카테고리 집중
8. [Phase 7: Zero-shot ML](PHASE_7_ZERO_SHOT.md) - ML 분류기

---

## Archived Documents

더 이상 사용하지 않는 접근 방식에 대한 문서:

- [Deep Verification v2.0](archive/DEEP_VERIFICATION_V2.md) - v3.0 주장 수준 검증으로 대체됨
- [Claim Verification Plan](archive/CLAIM_VERIFICATION_PLAN.md) - 완료된 계획 문서

---

## Key Decisions Timeline

| Date | Decision | Rationale |
|------|----------|-----------|
| Jan 10 | Two-Source Rule | IFCN 규정 준수 |
| Jan 11 | Tier system | 출처 신뢰도 차별화 |
| Jan 13 | VeriScore claims | 2026 SOTA 구현 |
| Jan 15 | Gate ordering | 가장 비싼 것에서 가장 저렴한 순으로 |
| Jan 21 | Hybrid verification | LLM 비용 70% 절감 |
| Jan 23 | Zero-shot classifier | 추가 70% 절감 |
| Jan 23 | International focus | 양보다 질 |

---

## Changelog

상세 버전 기록은 [CHANGELOG.md](CHANGELOG.md)를 참조하세요.

---

## Related Documentation

- [Architecture Decisions](../adr/README.md) - ADRs
- [Architecture](../architecture/README.md) - 현재 설계
