"""
v3 전체 10건 테스트.

Usage:
    cd backend
    python -m scripts.test_v3_full
"""

import asyncio
import logging
import re
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
logger = logging.getLogger("test_v3_full")

RESULTS_DIR = PROJECT_ROOT / "docs" / "v3-full-results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

TEST_CASES = [
    {
        "filename": "01-주4일제.md",
        "poll_id": "v3f-001",
        "poll_title": "주 4일제 도입, 찬성하십니까?",
        "poll_description": "근로시간 단축과 생산성 향상을 위한 주 4일제 전면 도입에 대한 의견을 묻습니다.",
        "poll_options": ["전면 도입", "단계적 도입", "시기상조"],
        "poll_category": "경제·노동",
    },
    {
        "filename": "02-의대정원.md",
        "poll_id": "v3f-002",
        "poll_title": "의대 정원 확대, 어떻게 생각하십니까?",
        "poll_description": "의사 부족 문제 해결을 위한 의대 정원 확대에 대한 의견을 묻습니다.",
        "poll_options": ["대폭 확대", "소폭 확대", "현행 유지"],
        "poll_category": "사회·보건",
    },
    {
        "filename": "03-상속세.md",
        "poll_id": "v3f-003",
        "poll_title": "상속세 최고세율 인하, 찬성하십니까?",
        "poll_description": "한국의 상속세 최고세율(50%)을 인하할 것인지에 대한 의견을 묻습니다.",
        "poll_options": ["대폭 인하", "소폭 인하", "현행 유지", "인상"],
        "poll_category": "경제·세금",
    },
    {
        "filename": "04-딥페이크.md",
        "poll_id": "v3f-004",
        "poll_title": "딥페이크 성범죄, 처벌을 더 강화해야 할까?",
        "poll_description": "AI 기술을 이용한 딥페이크 성범죄가 급증하고 있습니다. 현행 처벌 수준의 적절성과 표현의 자유 간 균형에 대한 의견을 묻습니다.",
        "poll_options": ["대폭 강화", "현행 유지", "표현의 자유 침해 우려"],
        "poll_category": "법·사회",
    },
    {
        "filename": "05-반려동물.md",
        "poll_id": "v3f-005",
        "poll_title": "반려동물 음식점 출입 허용, 찬성하십니까?",
        "poll_description": "반려동물 동반 음식점 출입 허용 여부에 대한 의견을 묻습니다.",
        "poll_options": ["찬성", "조건부 허용", "반대"],
        "poll_category": "생활·규제",
    },
    {
        "filename": "06-공매도.md",
        "poll_id": "v3f-006",
        "poll_title": "공매도 전면 재개, 어떻게 생각하십니까?",
        "poll_description": "2023년부터 금지된 공매도의 재개 방식에 대한 의견을 묻습니다.",
        "poll_options": ["전면 재개", "부분 재개", "금지 유지"],
        "poll_category": "경제·금융",
    },
    {
        "filename": "07-AI기본법.md",
        "poll_id": "v3f-007",
        "poll_title": "AI 기본법 시행, 규제 수준은 적절한가?",
        "poll_description": "2026년 시행 예정인 AI 기본법의 규제 수준에 대한 의견을 묻습니다.",
        "poll_options": ["더 강화", "적절", "완화 필요"],
        "poll_category": "기술·규제",
    },
    {
        "filename": "08-선거권연령.md",
        "poll_id": "v3f-008",
        "poll_title": "지방선거 선거권 연령을 16세로 낮춰야 할까?",
        "poll_description": "지방선거에서 선거권 연령을 현행 18세에서 16세로 낮추는 것에 대한 의견을 묻습니다.",
        "poll_options": ["찬성", "18세 유지", "반대"],
        "poll_category": "정치·사회",
    },
    {
        "filename": "09-원전확대.md",
        "poll_id": "v3f-009",
        "poll_title": "기후위기 대응, 원전 확대가 답인가?",
        "poll_description": "기후위기 대응을 위한 에너지 정책 방향에 대한 의견을 묻습니다.",
        "poll_options": ["원전 확대", "재생에너지 중심", "병행"],
        "poll_category": "환경·에너지",
    },
    {
        "filename": "10-고령운전.md",
        "poll_id": "v3f-010",
        "poll_title": "고령 운전자 면허 반납 의무화해야 할까?",
        "poll_description": "고령 운전자 교통사고 증가에 따른 면허 반납 의무화에 대한 의견을 묻습니다.",
        "poll_options": ["의무화", "자발적 유도", "반대"],
        "poll_category": "교통·안전",
    },
]

KOREAN_RE = re.compile(r"[가-힣]")


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
    checks = {}

    korean_sources = sum(1 for s in sources if KOREAN_RE.search(s.get("title", "")))
    checks["korean_src"] = f"{korean_sources}/{len(sources)}"
    checks["korean_pass"] = len(sources) == 0 or korean_sources >= len(sources) * 0.5

    has_conclusion = bool(re.search(r"#{2,3}\s*(결론|요약|정리|마무리)", article))
    checks["no_conclusion"] = not has_conclusion

    has_bold = "**" in article
    has_table = "|" in article and "---" in article
    has_bq = "\n> " in article or article.startswith("> ")
    checks["visual"] = f"b={'Y' if has_bold else 'N'} t={'Y' if has_table else 'N'} q={'Y' if has_bq else 'N'}"
    checks["visual_pass"] = sum([has_bold, has_table, has_bq]) >= 2

    blocked = ["namu.wiki", "blog.naver.com", "tistory.com", "wikipedia.org"]
    checks["no_blocked"] = not any(d in article for d in blocked)

    checks["numbered_cite"] = bool(re.search(r"\[\d+\]", article))
    checks["no_legacy"] = not bool(re.search(r"\[\^[^\]]+\|[^\]]+\]", article))

    checks["length"] = len(article)
    checks["length_pass"] = 800 <= len(article) <= 2500

    return checks


def _save_result(case: dict, final_state: dict, elapsed: float, checks: dict) -> str:
    filepath = RESULTS_DIR / case["filename"]
    article = final_state.get("final_article") or final_state.get("draft_article", "")
    web_sources = final_state.get("web_sources", [])

    md = f"""# {case['poll_title']}

## 체크
| 항목 | 결과 |
|------|------|
| 한국어 출처 | {checks['korean_src']} {'✅' if checks['korean_pass'] else '❌'} |
| 결론 없음 | {'✅' if checks['no_conclusion'] else '❌'} |
| 시각 요소 | {checks['visual']} {'✅' if checks['visual_pass'] else '❌'} |
| 차단 도메인 | {'✅' if checks['no_blocked'] else '❌'} |
| 인용 형식 | {'✅' if checks['numbered_cite'] else '❌'} |
| 길이 | {checks['length']}자 {'✅' if checks['length_pass'] else '❌'} |
| 시간 | {elapsed:.0f}초 |

## 아티클

{article}
"""
    filepath.write_text(md, encoding="utf-8")
    return str(filepath)


async def main():
    logger.info("v3 전체 테스트 (10건)")

    if not ai_settings.research_enabled:
        logger.error("API 키 미설정")
        sys.exit(1)

    graph = build_research_graph()
    total = len(TEST_CASES)
    results = []

    for i, case in enumerate(TEST_CASES, 1):
        logger.info(f"\n[{i}/{total}] {case['poll_title']}")

        initial_state = _build_initial_state(case)
        start = time.time()

        try:
            final_state = await graph.ainvoke(initial_state)
            elapsed = time.time() - start
        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"실패: {e}")
            final_state = {**initial_state, "error": str(e)}

        article = final_state.get("final_article") or final_state.get("draft_article", "")
        all_sources = final_state.get("web_sources", []) + final_state.get("academic_sources", [])
        checks = _check_quality(article, all_sources)
        _save_result(case, final_state, elapsed, checks)

        all_pass = all([
            checks["korean_pass"], checks["no_conclusion"], checks["visual_pass"],
            checks["no_blocked"], checks["numbered_cite"], checks["no_legacy"],
            checks["length_pass"],
        ])

        results.append({
            "title": case["poll_title"][:20],
            "elapsed": elapsed,
            "checks": checks,
            "all_pass": all_pass,
        })

        logger.info(f"  {'✅' if all_pass else '❌'} {checks['korean_src']} | "
                     f"결론={'N' if checks['no_conclusion'] else 'Y'} | "
                     f"{checks['visual']} | {checks['length']}자 | {elapsed:.0f}초")

        if i < total:
            await asyncio.sleep(5)

    # Summary
    print(f"\n{'='*70}")
    print("전체 결과 요약")
    print(f"{'='*70}")
    pass_count = 0
    for r in results:
        status = "✅" if r["all_pass"] else "❌"
        pass_count += r["all_pass"]
        c = r["checks"]
        print(f"  {status} {r['title']:<20} | src={c['korean_src']:>6} "
              f"| {c['visual']:>12} | {c['length']}자 | {r['elapsed']:.0f}s")

    print(f"\n통과: {pass_count}/{total}")
    print(f"결과: {RESULTS_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
