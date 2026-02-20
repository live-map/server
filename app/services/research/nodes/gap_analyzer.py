"""
Gap Analyzer node — 관점별 출처 커버리지를 검증합니다.

CRAG (Corrective RAG) 패턴: 검색 후 합성 전에 커버리지 부족을 감지하고
필요시 추가 검색을 트리거합니다.
"""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.research.config import ai_settings
from app.services.research.nodes.web_search import _is_relevant_source
from app.services.research.prompts.gap_analyzer_prompt import GAP_SYSTEM, GAP_USER
from app.services.research.schemas import GapReport
from app.services.research.state import ResearchState, SourceItem
from app.services.research.tools.duckduckgo_client import DuckDuckGoClient
from app.services.research.tools.tavily_client import TavilyClient
from app.services.research.utils import format_perspectives_inline

logger = logging.getLogger(__name__)


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
        "[GapAnalyzer] Analyzing coverage: %d perspectives, %d web + %d academic sources",
        len(perspectives), len(web_sources), len(academic_sources),
    )

    llm = ai_settings.get_chat_model(role="planner", max_tokens=1024, temperature=0.2)
    structured_llm = llm.with_structured_output(GapReport)

    user_msg = GAP_USER.format(
        perspectives=format_perspectives_inline(perspectives),
        web_count=len(web_sources),
        web_sources=_format_sources_brief(web_sources),
        academic_count=len(academic_sources),
        academic_sources=_format_sources_brief(academic_sources),
    )

    try:
        report: GapReport = await structured_llm.ainvoke([
            SystemMessage(content=GAP_SYSTEM),
            HumanMessage(content=user_msg),
        ])
    except Exception as e:
        logger.error("[GapAnalyzer] LLM analysis failed: %s", e)
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
            "[GapAnalyzer] Found gaps in %s. Running %d follow-up queries",
            report.gap_perspectives, len(report.follow_up_queries),
        )
        if ai_settings.TAVILY_API_KEY:
            client = TavilyClient()
        else:
            client = DuckDuckGoClient()
        for query in report.follow_up_queries[:3]:
            try:
                results = await client.search(query, max_results=3)
                extra_sources.extend(results)
            except Exception as e:
                logger.error("[GapAnalyzer] Follow-up search failed: %s", e)

        # 소스 필터링 적용 (web_search와 동일 기준)
        if extra_sources:
            before = len(extra_sources)
            extra_sources = [s for s in extra_sources if _is_relevant_source(s)]
            filtered = before - len(extra_sources)
            if filtered:
                logger.info("[GapAnalyzer] Filtered %d irrelevant follow-up sources", filtered)
            logger.info("[GapAnalyzer] Found %d additional sources", len(extra_sources))

    result: dict = {"gap_report": gap_report}
    if extra_sources:
        result["web_sources"] = extra_sources  # append via operator.add

    return result
