# ADR-005: Bilingual Article Generation

## Status
Accepted

## Context

타겟 시장에는 영어와 한국어 사용자가 모두 포함됩니다. 두 사용자층을 모두 서비스하는 방법을 결정해야 했습니다:

1. **소스 언어**: 대부분의 뉴스 소스(GDELT, Reuters)는 영어
2. **타겟 사용자**: 영어 사용자 + 한국어 사용자
3. **품질 요구사항**: 두 언어 모두에서 전문적인 품질의 기사
4. **비용 고려**: 번역/생성 비용

옵션은 생성 후 번역부터 동시 이중 언어 생성까지 다양했습니다.

## Decision

기사가 단일 LLM 호출로 영어와 한국어 모두로 생성되는 **동시 이중 언어 생성**을 구현합니다.

### Generation Approach

```python
BILINGUAL_PROMPT = """
Generate a news article in both English and Korean.

Event: {event_summary}
Sources: {sources}

Output Format:
===ENGLISH===
[English article here]

===KOREAN===
[Korean article here (formal 합니다체)]
"""
```

### Korean Style: Formal (합니다체)

한국어에 격식체(합니다체)를 선택한 이유:
- 뉴스/저널리즘에 적합함
- 전문성과 권위를 전달함
- 한국 뉴스 매체의 표준
- 지나치게 캐주얼한 어조(해요체)를 피함

### Implementation Structure

```python
@dataclass
class BilingualArticle:
    english_title: str
    english_body: str
    korean_title: str
    korean_body: str
    sources: list[str]
    generated_at: datetime
```

## Consequences

### Positive
- **단일 LLM 호출**: 두 번의 별도 호출보다 효율적
- **일관된 콘텐츠**: 두 언어에 동일한 사실
- **네이티브 품질**: 번역이 아닌 생성 (더 자연스러움)
- **문화적 적응**: 각 사용자층에 맞게 표현 조정 가능
- **동시 제공**: 두 버전 모두 즉시 사용 가능

### Negative
- **높은 토큰 사용량**: 생성당 ~2배 토큰
- **단일 장애점**: 두 버전이 함께 실패
- **LLM 언어 편향**: 모델이 한 언어를 선호할 수 있음
- **품질 변동**: 한국어가 가끔 덜 자연스러울 수 있음
- **어려운 테스트**: 이중 언어 리뷰어가 필요함

## Alternatives Considered

### Alternative A: English-Only + Post-Translation
영어 기사를 생성한 다음 한국어로 번역합니다.

**기각 사유:**
- 번역이 종종 부자연스럽게 들림
- 두 번의 API 호출 (생성 + 번역)
- 번역 과정에서 뉘앙스가 손실될 수 있음
- 총 지연 시간이 더 길어짐

### Alternative B: Separate Generation Calls
별도의 LLM 호출로 영어와 한국어를 생성합니다.

**기각 사유:**
- 2배의 API 호출 및 비용
- 잠재적인 콘텐츠 불일치
- 총 처리 시간이 더 길어짐
- 더 복잡한 오류 처리

### Alternative C: Korean-Only Generation
소스가 영어이므로 한국어만 생성합니다.

**기각 사유:**
- 영어 사용자 제외
- 시장 도달 범위 제한
- 영어 소스가 종종 더 완전함
- 국제 사용자는 영어를 기대함

### Alternative D: User-Selected Language
요청 시에만 요청된 언어로 생성합니다.

**고려되었지만 연기된 이유:**
- 사용자 요청 지연 시간 추가
- 캐시 복잡성
- 나중에 최적화로 구현할 수 있음

## Quality Assurance

### Korean Quality Checks
- 격식체(합니다체) 일관성
- 적절한 한국어 문장 구조 (SOV)
- 주어에 대한 적절한 존칭
- 한국어 뉴스 용어

### English Quality Checks
- AP 스타일 규칙
- 중립적이고 객관적인 어조
- 적절한 출처 표시
- 능동태 선호

## Configuration

```python
# Agent settings
generate_korean: bool = True
korean_style: str = "formal"  # 합니다체 (formal) or 해요체 (informal)
```

## References
- 구현: `app/agent/bilingual_article_generator.py`
- 기사 스키마: `app/schemas/article.py`
- 프로젝트 문서: `docs/CODE.md`
