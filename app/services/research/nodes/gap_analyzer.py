"""
Gap Analyzer node — 관점별 출처 커버리지를 검증합니다.

CRAG (Corrective RAG) 패턴: 검색 후 합성 전에 커버리지 부족을 감지하고
필요시 추가 검색을 트리거합니다.
"""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.research.config import (
    DEFAULT_MAX_TOKENS,
    GAP_ANALYSIS_SOURCE_LIMIT,
    GAP_FOLLOWUP_QUERIES,
    GAP_FOLLOWUP_RESULTS,
    ai_settings,
)
from app.services.research.nodes.web_search import _is_relevant_source
from app.services.research.prompts.gap_analyzer_prompt import GAP_SYSTEM, GAP_USER
from app.services.research.schemas import GapReport
from app.services.research.state import ResearchState, SourceItem
from app.services.research.tools.duckduckgo_client import DuckDuckGoClient
from app.services.research.tools.tavily_client import TavilyClient
from app.services.research.utils import filter_by_graded_urls, format_perspectives_inline

logger = logging.getLogger(__name__)


def _format_sources_brief(sources: list[SourceItem]) -> str:
    if not sources:
        return "(없음)"
    parts = []
    for i, s in enumerate(sources[:GAP_ANALYSIS_SOURCE_LIMIT], 1):
        parts.append(f"{i}. [{s['credibility']}] {s['title'][:60]} — {s['content_snippet'][:100]}")
    return "\n".join(parts)


async def gap_analyzer_node(state: ResearchState) -> dict:
    """관점별 출처 커버리지를 검증하고 부족시 추가 검색을 실행합니다."""
    perspectives = state.get("perspectives", [])
    web_sources = filter_by_graded_urls(
        state.get("web_sources", []), state.get("graded_web_urls", [])
    )
    academic_sources = filter_by_graded_urls(
        state.get("academic_sources", []), state.get("graded_academic_urls", [])
    )

    if not perspectives:
        logger.info("[GapAnalyzer] No perspectives, skipping")
        return {"gap_report": {}}

    logger.info(
        "[GapAnalyzer] Analyzing coverage: %d perspectives, %d web + %d academic sources",
        len(perspectives), len(web_sources), len(academic_sources),
    )

    llm = ai_settings.get_chat_model(role="planner", max_tokens=DEFAULT_MAX_TOKENS, temperature=0.2)
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

    # 갭이 있으면 추가 검색 실행 (+ ambiguous requery 병합)
    ambiguous_requery = state.get("ambiguous_requery", [])
    all_followup_queries = ambiguous_requery + (report.follow_up_queries or [])

    # 기존 소스 URL 수집 (중복 방지)
    existing_urls: set[str] = {s["url"] for s in web_sources + academic_sources if s.get("url")}

    extra_sources: list[SourceItem] = []
    if all_followup_queries:
        logger.info(
            "[GapAnalyzer] Running %d follow-up queries (gaps: %s, ambiguous: %d)",
            len(all_followup_queries), report.gap_perspectives, len(ambiguous_requery),
        )
        if ai_settings.TAVILY_API_KEY:
            client = TavilyClient()
        else:
            client = DuckDuckGoClient()
        for query in all_followup_queries[:GAP_FOLLOWUP_QUERIES]:
            try:
                results = await client.search(query, max_results=GAP_FOLLOWUP_RESULTS)
                extra_sources.extend(results)
            except Exception as e:
                logger.error("[GapAnalyzer] Follow-up search failed: %s", e)

        # 소스 필터링: 관련성 + URL 중복 제거 (기존 소스 대비 + 내부 중복)
        if extra_sources:
            before = len(extra_sources)
            extra_sources = [s for s in extra_sources if _is_relevant_source(s)]
            deduped: list[SourceItem] = []
            for s in extra_sources:
                if s["url"] not in existing_urls:
                    existing_urls.add(s["url"])
                    deduped.append(s)
            duplicates = len(extra_sources) - len(deduped)
            extra_sources = deduped
            filtered = before - len(extra_sources)
            if filtered:
                logger.info(
                    "[GapAnalyzer] Filtered %d follow-up sources (%d irrelevant, %d duplicate)",
                    filtered, filtered - duplicates, duplicates,
                )
            logger.info("[GapAnalyzer] Found %d unique additional sources", len(extra_sources))

    result: dict = {"gap_report": gap_report}
    if extra_sources:
        result["web_sources"] = extra_sources  # append via operator.add

    return result
