"""
Research Agent 실전 테스트 스크립트.

DB 없이 graph.ainvoke()를 직접 호출하여 3건의 여론조사 주제를 테스트합니다.
결과를 docs/research-results/ 폴더에 MD 파일로 저장합니다.

Usage:
    cd backend
    python -m scripts.test_research
"""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from app.services.research.config import ai_settings
from app.services.research.graph import build_research_graph
from app.services.research.state import ResearchState, SourceItem

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_research")

RESULTS_DIR = PROJECT_ROOT / "docs" / "research-results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────
# 테스트 케이스 정의
# ──────────────────────────────────────────────
TEST_CASES = [
    {
        "filename": "04-딥페이크.md",
        "poll_id": "test-004",
        "poll_title": "딥페이크 성범죄, 처벌을 더 강화해야 할까?",
        "poll_description": "AI 기술을 이용한 딥페이크 성범죄가 급증하고 있습니다. 현행 처벌 수준의 적절성과 표현의 자유 간 균형에 대한 의견을 묻습니다.",
        "poll_options": ["대폭 강화", "현행 유지", "표현의 자유 침해 우려"],
        "poll_category": "법·사회",
    },
    {
        "filename": "05-반려동물.md",
        "poll_id": "test-005",
        "poll_title": "반려동물 음식점 출입 허용, 찬성하십니까?",
        "poll_description": "반려동물 동반 음식점 출입 허용 여부에 대한 의견을 묻습니다. 반려인구 증가와 비반려인의 위생·알레르기 우려를 함께 고려해주세요.",
        "poll_options": ["찬성", "조건부 허용", "반대"],
        "poll_category": "생활·규제",
    },
    {
        "filename": "06-다주택자.md",
        "poll_id": "test-006",
        "poll_title": "부동산 다주택자 규제, 어떻게 해야 할까?",
        "poll_description": "주택 가격 안정과 재산권 보호 사이에서 다주택자 규제의 방향에 대한 의견을 묻습니다.",
        "poll_options": ["규제 강화", "현행 유지", "규제 완화"],
        "poll_category": "경제·부동산",
    },
    {
        "filename": "07-구글맵.md",
        "poll_id": "test-007",
        "poll_title": "구글맵 국내 지도 반출 허용해야 할까?",
        "poll_description": "구글의 국내 정밀지도 데이터 해외 반출 허용 여부에 대한 의견을 묻습니다. 산업 발전과 국가 안보 사이의 균형을 고려해주세요.",
        "poll_options": ["허용", "조건부 허용", "불허"],
        "poll_category": "기술·안보",
    },
    {
        "filename": "08-공매도.md",
        "poll_id": "test-008",
        "poll_title": "공매도 전면 재개, 어떻게 생각하십니까?",
        "poll_description": "2023년부터 금지된 공매도의 재개 방식에 대한 의견을 묻습니다. 시장 효율성과 개인투자자 보호를 함께 고려해주세요.",
        "poll_options": ["전면 재개", "부분 재개", "금지 유지"],
        "poll_category": "경제·금융",
    },
    {
        "filename": "09-AI기본법.md",
        "poll_id": "test-009",
        "poll_title": "AI 기본법 시행, 규제 수준은 적절한가?",
        "poll_description": "2026년 시행 예정인 AI 기본법의 규제 수준에 대한 의견을 묻습니다. AI 산업 육성과 위험 방지 사이의 균형을 고려해주세요.",
        "poll_options": ["더 강화", "적절", "완화 필요"],
        "poll_category": "기술·규제",
    },
    {
        "filename": "10-부자증세.md",
        "poll_id": "test-010",
        "poll_title": "부자 증세 vs 감세, 어느 쪽이 맞을까?",
        "poll_description": "고소득자·대기업에 대한 세금 정책 방향에 대한 의견을 묻습니다. 재정 건전성, 경제 성장, 소득 재분배를 함께 고려해주세요.",
        "poll_options": ["부자 증세", "현행 유지", "감세"],
        "poll_category": "경제·세금",
    },
    {
        "filename": "11-선거권연령.md",
        "poll_id": "test-011",
        "poll_title": "지방선거 선거권 연령을 16세로 낮춰야 할까?",
        "poll_description": "지방선거에서 선거권 연령을 현행 18세에서 16세로 낮추는 것에 대한 의견을 묻습니다. 청소년 정치 참여와 판단 능력을 함께 고려해주세요.",
        "poll_options": ["찬성", "18세 유지", "반대"],
        "poll_category": "정치·사회",
    },
    {
        "filename": "12-원전확대.md",
        "poll_id": "test-012",
        "poll_title": "기후위기 대응, 원전 확대가 답인가?",
        "poll_description": "기후위기 대응을 위한 에너지 정책 방향에 대한 의견을 묻습니다. 탄소 중립, 안전성, 경제성을 함께 고려해주세요.",
        "poll_options": ["원전 확대", "재생에너지 중심", "병행"],
        "poll_category": "환경·에너지",
    },
    {
        "filename": "13-고령운전.md",
        "poll_id": "test-013",
        "poll_title": "고령 운전자 면허 반납 의무화해야 할까?",
        "poll_description": "고령 운전자 교통사고 증가에 따른 면허 반납 의무화에 대한 의견을 묻습니다. 교통 안전과 이동권 보장을 함께 고려해주세요.",
        "poll_options": ["의무화", "자발적 유도", "반대"],
        "poll_category": "교통·안전",
    },
]


def _build_initial_state(case: dict) -> ResearchState:
    """테스트 케이스로부터 초기 상태를 생성합니다."""
    return ResearchState(
        poll_id=case["poll_id"],
        poll_title=case["poll_title"],
        poll_description=case["poll_description"],
        poll_options=case["poll_options"],
        poll_category=case["poll_category"],
        search_queries=[],
        academic_queries=[],
        fact_check_claims=[],
        web_sources=[],
        academic_sources=[],
        fact_check_results=[],
        draft_article="",
        review_feedback="",
        final_article="",
        extracted_sources=[],
        retry_count=0,
        error="",
    )


def _format_sources_md(sources: list[SourceItem]) -> str:
    """출처 목록을 마크다운 테이블로 포맷합니다."""
    if not sources:
        return "*출처 없음*"

    lines = ["| # | 제목 | URL | 유형 | 신뢰도 |"]
    lines.append("|---|------|-----|------|--------|")
    for i, s in enumerate(sources, 1):
        title = s.get("title", "")[:60]
        url = s.get("url", "")
        stype = s.get("source_type", "")
        cred = s.get("credibility", "")
        lines.append(f"| {i} | {title} | {url} | {stype} | {cred} |")
    return "\n".join(lines)


def _save_result(case: dict, final_state: dict, elapsed: float) -> str:
    """결과를 MD 파일로 저장합니다."""
    filename = case["filename"]
    filepath = RESULTS_DIR / filename

    final_article = final_state.get("final_article", "")
    draft_article = final_state.get("draft_article", "")
    article = final_article or draft_article or "(아티클 생성 실패)"

    web_sources = final_state.get("web_sources", [])
    academic_sources = final_state.get("academic_sources", [])
    fact_check_results = final_state.get("fact_check_results", [])
    extracted_sources = final_state.get("extracted_sources", [])
    retry_count = final_state.get("retry_count", 0)
    review_feedback = final_state.get("review_feedback", "")
    search_queries = final_state.get("search_queries", [])
    academic_queries = final_state.get("academic_queries", [])
    error = final_state.get("error", "")

    passed = bool(final_article)

    md = f"""# {case['poll_title']} — Research Agent 결과

## 메타데이터

| 항목 | 값 |
|------|-----|
| 실행 시간 | {elapsed:.1f}초 |
| 웹 검색 결과 수 | {len(web_sources)} |
| 학술 논문 결과 수 | {len(academic_sources)} |
| 팩트체크 결과 수 | {len(fact_check_results)} |
| 최종 출처 수 | {len(extracted_sources)} |
| 리뷰 통과 | {'YES' if passed else 'NO (draft 사용)'} |
| 재시도 횟수 | {retry_count} |
| 에러 | {error or '없음'} |

### Planner 생성 쿼리

**웹 검색 쿼리:**
{chr(10).join(f'- {q}' for q in search_queries) if search_queries else '- (없음)'}

**학술 검색 쿼리:**
{chr(10).join(f'- {q}' for q in academic_queries) if academic_queries else '- (없음)'}

---

## 생성된 아티클

{article}

---

## 수집된 출처

### 웹 출처
{_format_sources_md(web_sources)}

### 학술 출처
{_format_sources_md(academic_sources)}

### 팩트체크 결과
"""

    if fact_check_results:
        for i, fc in enumerate(fact_check_results, 1):
            md += f"\n{i}. **주장**: {fc.get('claim_text', '')}\n"
            md += f"   - 평가: {fc.get('rating', '없음')}\n"
            md += f"   - 출처: {fc.get('publisher', '')} — {fc.get('url', '')}\n"
    else:
        md += "\n*팩트체크 결과 없음*\n"

    md += f"""
---

## 품질 평가 (수동 체크)

- [ ] 인용 형식 `[^출처명|url]` 준수
- [ ] 모든 사실에 출처 인용
- [ ] 편향 없는 중립적 톤
- [ ] 자연스러운 아티클 흐름 (뉴스/잡지 스타일)
- [ ] 마크다운 시각 요소 적절 활용 (테이블, 볼드 등)
- [ ] 한국어 자연스러움
- [ ] 800-1500자 범위
- [ ] 관점 커버리지 (선택지에 대응)

### 아티클 길이: {len(article)}자

{f'### 리뷰 피드백 (마지막){chr(10)}{review_feedback}' if review_feedback else ''}
"""

    filepath.write_text(md, encoding="utf-8")
    logger.info(f"결과 저장: {filepath}")
    return str(filepath)


async def run_single_test(graph, case: dict, index: int, total: int) -> dict:
    """단일 테스트 케이스를 실행합니다."""
    title = case["poll_title"]
    logger.info(f"\n{'='*60}")
    logger.info(f"[{index}/{total}] 테스트 시작: {title}")
    logger.info(f"{'='*60}")

    initial_state = _build_initial_state(case)

    start = time.time()
    try:
        final_state = await graph.ainvoke(initial_state)
        elapsed = time.time() - start
        error = final_state.get("error", "")
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"[{index}/{total}] 실행 실패: {e}")
        final_state = {**initial_state, "error": str(e)}
        error = str(e)

    filepath = _save_result(case, final_state, elapsed)

    article = final_state.get("final_article") or final_state.get("draft_article", "")
    sources = final_state.get("extracted_sources", [])

    logger.info(f"[{index}/{total}] 완료 — {elapsed:.1f}초, "
                f"아티클 {len(article)}자, 출처 {len(sources)}개"
                f"{f', 에러: {error}' if error else ''}")

    return {
        "title": title,
        "elapsed": elapsed,
        "article_len": len(article),
        "source_count": len(sources),
        "passed": bool(final_state.get("final_article")),
        "retry_count": final_state.get("retry_count", 0),
        "filepath": filepath,
        "error": error,
    }


async def main():
    """10건의 테스트를 순차 실행합니다."""
    logger.info("Research Agent 대규모 실전 테스트 시작 (10건)")
    logger.info(f"Provider: {ai_settings.provider}")
    logger.info(f"AI Model: {ai_settings.AI_MODEL}")
    logger.info(f"Research enabled: {ai_settings.research_enabled}")
    logger.info(f"Tavily API: {'설정됨' if ai_settings.TAVILY_API_KEY else '미설정'}")
    logger.info(f"Semantic Scholar API: {'설정됨' if ai_settings.SEMANTIC_SCHOLAR_API_KEY else '미설정'}")
    logger.info(f"Google Fact Check API: {'설정됨' if ai_settings.GOOGLE_FACT_CHECK_API_KEY else '미설정'}")

    if not ai_settings.research_enabled:
        logger.error("ANTHROPIC_API_KEY 또는 TAVILY_API_KEY가 설정되지 않았습니다.")
        sys.exit(1)

    graph = build_research_graph()
    results = []
    total = len(TEST_CASES)

    for i, case in enumerate(TEST_CASES, 1):
        result = await run_single_test(graph, case, i, total)
        results.append(result)

        # API rate limit 고려 — 케이스 간 5초 대기
        if i < total:
            logger.info("다음 테스트까지 5초 대기...")
            await asyncio.sleep(5)

    # 요약 출력
    logger.info(f"\n{'='*60}")
    logger.info("전체 테스트 요약")
    logger.info(f"{'='*60}")
    for r in results:
        status = "PASS" if r["passed"] else "DRAFT"
        err_part = ""
        if r["error"]:
            err_msg = r["error"][:50]
            err_part = f", ERROR: {err_msg}"
        logger.info(
            f"  [{status}] {r['title'][:30]}... — "
            f"{r['elapsed']:.1f}s, {r['article_len']}자, "
            f"{r['source_count']}출처, retry={r['retry_count']}"
            f"{err_part}"
        )

    total_time = sum(r["elapsed"] for r in results)
    pass_count = sum(1 for r in results if r["passed"])
    logger.info(f"\n총 실행 시간: {total_time:.1f}초")
    logger.info(f"통과: {pass_count}/{total}")
    logger.info(f"결과 파일: {RESULTS_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
