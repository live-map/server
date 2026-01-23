# LiveMap 문서

> AI 기반 국제 정세 뉴스 검증 플랫폼

---

## 경로 선택

### 투자자 및 비즈니스용

> *"LiveMap이란 무엇이며 왜 중요한가?"*

| 문서 | 설명 |
|------|------|
| [**개요**](OVERVIEW.md) | 시스템 개요 및 핵심 차별점 |
| [**투자자 요약**](business/INVESTOR_SUMMARY.md) | 경영진 피치 및 비즈니스 모델 |
| [**로드맵**](business/ROADMAP.md) | 향후 개발 계획 |

**핵심 하이라이트:**
- 소스 비용 $0 (경쟁사 월 $20,000+ 대비)
- 전통 언론 대비 15-60분 빠른 속보
- 하이브리드 검증으로 91% LLM 비용 절감

---

### 사용자 및 기자용

> *"LiveMap의 정보를 어떻게 신뢰할 수 있나?"*

| 문서 | 설명 |
|------|------|
| [**개요**](OVERVIEW.md) | LiveMap 작동 방식 |
| [**신뢰도 점수**](concepts/CONFIDENCE_SCORING.md) | 신뢰 점수 계산 방법 |
| [**소스 Tier**](concepts/SOURCE_TIERS.md) | 소스 평가 방법 |
| [**2소스 규칙**](concepts/TWO_SOURCE_RULE.md) | 2개 이상 소스가 필요한 이유 |
| [**국제 정세 집중**](concepts/INTERNATIONAL_AFFAIRS.md) | 다루는 카테고리 |

**핵심 원칙:**
- IFCN 준수 방법론
- 투명한 신뢰도 점수
- 모든 출처 명시

---

### 기술 전문가용

> *"기술이 실제로 어떻게 작동하는가?"*

| 문서 | 설명 |
|------|------|
| [**아키텍처 개요**](architecture/README.md) | 시스템 아키텍처 |
| [**스캐너 파이프라인**](architecture/SCANNER_PIPELINE.md) | 7단계 처리 파이프라인 |
| [**이벤트 검증**](architecture/EVENT_VERIFICATION.md) | Gate 0 하이브리드 검증 |
| [**Zero-shot 분류기**](architecture/ZERO_SHOT_CLASSIFIER.md) | ML 기반 분류 |
| [**주장 검증**](architecture/CLAIM_VERIFICATION.md) | v3.0 SOTA 구현 |
| [**알고리즘**](algorithms/README.md) | 상세 알고리즘 문서 |
| [**ADR**](adr/README.md) | 아키텍처 결정 기록 |

**기술 하이라이트:**
- 2026 SOTA 구현 (AIC CTU, HerO 2, VeriScore)
- 3단계 하이브리드 검증 (규칙 → Zero-shot → LLM)
- BGE-M3 임베딩 + HDBSCAN 클러스터링

---

### 개발자용

> *"어떻게 설정하고 기여하는가?"*

| 문서 | 설명 |
|------|------|
| [**시작하기**](getting-started/README.md) | 5분 퀵스타트 |
| [**설치**](getting-started/INSTALLATION.md) | 상세 설정 가이드 |
| [**프로젝트 구조**](getting-started/PROJECT_STRUCTURE.md) | 코드베이스 구성 |
| [**API 레퍼런스**](api/README.md) | REST API 문서 |
| [**설정**](guides/CONFIGURATION.md) | 모든 설정 |
| [**트리거 가이드**](guides/TRIGGER_GUIDE.md) | 새 데이터 소스 추가 |
| [**테스트 가이드**](guides/TESTING_GUIDE.md) | 테스트 작성 |
| [**배포**](guides/DEPLOYMENT.md) | 프로덕션 배포 |
| [**문제 해결**](guides/TROUBLESHOOTING.md) | 일반적인 문제 |

**개발자 리소스:**
- 데이터베이스 스키마: [reference/DATABASE_SCHEMA.md](reference/DATABASE_SCHEMA.md)
- 용어집: [reference/GLOSSARY.md](reference/GLOSSARY.md)
- 보안: [security/README.md](security/README.md)

---

## 읽기 가이드

| 역할 | 가이드 |
|------|-------|
| 프로젝트 매니저 | [**READING_GUIDE.md**](READING_GUIDE.md) - 90분 구조화된 읽기 경로 |
| 투자자 | OVERVIEW → business/INVESTOR_SUMMARY → business/COMPETITIVE_ANALYSIS |
| 개발자 | getting-started/README → architecture → guides |

---

## 빠른 링크

| 필요한 것 | 이동 |
|----------|------|
| 시스템 개요 | [OVERVIEW.md](OVERVIEW.md) |
| 5분 설정 | [getting-started/README.md](getting-started/README.md) |
| API 엔드포인트 | [api/README.md](api/README.md) |
| 모든 설정 | [guides/CONFIGURATION.md](guides/CONFIGURATION.md) |
| 문제 해결 | [guides/TROUBLESHOOTING.md](guides/TROUBLESHOOTING.md) |

---

## 다른 언어

- [**English Documentation**](../en/README.md)

---

*최종 업데이트: 2026년 1월*
