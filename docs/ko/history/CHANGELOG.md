# Changelog

LiveMap 백엔드의 모든 주요 변경 사항이 이 문서에 기록됩니다.

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
