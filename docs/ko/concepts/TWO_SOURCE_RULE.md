# Two-Source Rule (2소스 규칙)

Two-Source Rule은 LiveMap이 정확성을 보장하기 위해 구현하는 기본 저널리즘 원칙입니다.

---

## 정의

> 이벤트는 게시 전 **2개 이상의 독립적인 소스**로부터 검증이 필요합니다.

이것은 AP, Reuters, BBC를 포함한 주요 뉴스 조직에서 사용하는 전문 저널리즘의 표준 관행입니다.

---

## 왜 두 개의 소스인가?

### 단일 소스의 문제점

| 시나리오 | 위험 |
|----------|------|
| 소스 오류 | 사실적 실수가 전파됨 |
| 소스 편향 | 일방적인 관점 |
| 의도적 허위 정보 | 검증되지 않은 거짓 주장 |
| 잘못된 해석 | 맥락 손실 |

### 다중 소스 검증의 이점

1. **오류 감지**: 다른 소스가 다른 실수를 포착
2. **편향 완화**: 다중 관점이 보도의 균형을 맞춤
3. **신뢰 구축**: 일치가 신뢰성을 높임
4. **맥락 풍부화**: 다른 각도가 더 완전한 그림 제공

---

## LiveMap에서의 구현

### 소스 독립성

소스가 "독립적"으로 간주되려면:

- 다른 조직
- 다른 주요 데이터 소스
- 공유된 소유권 또는 편집 통제 없음

**독립적**:
- GDELT (Reuters에서) + Reddit (사용자 보고) ✓
- USGS + NOAA (다른 기관) ✓

**독립적이지 않음**:
- 같은 언론사의 두 기사 ✗
- GDELT 기사와 그것의 Reddit 공유 ✗

### 예외

| 소스 유형 | 단일 소스 게시? | 근거 |
|-------------|------------------------|-----------|
| **Tier-1 정부** (USGS, NOAA) | 예 | 공식 권위 데이터 |
| **Tier-1 뉴스** (GDELT) 신뢰도 ≥ 0.70 | 예 | 확립된 편집 표준 |
| 모든 다른 소스 | 아니오 | 확인 필요 |

### 신뢰도 점수 영향

```python
# Two-source 충족
base_score = 0.70  # vs 단일 소스의 0.50

# 예시: GDELT + Reddit
sources = ["gdelt", "reddit"]
base_score = 0.70  # 2 소스
tier_average = (0.90 + 0.40) / 2 = 0.65
diversity_bonus = 0.03  # 다른 티어

final_score = (0.70 * 0.5) + (0.65 * 0.5) + 0.03 = 0.71
```

---

## IFCN 표준

Two-Source Rule은 International Fact-Checking Network (IFCN) 원칙과 일치합니다:

> "비당파성과 공정성에 대한 헌신은 팩트체커가 사실 주장에 대해 단일 소스에 의존하지 않을 것을 요구합니다."

---

## 예시

### Two-Source 충족

```
이벤트: "이란, 이라크 내 미군 기지에 미사일 발사"

소스 1: GDELT (AP 기사)
  - "이란, 미군에 탄도 미사일 발사"
  - 신뢰도: 0.90

소스 2: Reddit (r/worldnews)
  - "미군 기지 미사일 공격 다수 보고"
  - 신뢰도: 0.40

결과: Two-Source Rule 충족
권장: 게시 가능
```

### 단일 소스 (게시 안 함)

```
이벤트: "펜타곤 상공 UFO 목격"

소스 1: Reddit (r/conspiracy)
  - 사진이 있는 사용자 보고
  - 신뢰도: 0.40

결과: Two-Source Rule 미충족
권장: 게시 안 함 (확인 대기)
```

### Tier-1 정부 예외

```
이벤트: "알래스카 M6.2 지진"

소스: USGS (공식)
  - 공식 지진계 데이터
  - 신뢰도: 0.99

결과: Two-Source Rule 면제
권장: 즉시 게시
```

---

## 설정

```python
# config.py
class AgentSettings:
    # Two-Source Rule
    require_two_sources: bool = True

    # 예외
    tier1_govt_immediate_publish: bool = True
    tier1_news_min_confidence: float = 0.70
```

---

## 관련 문서

- [Source Tiers](SOURCE_TIERS.md) - 소스 분류 방법
- [Confidence Scoring](CONFIDENCE_SCORING.md) - 점수 계산 방법
- [ADR-001: Two-Source Rule](../adr/ADR-001-two-source-rule.md) - 설계 결정
