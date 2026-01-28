# Configuration Reference

LiveMap 백엔드의 모든 설정 옵션에 대한 완전한 참조입니다.

## 환경 변수

모든 에이전트 설정은 `AGENT_` 접두사를 사용합니다.

### LLM 설정

| 변수 | 타입 | 기본값 | 설명 |
|----------|------|---------|-------------|
| `AGENT_OPENAI_API_KEY` | str | "" | OpenAI API 키 (LLM 기능에 필수) |
| `AGENT_LLM_MODEL` | str | "gpt-4o-mini" | 검증/생성용 LLM 모델 |
| `AGENT_LLM_TEMPERATURE` | float | 0.3 | LLM temperature (0=결정적, 1=창의적) |
| `AGENT_TAVILY_API_KEY` | str | "" | 웹 검색용 Tavily API 키 |

### Trigger 소스 설정

#### Tier-1 소스

| 변수 | 타입 | 기본값 | 설명 |
|----------|------|---------|-------------|
| `AGENT_GDELT_ENABLED` | bool | true | GDELT 뉴스 소스 활성화 |
| `AGENT_GDELT_TIMESPAN` | str | "2h" | GDELT 검색 기간 |
| `AGENT_GDELT_ANOMALY_ENABLED` | bool | true | GDELT 이상 탐지 활성화 |
| `AGENT_GDELT_USE_GKG_THEMES` | bool | true | 이상 탐지에 GKG 테마 사용 |
| `AGENT_GDELT_TONE_THRESHOLD` | float | -5.0 | Goldstein 톤 임계값 |
| `AGENT_USGS_ENABLED` | bool | false | USGS 지진 소스 활성화 |
| `AGENT_USGS_MIN_MAGNITUDE` | float | 5.0 | 최소 지진 규모 |
| `AGENT_NOAA_ENABLED` | bool | false | NOAA 기상 경보 활성화 |
| `AGENT_NOAA_SEVERITY` | str | "Extreme,Severe" | 기상 경보 심각도 |

#### Tier-2 소스

| 변수 | 타입 | 기본값 | 설명 |
|----------|------|---------|-------------|
| `AGENT_CURRENTS_ENABLED` | bool | false | Currents API 활성화 |
| `AGENT_CURRENTS_API_KEY` | str | "" | Currents API 키 |
| `AGENT_WORLDNEWS_ENABLED` | bool | false | World News API 활성화 |
| `AGENT_WORLDNEWS_API_KEY` | str | "" | World News API 키 |
| `AGENT_ACLED_ENABLED` | bool | false | ACLED 분쟁 데이터 활성화 |
| `AGENT_ACLED_API_KEY` | str | "" | ACLED API 키 |
| `AGENT_ACLED_EMAIL` | str | "" | ACLED 등록 이메일 |

#### Tier-3 소스

| 변수 | 타입 | 기본값 | 설명 |
|----------|------|---------|-------------|
| `AGENT_REDDIT_ENABLED` | bool | true | Reddit 소스 활성화 |
| `AGENT_REDDIT_SUBREDDITS` | str | "worldnews,news,..." | 쉼표로 구분된 서브레딧 |
| `AGENT_REDDIT_MIN_SCORE` | int | 50 | 최소 게시물 점수 |
| `AGENT_BLUESKY_ENABLED` | bool | false | Bluesky 소스 활성화 |
| `AGENT_BLUESKY_MIN_LIKES` | int | 10 | 최소 좋아요 수 |
| `AGENT_GOOGLE_TRENDS_ENABLED` | bool | false | Google Trends 활성화 |
| `AGENT_GOOGLE_TRENDS_GEO` | str | "US" | Trends 지역 |
| `AGENT_TWITTER_ENABLED` | bool | false | X/Twitter 활성화 |
| `AGENT_TWITTER_USERNAME` | str | "" | Twitter 사용자명 |
| `AGENT_TWITTER_EMAIL` | str | "" | Twitter 이메일 |
| `AGENT_TWITTER_PASSWORD` | str | "" | Twitter 비밀번호 |
| `AGENT_TELEGRAM_ENABLED` | bool | false | Telegram 활성화 |
| `AGENT_TELEGRAM_API_ID` | str | "" | Telegram API ID |
| `AGENT_TELEGRAM_API_HASH` | str | "" | Telegram API 해시 |
| `AGENT_TELEGRAM_PHONE` | str | "" | Telegram 전화번호 |
| `AGENT_TELEGRAM_CHANNELS` | str | "" | 쉼표로 구분된 채널 |

### 신뢰도 점수화

| 변수 | 타입 | 기본값 | 설명 |
|----------|------|---------|-------------|
| `AGENT_MIN_CONFIDENCE_SCORE` | float | 0.70 | 게시를 위한 최소 점수 |
| `AGENT_CROSS_SOURCE_SIMILARITY_THRESHOLD` | float | 0.70 | 교차 소스 매칭을 위한 유사도 |

### 스캐너 설정

| 변수 | 타입 | 기본값 | 설명 |
|----------|------|---------|-------------|
| `AGENT_SCAN_INTERVAL_MINUTES` | int | 15 | 스캔 주기 |
| `AGENT_MAX_NEWS_PER_SCAN` | int | 100 | 스캔당 최대 이벤트 |
| `AGENT_MAX_EVENTS_PER_CATEGORY` | int | 5 | 카테고리 제한 |
| `AGENT_ENSURE_CATEGORY_DIVERSITY` | bool | true | 다양성 인터리빙 활성화 |
| `AGENT_RECENCY_FILTER_ENABLED` | bool | **false** | Recency 필터 (비활성화 - 트리거에서 처리) |
| `AGENT_MAX_EVENT_AGE_HOURS` | int | 6 | 최대 이벤트 나이 (폴백용) |

### LLM 분류기 설정 (Phase 6 신규)

> Gate 0-2 패턴 기반 필터링을 LLM 분류기로 대체합니다.

| 변수 | 타입 | 기본값 | 설명 |
|----------|------|---------|-------------|
| `AGENT_LLM_CLASSIFIER_ENABLED` | bool | true | LLM 분류기 활성화 |
| `AGENT_DEEPINFRA_API_KEY` | str | "" | Deepinfra API 키 |
| `AGENT_DEEPINFRA_BASE_URL` | str | "https://api.deepinfra.com/v1/openai" | API 엔드포인트 |
| `AGENT_LLM_CLASSIFIER_MODEL` | str | "meta-llama/Meta-Llama-3.1-8B-Instruct" | 모델 |
| `AGENT_LLM_CLASSIFIER_BATCH_SIZE` | int | 20 | 배치 크기 |
| `AGENT_LLM_CLASSIFIER_TIMEOUT` | float | 30.0 | 타임아웃 (초) |
| `AGENT_LLM_CLASSIFIER_FALLBACK_ENABLED` | bool | true | 패턴 폴백 활성화 |
| `AGENT_DEDUP_BEFORE_LLM` | bool | true | LLM 전 Title Dedup (비용 절감) |

### 도메인 화이트리스트 설정 (Phase 6 신규)

> Tier-1/2 도메인만 허용하여 잡음을 줄입니다.

| 변수 | 타입 | 기본값 | 설명 |
|----------|------|---------|-------------|
| `AGENT_DOMAIN_WHITELIST_ENABLED` | bool | true | 화이트리스트 활성화 |
| `AGENT_TRUSTED_DOMAINS` | str | "reuters.com,apnews.com,..." | 신뢰 도메인 (59개) |

### 국제 정세 초점

| 변수 | 타입 | 기본값 | 설명 |
|----------|------|---------|-------------|
| `AGENT_FOCUS_INTERNATIONAL_AFFAIRS` | bool | true | 국제 카테고리에 초점 |
| `AGENT_INTERNATIONAL_AFFAIRS_CATEGORIES` | str | "war,conflict,politics,..." | 허용된 카테고리 |

### 중요도 점수화

| 변수 | 타입 | 기본값 | 설명 |
|----------|------|---------|-------------|
| `AGENT_MIN_PUBLISH_SCORE` | int | 40 | 최소 중요도 점수 |
| `AGENT_MIN_INVESTIGATE_SCORE` | int | 50 | 조사 트리거 점수 |
| `AGENT_USE_DETERMINISTIC_SCORING` | bool | true | 규칙 기반 점수화 사용 |
| `AGENT_USE_LLM_SCORING` | bool | true | LLM 점수화 사용 |
| `AGENT_COMBINE_SCORES` | bool | true | 두 점수 결합 |
| `AGENT_LOG_ALL_SCORES` | bool | true | 모든 점수 계산 로깅 |

### 콘텐츠 필터링 게이트

#### Gate 0: 이벤트 검증 (3단계 하이브리드)

자세한 내용은 [Zero-shot Classification](../architecture/ZERO_SHOT_CLASSIFIER.md)과 [Event Verification](../architecture/EVENT_VERIFICATION.md)을 참조하세요.

| 변수 | 타입 | 기본값 | 설명 |
|----------|------|---------|-------------|
| `AGENT_EVENT_VERIFICATION_ENABLED` | bool | true | Gate 0 활성화 (모든 단계) |
| `AGENT_EVENT_VERIFICATION_USE_ZERO_SHOT` | bool | true | Stage 2: Zero-shot 분류 |
| `AGENT_EVENT_VERIFICATION_USE_LLM` | bool | true | Stage 3: LLM 검증 |

#### Gate 1-3: 콘텐츠 품질

| 변수 | 타입 | 기본값 | 설명 |
|----------|------|---------|-------------|
| `AGENT_CHECKWORTHINESS_ENABLED` | bool | true | Gate 1 활성화 |
| `AGENT_ENTERTAINMENT_PATTERN_THRESHOLD` | int | 2 | 엔터테인먼트 패턴 개수 |
| `AGENT_SPECULATION_PATTERN_THRESHOLD` | int | 2 | 추측 패턴 개수 |
| `AGENT_HUMAN_INTEREST_PATTERN_THRESHOLD` | int | 3 | 휴먼 인터레스트 패턴 개수 |
| `AGENT_SPECIFICITY_ENABLED` | bool | true | Gate 2 활성화 |
| `AGENT_MIN_SPECIFICITY_SCORE` | float | 0.4 | 최소 구체성 (0-1) |
| `AGENT_EVIDENCE_GATE_ENABLED` | bool | true | Gate 3 활성화 |
| `AGENT_MIN_SUPPORTED_CLAIMS` | int | 1 | 최소 검증된 주장 |
| `AGENT_MIN_EVIDENCE_RATIO` | float | 0.3 | 최소 증거 비율 |
| `AGENT_LOG_GATE_REJECTIONS` | bool | true | 거부 이유 로깅 |

### 중복 제거

| 변수 | 타입 | 기본값 | 설명 |
|----------|------|---------|-------------|
| `AGENT_DEDUP_ENABLED` | bool | true | 중복 제거 활성화 |
| `AGENT_DEDUP_DUPLICATE_THRESHOLD` | float | 0.95 | 정확한 중복 임계값 |
| `AGENT_DEDUP_POTENTIAL_THRESHOLD` | float | 0.85 | 잠재적 일치 임계값 |
| `AGENT_DEDUP_RELATED_THRESHOLD` | float | 0.70 | 관련 이벤트 임계값 |
| `AGENT_DEDUP_TIME_WINDOW_DAYS` | int | 7 | 조회 시간 창 |
| `AGENT_DEDUP_LOG_ALL_SIMILARITIES` | bool | true | 유사도 점수 로깅 |

### 이중 언어 생성

| 변수 | 타입 | 기본값 | 설명 |
|----------|------|---------|-------------|
| `AGENT_GENERATE_KOREAN` | bool | true | 한국어 기사 생성 |
| `AGENT_KOREAN_STYLE` | str | "formal" | 한국어 스타일 (formal/informal) |

### 타임아웃

| 변수 | 타입 | 기본값 | 설명 |
|----------|------|---------|-------------|
| `AGENT_LLM_TIMEOUT_SECONDS` | float | 60.0 | LLM 호출 타임아웃 |
| `AGENT_MAX_CONCURRENT_LLM_CALLS` | int | 3 | 최대 병렬 LLM 호출 |
| `AGENT_INVESTIGATION_TIMEOUT_SECONDS` | float | 300.0 | 조사 타임아웃 |

## 예시 .env 파일

```bash
# 필수
OPENAI_API_KEY=sk-...

# 데이터베이스
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/livemap

# 에이전트 설정
AGENT_GDELT_ENABLED=true
AGENT_GDELT_TIMESPAN=30min
AGENT_REDDIT_ENABLED=false  # Phase 6: Tier-3 비활성화
AGENT_MIN_CONFIDENCE_SCORE=0.70
AGENT_SCAN_INTERVAL_MINUTES=15
AGENT_FOCUS_INTERNATIONAL_AFFAIRS=true

# Phase 6: LLM 분류기 (Gate 0-2 대체)
AGENT_LLM_CLASSIFIER_ENABLED=true
AGENT_DEEPINFRA_API_KEY=your_deepinfra_key_here
AGENT_LLM_CLASSIFIER_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
AGENT_DEDUP_BEFORE_LLM=true

# Phase 6: 도메인 화이트리스트
AGENT_DOMAIN_WHITELIST_ENABLED=true

# Phase 6: Recency 필터 비활성화 (트리거에서 처리)
AGENT_RECENCY_FILTER_ENABLED=false

# 선택: 추가 소스
AGENT_CURRENTS_ENABLED=false
AGENT_CURRENTS_API_KEY=
AGENT_WORLDNEWS_ENABLED=false
AGENT_WORLDNEWS_API_KEY=

# 로깅
AGENT_LOG_GATE_REJECTIONS=true
AGENT_DEDUP_LOG_ALL_SIMILARITIES=true
```

### 시간적 분류 설정 (Phase 6.1 신규)

> 회고/분석 기사와 예측 기사를 자동으로 필터링합니다.

| 변수 | 타입 | 기본값 | 설명 |
|----------|------|---------|-------------|
| `AGENT_TEMPORAL_CLASSIFICATION_ENABLED` | bool | true | 시간적 분류 활성화 |
| `AGENT_TEMPORAL_FILTER_ENABLED` | bool | true | 비발행 카테고리 자동 거부 |
| `AGENT_TEMPORAL_REJECT_CATEGORIES` | str | "retrospective,predictive" | 거부할 시간적 카테고리 |
| `AGENT_TEMPORAL_LOG_CLASSIFICATIONS` | bool | true | 분류 결과 로깅 |

**시간적 분류 카테고리**:

| 카테고리 | 시간 범위 | 발행 여부 | 예시 |
|---------|----------|----------|-----|
| `breaking` | 24시간 이내 | ✅ 발행 | "Russia launches offensive" |
| `developing` | 1-7일 | ✅ 발행 | "Day 5 of peace talks" |
| `retrospective` | 과거 분석 | ❌ 거부 | "Three years of war: Analysis" |
| `predictive` | 미래 예측 | ❌ 거부 | "What 2027 elections could mean" |
| `timeless` | 시간 무관 | ⚠️ 개별 평가 | "How sanctions work: Explainer" |

### 레거시 설정 (Phase 5 이전)

패턴 기반 Gate 시스템을 사용하려면:

```bash
# LLM 분류기 비활성화 → 패턴 폴백
AGENT_LLM_CLASSIFIER_ENABLED=false
AGENT_EVENT_VERIFICATION_ENABLED=true
AGENT_EVENT_VERIFICATION_USE_ZERO_SHOT=true
AGENT_EVENT_VERIFICATION_USE_LLM=true
```

## 코드에서 설정 사용

```python
from app.agent.config import agent_settings

# 설정 접근
if agent_settings.gdelt_enabled:
    manager.add_gdelt(timespan=agent_settings.gdelt_timespan)

# 임계값 확인
if confidence >= agent_settings.min_confidence_score:
    publish(event)
```

## 런타임 설정

일부 설정은 런타임에 재정의할 수 있습니다:

```python
# 커스텀 신뢰도 점수기
scorer = MultiSourceConfidenceScorer(
    min_publish_confidence=0.60  # 기본값 0.70 재정의
)

# 커스텀 교차 소스 매처
matcher = CrossSourceMatcher(
    similarity_threshold=0.80,  # 기본값 0.70 재정의
    time_window_hours=12  # 기본값 6 재정의
)
```
