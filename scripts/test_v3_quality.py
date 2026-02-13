"""
v3 품질 개선 검증 테스트 (3건).

test_research.py 기반, 주 4일제 / 의대 정원 / 상속세 3건만 실행.

Usage:
    cd backend
    python -m scripts.test_v3_quality
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from app.services.research.config import ai_settings
from app.services.research.graph import build_research_graph
from app.services.research.state import ResearchState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_v3")

RESULTS_DIR = PROJECT_ROOT / "docs" / "v3-test-results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

TEST_CASES = [
    {
        "filename": "01-주4일제.md",
        "poll_id": "v3-001",
        "poll_title": "주 4일제 도입, 찬성하십니까?",
        "poll_description": "근로시간 단축과 생산성 향상을 위한 주 4일제 전면 도입에 대한 의견을 묻습니다.",
        "poll_options": ["전면 도입", "단계적 도입", "시기상조"],
        "poll_category": "경제·노동",
    },
    {
        "filename": "02-의대정원.md",
        "poll_id": "v3-002",
        "poll_title": "의대 정원 확대, 어떻게 생각하십니까?",
        "poll_description": "의사 부족 문제 해결을 위한 의대 정원 확대에 대한 의견을 묻습니다. 의료 접근성과 교육 품질을 함께 고려해주세요.",
        "poll_options": ["대폭 확대", "소폭 확대", "현행 유지"],
        "poll_category": "사회·보건",
    },
    {
        "filename": "03-상속세.md",
        "poll_id": "v3-003",
        "poll_title": "상속세 최고세율 인하, 찬성하십니까?",
        "poll_description": "한국의 상속세 최고세율(50%)을 인하할 것인지에 대한 의견을 묻습니다. 기업 승계와 부의 재분배를 함께 고려해주세요.",
        "poll_options": ["대폭 인하", "소폭 인하", "현행 유지", "인상"],
        "poll_category": "경제·세금",
    },
]


def _build_initial_state(case: dict) -> ResearchState:
    return ResearchState(
        poll_id=case["poll_id"],
        poll_title=case["poll_title"],
        poll_description=case["poll_description"],
        poll_options=case["poll_options"],
        poll_category=case["poll_category"],
        perspectives=[],
        search_queries=[],
        academic_queries=[],
        fact_check_claims=[],
        web_sources=[],
        academic_sources=[],
        fact_check_results=[],
        gap_report={},
        outline=[],
        draft_article="",
        review_feedback="",
        final_article="",
        extracted_sources=[],
        retry_count=0,
        error="",
    )


def _check_quality(article: str, sources: list) -> dict:
    """품질 체크리스트를 자동 검증합니다."""
    import re

    checks = {}

    # 1. 한국어 출처 확인
    korean_re = re.compile(r"[가-힣]")
    korean_sources = sum(1 for s in sources if korean_re.search(s.get("title", "")))
    checks["korean_sources"] = f"{korean_sources}/{len(sources)}"
    checks["korean_sources_pass"] = korean_sources >= len(sources) * 0.5

    # 2. 결론 섹션 없음
    has_conclusion = bool(re.search(r"#{2,3}\s*(결론|요약|정리|마무리)", article))
    checks["no_conclusion"] = not has_conclusion

    # 3. 시각 요소
    has_bold = "**" in article
    has_table = "|" in article and "---" in article
    has_blockquote = "\n> " in article or article.startswith("> ")
    visual_count = sum([has_bold, has_table, has_blockquote])
    checks["visual_elements"] = f"bold={has_bold}, table={has_table}, bq={has_blockquote}"
    checks["visual_pass"] = visual_count >= 2

    # 4. 차단 도메인 없음
    blocked = ["namu.wiki", "blog.naver.com", "tistory.com", "wikipedia.org"]
    found_blocked = [d for d in blocked if d in article]
    checks["no_blocked_domains"] = len(found_blocked) == 0
    if found_blocked:
        checks["blocked_found"] = found_blocked

    # 5. 인용 형식
    has_numbered = bool(re.search(r"\[\d+\]", article))
    has_legacy = bool(re.search(r"\[\^[^\]]+\|[^\]]+\]", article))
    checks["numbered_citations"] = has_numbered
    checks["no_legacy_citations"] = not has_legacy

    # 6. 길이
    checks["length"] = len(article)
    checks["length_pass"] = 800 <= len(article) <= 2500

    return checks


def _save_result(case: dict, final_state: dict, elapsed: float) -> str:
    filename = case["filename"]
    filepath = RESULTS_DIR / filename

    article = final_state.get("final_article") or final_state.get("draft_article", "")
    web_sources = final_state.get("web_sources", [])
    academic_sources = final_state.get("academic_sources", [])
    all_sources = web_sources + academic_sources

    checks = _check_quality(article, all_sources)

    md = f"""# {case['poll_title']} — v3 테스트 결과

## 품질 체크리스트

| 항목 | 결과 |
|------|------|
| 한국어 출처 비율 | {checks['korean_sources']} ({'✅' if checks['korean_sources_pass'] else '❌'}) |
| 결론 섹션 없음 | {'✅' if checks['no_conclusion'] else '❌'} |
| 시각 요소 2개+ | {checks['visual_elements']} ({'✅' if checks['visual_pass'] else '❌'}) |
| 차단 도메인 없음 | {'✅' if checks['no_blocked_domains'] else '❌ ' + str(checks.get('blocked_found', ''))} |
| 번호 인용 [N] | {'✅' if checks['numbered_citations'] else '❌'} |
| 레거시 인용 없음 | {'✅' if checks['no_legacy_citations'] else '❌'} |
| 길이 ({checks['length']}자) | {'✅' if checks['length_pass'] else '❌'} |

## 메타데이터

| 항목 | 값 |
|------|-----|
| 실행 시간 | {elapsed:.1f}초 |
| 웹 출처 | {len(web_sources)} |
| 학술 출처 | {len(academic_sources)} |
| 리뷰 통과 | {'YES' if final_state.get('final_article') else 'NO (draft)'} |
| 재시도 | {final_state.get('retry_count', 0)} |

## 생성된 아티클

{article or '(생성 실패)'}

---

## 출처 목록

### 웹 출처
"""

    for i, s in enumerate(web_sources[:15], 1):
        md += f"{i}. [{s.get('credibility', '?')}] {s.get('title', '')} — {s.get('url', '')}\n"

    md += "\n### 학술 출처\n"
    for i, s in enumerate(academic_sources[:10], 1):
        md += f"{i}. {s.get('title', '')} — {s.get('url', '')}\n"

    filepath.write_text(md, encoding="utf-8")
    logger.info(f"결과 저장: {filepath}")
    return str(filepath)


async def main():
    logger.info("v3 품질 검증 테스트 시작 (3건)")
    logger.info(f"Provider: {ai_settings.provider}")

    if not ai_settings.research_enabled:
        logger.error("API 키가 설정되지 않았습니다.")
        sys.exit(1)

    graph = build_research_graph()
    total = len(TEST_CASES)

    for i, case in enumerate(TEST_CASES, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"[{i}/{total}] {case['poll_title']}")
        logger.info(f"{'='*60}")

        initial_state = _build_initial_state(case)
        start = time.time()

        try:
            final_state = await graph.ainvoke(initial_state)
            elapsed = time.time() - start
        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"실행 실패: {e}", exc_info=True)
            final_state = {**initial_state, "error": str(e)}

        filepath = _save_result(case, final_state, elapsed)

        article = final_state.get("final_article") or final_state.get("draft_article", "")
        logger.info(f"완료 — {elapsed:.1f}초, {len(article)}자")

        if i < total:
            logger.info("5초 대기...")
            await asyncio.sleep(5)

    logger.info("\n테스트 완료! 결과: docs/v3-test-results/")


if __name__ == "__main__":
    asyncio.run(main())
