# Glossary

LiveMap 문서에서 사용되는 용어와 정의입니다.

---

## A

### ACLED
**Armed Conflict Location & Event Data Project**. 학술적 방법론을 사용하여 분쟁 데이터를 제공하는 Tier-2 연구 소스입니다.

### Atomic Claim
더 큰 텍스트에서 추출된 단일하고 검증 가능한 진술입니다. 더 이상 분해할 수 없습니다. 예: "3명의 군인이 부상당했다"는 원자적입니다. "이란이 공격했고 군인들이 부상당했다"는 원자적이지 않습니다.

### AP Style
뉴스 작성을 위한 **Associated Press Stylebook** 가이드라인입니다. LiveMap은 AP Style 2024-2026 규약을 따라 기사를 생성합니다.

---

## B

### BART-MNLI
**facebook/bart-large-mnli**. 이벤트 검증 2단계에서 사용되는 제로샷 분류 모델입니다. API 비용 없이 로컬에서 실행됩니다.

### BGE-M3
**BAAI/bge-m3**. 시맨틱 클러스터링 및 유사도 매칭에 사용되는 다국어 임베딩 모델입니다.

---

## C

### Claim Verification
이벤트에서 개별 주장을 추출하고 각각을 증거와 대조하여 검증하는 프로세스입니다. VeriScore 스타일 추출과 QA 기반 검증을 사용합니다.

### Clustering
임베딩 유사도를 사용하여 유사한 이벤트를 그룹화합니다. 중복을 줄이고 관련 보도를 식별합니다.

### Confidence Score
기사의 신뢰도를 나타내는 수치(0.00-1.00)입니다. 소스 수, 티어 신뢰도, 다양성을 기반으로 합니다.

### Cross-Source Matching
서로 다른 독립적인 소스에서 보도된 동일한 이벤트를 찾습니다. Two-Source Rule의 핵심입니다.

---

## D

### Deduplication
파이프라인에서 중복 이벤트를 제거합니다. 2계층 접근 방식: intra-scan(동일 스캔 내)과 inter-scan(데이터베이스 대조).

### Diversity Bonus
소스가 서로 다른 티어에서 오는 경우 +0.03의 신뢰도 보너스가 부여되며, 이는 독립적인 검증 경로를 나타냅니다.

---

## E

### Event Verification
파이프라인의 **Gate 0**입니다. 3단계 하이브리드 접근 방식(규칙, 제로샷 ML, LLM)을 사용하여 비이벤트(영화, 게임, 역사)를 필터링합니다.

---

## F

### False Positive
뉴스로 잘못 식별된 이벤트입니다. 예: "전쟁" 키워드에 매칭된 "신작 전쟁 영화 개봉".

---

## G

### Gate
저품질 콘텐츠를 제거하는 파이프라인의 필터링 단계입니다:
- **Gate 0**: 이벤트 검증 (실제 이벤트인가?)
- **Gate 1**: 보도 가치 (뉴스 가치가 있는가?)
- **Gate 2**: 구체성 (구체적인 세부사항이 있는가?)
- **Gate 3**: 증거 충분성 (충분한 증거가 있는가?)

### GDELT
**Global Database of Events, Language, and Tone**. Reuters, AP, BBC의 기사를 포함하여 글로벌 뉴스 커버리지를 제공하는 Tier-1 뉴스 소스입니다.

---

## H

### Hybrid Verification
비용 효율적인 필터링을 위해 여러 검증 방법(규칙 + ML + LLM)을 결합합니다. LLM만 사용하는 것 대비 91% 비용 절감.

---

## I

### IFCN
**International Fact-Checking Network**. LiveMap이 따르는 팩트체킹 5원칙을 정의하는 조직입니다.

### Investigation
이벤트를 심층 검증하고, 주장을 추출하고, 증거를 수집하고, 기사를 생성하는 프로세스입니다.

---

## L

### Lifespan
FastAPI 애플리케이션 라이프사이클 관리입니다. 시작 시 ML 모델 로딩과 종료 시 정리에 사용됩니다.

### LLM
**Large Language Model**. 주장 검증 및 기사 생성에 사용되는 OpenAI GPT-4o-mini입니다.

---

## M

### Multi-Source
정보를 검증하기 위해 여러 독립적인 소스를 사용합니다. LiveMap 방법론의 핵심 원칙입니다.

---

## N

### NEI
**Not Enough Information**. 주장을 지지하거나 반박할 증거가 불충분한 경우의 판정입니다.

### NOAA
**National Oceanic and Atmospheric Administration**. 기상 경보를 위한 Tier-1 정부 소스입니다.

---

## P

### Pipeline
이벤트 수집부터 기사 발행까지의 7단계 처리 흐름입니다.

### pgvector
벡터 유사도 검색을 위한 PostgreSQL 확장입니다. 임베딩 저장 및 유사도 쿼리에 사용됩니다.

---

## Q

### QA Verification
질문-답변 기반 검증입니다. 주장으로부터 질문을 생성하고 증거 문서를 사용하여 답변합니다.

---

## S

### Scanner
모든 소스에서 이벤트를 수집하고, 클러스터링하고, 필터를 적용하고, 검증된 이벤트를 조사를 위해 출력하는 주요 구성 요소입니다.

### Source Tier
신뢰도에 따른 데이터 소스 분류입니다:
- Tier-1: 정부(0.99) 및 주요 뉴스(0.90)
- Tier-2: 연구(0.85) 및 보조 뉴스(0.75)
- Tier-3: 소셜(0.40), 메시징(0.35), 트렌드(0.30)

---

## T

### Trigger
이벤트를 생성하는 데이터 소스입니다. 예: GDELT trigger, USGS trigger, Reddit trigger.

### Two-Source Rule
발행 전 2개 이상의 독립적인 소스를 요구하는 저널리즘 표준입니다. 예외: Tier-1 정부 소스.

---

## U

### USGS
**United States Geological Survey**. 지진 데이터를 위한 Tier-1 정부 소스입니다.

---

## V

### Verdict
주장 검증의 결론입니다:
- **SUPPORTED**: 증거가 주장을 확인함
- **REFUTED**: 증거가 주장을 반박함
- **NEI**: 정보 불충분

### VeriScore
텍스트를 원자적이고 검증 가능한 주장으로 분해하는 주장 추출 방법론입니다. LiveMap은 VeriScore 스타일 추출을 구현합니다.

---

## Z

### Zero-Shot Classification
태스크별 훈련 없이 수행하는 ML 분류입니다. BART-MNLI는 자연어 레이블을 사용하여 이벤트를 "military conflict" 또는 "sports" 같은 카테고리로 분류합니다.

---

## Acronyms

| Acronym | Full Form |
|---------|-----------|
| ADR | Architecture Decision Record |
| API | Application Programming Interface |
| CAMEO | Conflict and Mediation Event Observations |
| CLI | Command Line Interface |
| DB | Database |
| GDELT | Global Database of Events, Language, and Tone |
| IFCN | International Fact-Checking Network |
| LLM | Large Language Model |
| ML | Machine Learning |
| MNLI | Multi-Genre Natural Language Inference |
| NEI | Not Enough Information |
| NOAA | National Oceanic and Atmospheric Administration |
| ORM | Object-Relational Mapping |
| OSINT | Open Source Intelligence |
| SOTA | State of the Art |
| USGS | United States Geological Survey |

---

## Related Documentation

- [Overview](../OVERVIEW.md) - 시스템 개요
- [Concepts](../concepts/README.md) - 핵심 개념
