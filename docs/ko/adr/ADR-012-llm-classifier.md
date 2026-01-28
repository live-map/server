# ADR-012: LLM 분류기로 패턴 기반 필터링 대체

## 상태
**수락됨** (2026-01-27)

## 컨텍스트

### 기존 시스템
패턴 기반 Gate 시스템으로 뉴스 필터링:
- Gate 0 (이벤트 검증): ~200개 정규식
- Gate 1 (Check-worthiness): ~150개 정규식
- Gate 2 (Specificity): ~100개 정규식
- 기타 카테고리 패턴: ~150개 정규식
- **총 600+ 정규식 패턴**

### 문제점

1. **맥락 무시**
   ```
   "Warsaw summit" → "war" 매칭 → 오분류
   "War movie review" → "war" 매칭 → 오분류
   ```

2. **유지보수 어려움**
   - 새 패턴 추가 시 기존 패턴과 충돌
   - 엣지 케이스마다 패턴 추가 필요
   - 코드 복잡도 증가

3. **다국어 한계**
   - 영어 패턴만 존재
   - 새 언어 지원 시 패턴 세트 복제 필요

4. **False Positive/Negative**
   - 단순 문자열 매칭의 한계
   - 뉴앙스/맥락 이해 불가

## 결정

**600+ 정규식 패턴을 단일 LLM 프롬프트로 대체**

### 선택한 접근법
- Deepinfra API + Llama 3.1 8B Instruct
- 단일 프롬프트로 is_news, category, is_significant 판단
- 배치 처리 (20개 기사/요청)

### 대안 비교

| 접근법 | 비용 | 정확도 | 유지보수 | 선택 |
|--------|------|--------|----------|------|
| 패턴 유지 | $0 | ~85% | 높음 | X |
| **LLM 분류** | $3-5/월 | ~95% | 낮음 | **O** |
| ML 모델 학습 | $0 (추론) | ~90% | 중간 | X |
| 하이브리드 | $1-2/월 | ~93% | 중간 | X |

### 선택 근거
1. **비용 효율**: Deepinfra Llama 8B는 매우 저렴 (~$0.03/1M 입력)
2. **정확도**: 맥락 이해로 False Positive 감소
3. **유지보수**: 프롬프트 한 줄 수정 vs 패턴 수십 개 수정
4. **다국어**: 자동 지원 (추가 작업 없음)

## 구현

### LLM 분류기 (`llm_classifier.py`)

```python
CLASSIFICATION_PROMPT = """
You are a breaking international news classifier.
Today's date: {current_date}

For each article, determine:
1. TEMPORAL_CATEGORY: breaking|developing|retrospective|predictive|timeless
2. IS_NEWS: Is this a real breaking news event?
3. CATEGORY: war|conflict|politics|security|military|terrorism|diplomacy|protest|other
4. IS_SIGNIFICANT: Is this internationally significant?

Return JSON: {
  "temporal_category": str,
  "is_news": bool,
  "category": str,
  "is_significant": bool,
  "temporal_markers_found": list,
  "reason": str
}
"""
```

### 시간적 분류 체계 (Phase 6 강화)

| 카테고리 | 시간 범위 | 발행 여부 | 언어적 특징 |
|---------|----------|----------|-----------|
| **BREAKING** | 24시간 이내 | ✅ 발행 | "just", "breaking", 현재진행형 |
| **DEVELOPING** | 1-7일 | ✅ 발행 | "latest update", "Day N of" |
| **RETROSPECTIVE** | 7일+ | ❌ 거부 | "years later", "looking back", "analysis" |
| **PREDICTIVE** | 미래 지향 | ❌ 거부 | "could", "may", "expected to" |
| **TIMELESS** | 시간 무관 | ⚠️ 개별 평가 | 백과사전적 콘텐츠 |

### 설정 (`config.py`)

```python
llm_classifier_enabled: bool = True
deepinfra_api_key: str = ""
llm_classifier_model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct"
llm_classifier_batch_size: int = 20
llm_classifier_fallback_enabled: bool = True  # 패턴 폴백
```

### 파이프라인 통합 (`scanner.py`)

```python
# Step 3.35: LLM Classification
if use_llm_classification:
    llm_result = await classify_articles(articles_for_llm)
    # is_news=False → 거부
    # is_significant=False → 거부
    # category=other → 거부
```

## 결과

### 기대 효과

| 지표 | 이전 | 이후 |
|------|------|------|
| 패턴 수 | 600+ | 1 (프롬프트) |
| 오분류 수정 시간 | 수 시간 | 수 분 |
| 다국어 지원 | 패턴 추가 필요 | 자동 |
| 월 비용 | $0 | $3-5 |

### 리스크 및 완화

| 리스크 | 완화 |
|--------|------|
| API 장애 | `llm_classifier_fallback_enabled=True` |
| 환각 | JSON 구조 강제, confidence 임계값 |
| 비용 초과 | 배치 처리, 일일 한도 |

## 관련 문서

- [Phase 6 히스토리](../history/PHASE_6_LLM_CLASSIFIER.md)
- [ADR-004: 하이브리드 검증](ADR-004-hybrid-verification.md)
- [Source Tiers](../algorithms/SOURCE_TIERS.md)

## 변경 이력

| 날짜 | 변경 | 작성자 |
|------|------|--------|
| 2026-01-27 | 초안 작성 | Claude |
| 2026-01-27 | 시간적 분류 체계 추가 (TemporalCategory) | Claude |
