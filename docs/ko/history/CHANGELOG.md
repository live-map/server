# Changelog

LiveMap 백엔드의 모든 주요 변경 사항이 이 문서에 기록됩니다.

---

## [3.6.1] - 2026-01-27

### Added
- **시간적 분류 강화** (`llm_classifier.py`) - Phase 6.1
  - `TemporalCategory` enum 추가 (BREAKING, DEVELOPING, RETROSPECTIVE, PREDICTIVE, TIMELESS)
  - 프롬프트에 현재 날짜 컨텍스트 포함
  - 시간적 언어 마커 기반 분류
  - RETROSPECTIVE/PREDICTIVE 기사 자동 거부
- 시간적 분류 설정 옵션
  - `temporal_classification_enabled`
  - `temporal_filter_enabled`
  - `temporal_reject_categories`

### Changed
- 프롬프트 길이 증가 (~300 → ~600 tokens)
- 회고/분석 기사 필터링 정확도 향상 (~85% → ~95%)

### Performance
- 비발행 기사 (회고/예측) 조기 필터링으로 파이프라인 효율 개선

---

## [3.6.0] - 2026-01-27

### Added
- **LLM 분류기** (`llm_classifier.py`) - Deepinfra Llama 3.1 8B 기반
  - 단일 프롬프트로 is_news, category, is_significant 판단
  - Gate 0-2 패턴 기반 필터링 대체
  - 배치 처리 지원 (기본 20개)
- **도메인 화이트리스트** (`source_tiers.py`) - 59개 Tier-1/2 도메인만 허용
- **Pre-LLM Title Deduplication** - LLM 호출 전 중복 제거로 비용 절감
- `dedup_before_llm` 설정 옵션

### Changed
- **Recency 필터 비활성화** - 트리거 레벨에서 이미 처리
  - `recency_filter_enabled: bool = False` 추가
  - 3중 검증 → 단일 검증으로 단순화
- Title Deduplication을 Step 6.5에서 Step 3.34로 이동
- Tier-3 소스 (Reddit 등) 기본 비활성화

### Removed
- Scanner 레벨 Recency 필터 (조건부 비활성화)
- 패턴 기반 Gate 의존성 (LLM 모드에서)

### Performance
- LLM 비용 ~25% 절감 (Pre-LLM dedup)
- 600+ 정규식 패턴 → 1개 프롬프트
- 예상 월 비용: $3-5 (Deepinfra)

---

## [3.5.0] - 2026-01-25

### Added
- **세션 기반 로깅** - 타임스탬프 로그 파일
- 포괄적 문서 업데이트 (Phase 1-5 히스토리, ADR, 알고리즘)

### Changed
- P2 유지보수 - 죽은 코드 제거, 오류 추적, LLM 타임아웃
- P0+P1 파이프라인 최적화

---

## [3.4.0] - 2026-01-24

### Added
- **속보 패스트패스** - Tier-1 소스 5초 내 발행
- **Goldstein Scale 중요도 점수** - 6차원 점수 시스템
- **도메인 티어 시스템** (ADR-011)
- Currents API, WorldNews API 통합 (Tier-2)
- 파이프라인 메트릭 시스템

### Changed
- Gate 스킵 메커니즘 - 속보는 Gate 0, 2, 3 스킵 가능

---

## [3.3.0] - 2026-01-23

### Added
- 이벤트 검증 Stage 2를 위한 **Zero-shot classifier** (BART-MNLI)
- 3단계 하이브리드 검증 파이프라인 (Rules → Zero-shot → LLM)
- 7개 카테고리의 국제 업무 집중
- 다국어 스포츠 패턴 감지 (한국어, 아랍어, 중국어)

### Changed
- 이벤트 검증 비용 $4.80/day에서 $1.44/day로 감소 (총 91% 절감)
- Scanner가 이제 비국제 이벤트를 조기에 필터링

### Performance
- Zero-shot 사전 필터링을 통해 LLM 호출 90% 감소

---

## [3.2.0] - 2026-01-21

### Added
- Gate 0: 규칙 기반 이벤트 검증
- Gate 1: 검토가치 필터
- Gate 2: 구체성 필터
- Scanner-Agent 통합

### Changed
- 파이프라인이 이제 7단계로 구성 (Gate 시스템 추가)
- 비영어 기사는 구체성 검사에서 면제

---

## [3.1.0] - 2026-01-14

### Added
- LLM 타임아웃 (60초)
- `asyncio.gather()`를 사용한 병렬 주장 검증
- 입력 유효성 검사 (최소/최대 길이)
- Scanner 루프의 오류 복구

### Changed
- Pydantic v2 `ConfigDict`로 마이그레이션

### Fixed
- 심층 분석에서 식별된 15개 코드 품질 이슈

---

## [3.0.0] - 2026-01-14

### Added
- **주장 수준 검증** (VeriScore 스타일)
- QA 기반 LLM 검증 (AIC CTU 접근 방식)
- AP Style 기사 생성
- 5단계 조사 파이프라인:
  1. 주장 추출
  2. 증거 검색
  3. QA 검증
  4. 집계
  5. 기사 합성

### Changed
- 이벤트 수준 검증을 주장 수준으로 대체
- 2026 SOTA 접근 방식으로 업데이트

### References
- AIC CTU (FEVER 8 우승)
- HerO 2 (AVeriTeC 2025)
- VeriScore

---

## [2.0.0] - 2026-01-13

### Added
- 심층 검증 에이전트
- LangGraph 통합
- 병렬 증거 수집
- 다중 소스 검색 도구

### Changed
- 에이전트 기반 아키텍처가 단순 파이프라인 대체

---

## [1.0.0] - 2026-01-11

### Added
- 3단계 검증 파이프라인
- 출처 등급 시스템 (Tier 1-3)
- Two-Source Rule 구현
- 신뢰도 점수 산정

---

## [0.1.0] - 2026-01-10

### Added
- 초기 프로젝트 설정
- Telegram MCP 통합
- GDELT 트리거
- 기본 이벤트 감지

---

## Legend

- **Added**: 새로운 기능
- **Changed**: 기존 기능 변경
- **Deprecated**: 곧 제거될 기능
- **Removed**: 제거된 기능
- **Fixed**: 버그 수정
- **Security**: 보안 업데이트
- **Performance**: 성능 개선
