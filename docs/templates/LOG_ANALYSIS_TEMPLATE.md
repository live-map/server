# 로그 분석 템플릿 (Log Analysis Template)

**목적**: 서버 로그 분석을 통한 성능 측정 및 품질 검증

---

## 분석 명령어 모음

### 1. 기본 통계

```bash
LOG="logs/livemap_YYYY-MM-DD_HH-MM-SS.log"

# 세션 시작/종료
echo "세션 시작: $(head -1 "$LOG" | cut -d' ' -f1-2)"
echo "세션 종료: $(tail -1 "$LOG" | cut -d' ' -f1-2)"

# 핵심 지표
echo "발행 기사: $(cat "$LOG" | grep -c 'Saved article')"
echo "POST-LLM 거부: $(cat "$LOG" | grep -c 'POST-LLM-DATE-REJECT')"
echo "중복 탐지: $(cat "$LOG" | grep -c 'REEMBED-DUPLICATE')"
echo "URL 날짜 거부: $(cat "$LOG" | grep -c 'RECENCY.*Rejected')"
echo "에러 (No results 제외): $(cat "$LOG" | grep 'ERROR' | grep -vc 'No results')"
```

### 2. 카테고리 분포

```bash
cat "$LOG" | grep 'Saved article' | sed 's/.*category=//' | cut -d',' -f1 | sort | uniq -c | sort -rn
```

### 3. POST-LLM 날짜 거부 상세

```bash
cat "$LOG" | grep 'POST-LLM-DATE-REJECT'
```

### 4. 중복 유사도 분석

```bash
# 가장 높은 유사도 매칭
cat "$LOG" | grep 'best match:' | grep -v 'N/A' | sort -t':' -k8 -rn | head -10
```

### 5. 에러 분석

```bash
# 심각한 에러만 (No results 제외)
cat "$LOG" | grep 'ERROR' | grep -v 'No results' | head -20

# 에러 유형별 카운트
cat "$LOG" | grep 'ERROR' | grep -v 'No results' | grep -oE 'ERROR.*\|' | sort | uniq -c
```

### 6. 발행 속도 추적

```bash
# 특정 키워드로 이벤트 추적
cat "$LOG" | grep -E "KEYWORD|event_id=N" | head -10
```

### 7. 발행된 헤드라인 목록

```bash
cat "$LOG" | grep 'canonical embedding for' | sed 's/.*canonical embedding for: //' | sed 's/\.\.\..*//'
```

### 8. 스캔 빈도

```bash
cat "$LOG" | grep 'scan:' | head -30
```

---

## 핵심 지표 정의

| 지표 | 계산 방법 | 목표값 | 비고 |
|-----|----------|-------|-----|
| **발행률** | 발행 / (발행 + 거부) | >30% | 높을수록 효율적 |
| **중복 방지율** | 중복탐지 / (발행 + 중복탐지) | >10% | 낮으면 중복 우려 |
| **과거 기사 차단율** | POST-LLM 거부 / 총 LLM 처리 | <5% | 높으면 소스 품질 문제 |
| **에러율** | 심각 에러 / 총 스캔 | <1% | 낮을수록 안정적 |
| **평균 발행 속도** | 탐지→저장 시간 | <2분 | 빠를수록 좋음 |
| **시간당 발행량** | 발행 / 운영 시간 | 4-6개/h | 너무 많으면 품질 확인 |

---

## 보고서 템플릿

```markdown
## 📊 로그 분석 보고서

**파일**: [filename]
**기간**: [start] ~ [end]
**운영 시간**: [hours]시간

### 핵심 지표
| 지표 | 수치 | 평가 |
|-----|------|------|
| 발행 기사 | N | ✅/⚠️/❌ |
| POST-LLM 거부 | N | ✅/⚠️/❌ |
| 중복 탐지 | N | ✅/⚠️/❌ |
| 에러 | N | ✅/⚠️/❌ |

### 카테고리 분포
[table]

### POST-LLM 거부 목록
[list with years]

### 에러 분석
[categorized list]

### 발행 헤드라인 (상위 10개)
[numbered list]

### 개선 권고사항
- P0: [즉시 조치]
- P1: [단기 개선]
- P2: [장기 개선]
```

---

## 한국 언론 비교 기준

### 비교 항목

| 항목 | 측정 방법 | 데이터 소스 |
|-----|----------|-----------|
| **속보 속도** | 트리거 감지 → 발행 시간 | 로그 타임스탬프 |
| **동일 사건 최초 보도** | 국내 언론 첫 기사 시점 | 네이버 뉴스 검색 |
| **커버리지 차이** | 발행된 국제뉴스 vs 국내 언론 | 수동 비교 |

### 주요 한국 언론 RSS

```
연합뉴스: https://www.yonhapnews.co.kr/RSS/
조선일보: https://www.chosun.com/arc/outboundfeeds/rss/
한겨레: https://www.hani.co.kr/rss/
```

---

## 자동화 스크립트

### 일일 분석 스크립트

```bash
#!/bin/bash
# daily_log_analysis.sh

LOG_DIR="/Users/iyeonsang/Desktop/project/livemap/backend/logs"
LATEST_LOG=$(ls -t "$LOG_DIR"/livemap_*.log | head -1)

echo "=== 일일 로그 분석 ==="
echo "파일: $LATEST_LOG"
echo ""
echo "=== 기본 통계 ==="
echo "발행: $(grep -c 'Saved article' "$LATEST_LOG")"
echo "POST-LLM 거부: $(grep -c 'POST-LLM-DATE-REJECT' "$LATEST_LOG")"
echo "중복 탐지: $(grep -c 'REEMBED-DUPLICATE' "$LATEST_LOG")"
echo ""
echo "=== 카테고리 ==="
grep 'Saved article' "$LATEST_LOG" | sed 's/.*category=//' | cut -d',' -f1 | sort | uniq -c | sort -rn
echo ""
echo "=== 에러 (상위 5개) ==="
grep 'ERROR' "$LATEST_LOG" | grep -v 'No results' | head -5
```

---

*마지막 업데이트: 2026-01-28*
