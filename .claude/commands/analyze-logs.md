---
allowed-tools: Bash(cat:*), Bash(grep:*), Bash(head:*), Bash(tail:*), Bash(wc:*), Bash(ls:*), Bash(sort:*), Bash(uniq:*), Bash(cut:*), Bash(sed:*), Bash(echo:*)
description: Analyze livemap server logs and generate comprehensive report
---

## Context

You are analyzing livemap server logs. The log files are stored in `logs/livemap_*.log`.

Latest log file: !`ls -t logs/livemap_*.log 2>/dev/null | head -1`
Log files count: !`ls logs/livemap_*.log 2>/dev/null | wc -l`

## Your Task

Analyze the latest (or specified) livemap server log file and provide a comprehensive Korean report.

### Analysis Commands

Run these commands to gather data:

```bash
LOG="[LOG_FILE_PATH]"

# 1. Session info
echo "세션 시작: $(head -1 "$LOG" | cut -d' ' -f1-2)"
echo "세션 종료: $(tail -1 "$LOG" | cut -d' ' -f1-2)"

# 2. Core metrics
echo "발행 기사: $(cat "$LOG" | grep -c 'Saved article')"
echo "POST-LLM 거부: $(cat "$LOG" | grep -c 'POST-LLM-DATE-REJECT')"
echo "중복 탐지: $(cat "$LOG" | grep -c 'REEMBED-DUPLICATE')"
echo "에러: $(cat "$LOG" | grep 'ERROR' | grep -vc 'No results')"

# 3. Category distribution
cat "$LOG" | grep 'Saved article' | sed 's/.*category=//' | cut -d',' -f1 | sort | uniq -c | sort -rn

# 4. POST-LLM rejections
cat "$LOG" | grep 'POST-LLM-DATE-REJECT'

# 5. Similarity analysis
cat "$LOG" | grep 'best match:' | grep -v 'N/A' | sort -t':' -k8 -rn | head -10

# 6. Errors (serious only)
cat "$LOG" | grep 'ERROR' | grep -v 'No results' | head -10

# 7. Published headlines
cat "$LOG" | grep 'canonical embedding for' | head -20
```

### Report Format

Output the report in this format:

```markdown
## 📊 로그 분석 보고서

**파일**: [filename]
**기간**: [start] ~ [end]
**운영 시간**: [calculated hours]

### 핵심 지표
| 지표 | 수치 | 평가 |
|-----|------|------|
| 발행 기사 | N | ✅/⚠️/❌ |
| POST-LLM 거부 | N | ✅/⚠️/❌ |
| 중복 탐지 | N | ✅/⚠️/❌ |
| 에러 | N | ✅/⚠️/❌ |

### 카테고리 분포
[table from grep results]

### POST-LLM 거부 목록 (과거 연도 차단)
[list with years]

### 유사도 분석
[highest similarity matches - check if potential duplicates]

### 에러 분석
[categorized error list]

### 발행 헤드라인 (상위 10개)
[numbered list]

### 개선 권고사항
- P0: [즉시 조치]
- P1: [단기 개선]
```

### Evaluation Criteria

- 발행 기사: ✅ 시간당 4-6개, ⚠️ 2-4개 또는 6개 초과, ❌ 2개 미만
- POST-LLM 거부: ✅ <5% of total, ⚠️ 5-10%, ❌ >10%
- 중복 탐지: ✅ >0 (working), ⚠️ 0 (check needed)
- 에러: ✅ <5, ⚠️ 5-15, ❌ >15

Reference template: `docs/templates/LOG_ANALYSIS_TEMPLATE.md`
