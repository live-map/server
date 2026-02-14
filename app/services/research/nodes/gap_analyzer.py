"""
Gap Analyzer node — 관점별 출처 커버리지를 검증합니다.

CRAG (Corrective RAG) 패턴: 검색 후 합성 전에 커버리지 부족을 감지하고
필요시 추가 검색을 트리거합니다.
"""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.research.config import ai_settings
from app.services.research.schemas import GapReport
from app.services.research.state import ResearchState, SourceItem
from app.services.research.tools.tavily_client import TavilyClient

logger = logging.getLogger(__name__)

_GAP_SYSTEM = """당신은 리서치 커버리지를 분석하는 전문가입니다.

주어진 관점 목록과 수집된 출처를 비교하여:
1. 각 관점별로 충분한 출처가 있는지 확인하세요 (최소 2개).
2. 구체적 데이터/통계가 포함된 출처가 있는지 확인하세요.
3. 부족한 관점이 있으면 해당 관점에 맞는 추가 검색 쿼리를 생성하세요.

추가 검색 쿼리는 구체적이고 데이터 중심이어야 합니다 (예: "주 4일제 생산성 변화 통계 2024")."""

_GAP_USER = """## 관점 목록
{perspectives}

## 수집된 웹 출처 ({web_count}건)
{web_sources}

## 수집된 학술 출처 ({academic_count}건)
{academic_sources}

각 관점별 출처 커버리지를 분석하고, 부족한 관점에 대한 추가 검색 쿼리를 생성해주세요."""


def _format_perspectives(perspectives: list[dict]) -> str:
    parts = []
    for p in perspectives:
        questions = ", ".join(p.get("key_questions", []))
        parts.append(f"- **{p['label']}**: {p['description']} (질문: {questions})")
    return "\n".join(parts)


def _format_sources_brief(sources: list[SourceItem]) -> str:
    if not sources:
        return "(없음)"
    parts = []
    for i, s in enumerate(sources[:15], 1):
        parts.append(f"{i}. [{s['credibility']}] {s['title'][:60]} — {s['content_snippet'][:100]}")
    return "\n".join(parts)


async def gap_analyzer_node(state: ResearchState) -> dict:
    """관점별 출처 커버리지를 검증하고 부족시 추가 검색을 실행합니다."""
    perspectives = state.get("perspectives", [])
    web_sources = state.get("web_sources", [])
    academic_sources = state.get("academic_sources", [])

    if not perspectives:
        logger.info("[GapAnalyzer] No perspectives, skipping")
        return {"gap_report": {}}

    logger.info(
        f"[GapAnalyzer] Analyzing coverage: {len(perspectives)} perspectives, "
        f"{len(web_sources)} web + {len(academic_sources)} academic sources"
    )

    llm = ai_settings.get_chat_model(role="planner", max_tokens=1024, temperature=0.2)
    structured_llm = llm.with_structured_output(GapReport)

    user_msg = _GAP_USER.format(
        perspectives=_format_perspectives(perspectives),
        web_count=len(web_sources),
        web_sources=_format_sources_brief(web_sources),
        academic_count=len(academic_sources),
        academic_sources=_format_sources_brief(academic_sources),
    )

    try:
        report: GapReport = await structured_llm.ainvoke([
            SystemMessage(content=_GAP_SYSTEM),
            HumanMessage(content=user_msg),
        ])
    except Exception as e:
        logger.error(f"[GapAnalyzer] LLM analysis failed: {e}")
        return {"gap_report": {"summary": "분석 실패"}}

    gap_report = {
        "covered": report.covered_perspectives,
        "gaps": report.gap_perspectives,
        "summary": report.summary,
    }

    # 갭이 있으면 추가 검색 실행
    extra_sources: list[SourceItem] = []
    if report.follow_up_queries:
        logger.info(
            f"[GapAnalyzer] Found gaps in {report.gap_perspectives}. "
            f"Running {len(report.follow_up_queries)} follow-up queries"
        )
        client = TavilyClient()
        for query in report.follow_up_queries[:3]:
            try:
                results = await client.search(query, max_results=3)
                extra_sources.extend(results)
            except Exception as e:
                logger.error(f"[GapAnalyzer] Follow-up search failed: {e}")

        if extra_sources:
            logger.info(f"[GapAnalyzer] Found {len(extra_sources)} additional sources")

    result: dict = {"gap_report": gap_report}
    if extra_sources:
        result["web_sources"] = extra_sources  # append via operator.add

    return result
