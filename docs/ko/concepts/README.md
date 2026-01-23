# 핵심 개념

이 섹션은 LiveMap 시스템을 이끄는 기본 개념과 원칙을 설명합니다.

---

## 개요

LiveMap은 세 가지 기본 원칙을 기반으로 구축되었습니다:

1. **다중 소스 검증** - 단일 진실의 소스 없음
2. **투명성** - 공개 방법론 및 신뢰도 점수
3. **정확성을 갖춘 속도** - 실시간이지만 검증됨

---

## 핵심 개념

### 검증 & 신뢰

- **[Two-Source Rule](TWO_SOURCE_RULE.md)** - 2개 이상의 독립 소스가 필요한 이유
- **[Source Tiers](SOURCE_TIERS.md)** - 소스가 분류되고 가중치가 부여되는 방법
- **[Confidence Scoring](CONFIDENCE_SCORING.md)** - 신뢰 점수가 계산되는 방법

### 집중 & 전략

- **[International Affairs Focus](INTERNATIONAL_AFFAIRS.md)** - 7개 카테고리에 집중하는 이유

---

## 빠른 참조

### Source Tier 요약

| Tier | 신뢰도 | 예시 | 단일 소스 게시? |
|------|-------------|----------|------------------------|
| Tier-1 정부 | 0.99 | USGS, NOAA | 예 |
| Tier-1 뉴스 | 0.90 | GDELT | 예 (≥0.70) |
| Tier-2 데이터 | 0.85 | ACLED | 아니오 |
| Tier-2 뉴스 | 0.75 | Currents, WorldNews | 아니오 |
| Tier-3 소셜 | 0.40 | Reddit, Bluesky | 아니오 |
| Tier-3 메시징 | 0.35 | Telegram | 아니오 |

### 카테고리 요약

| 카테고리 | 범위 | 예시 |
|----------|-------|----------|
| war | 무력 충돌 | 침략, 공습 |
| conflict | 지역 분쟁 | 국경 충돌, 내전 |
| politics | 국제 정치 | 정상회담, 제재 |
| security | 보안 위협 | 핵, 사이버 |
| military | 군사 활동 | 작전, 배치 |
| terrorism | 테러 이벤트 | 공격, 조직 |
| diplomacy | 외교 활동 | 조약, 협상 |

---

## IFCN 원칙

LiveMap은 International Fact-Checking Network의 5대 원칙을 따릅니다:

| 원칙 | 우리의 구현 |
|-----------|-------------------|
| 비당파성 | 알고리즘 기반, 편집 편향 없음 |
| 소스 투명성 | 모든 기사에 모든 소스 인용 |
| 자금 투명성 | 광고 또는 후원 콘텐츠 없음 |
| 방법론 투명성 | 공개 문서화 |
| 정정 정책 | 오류 발견 시 즉시 정정 |

---

## 관련 문서

- [아키텍처](../architecture/README.md) - 기술 구현
- [알고리즘](../algorithms/README.md) - 상세 알고리즘
