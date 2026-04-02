"""
LangGraph StateGraph assembly for the Research Agent.

v5: 11-node 그래프 + CRAG relevance grading.
START → perspective_discovery → planner → [web|academic|fact_check] 병렬
→ relevance_grader → gap_analyzer → outline_generator → synthesizer
→ citation_validator → reviewer → 조건부 재시도.
"""

import asyncio
import functools
import logging
from collections.abc import Callable

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.services.research.config import MAX_RETRY_COUNT, NODE_TIMEOUTS
from app.services.research.nodes.academic_search import academic_search_node
from app.services.research.nodes.citation_validator import citation_validator_node
from app.services.research.nodes.fact_check import fact_check_node
from app.services.research.nodes.gap_analyzer import gap_analyzer_node
from app.services.research.nodes.relevance_grader import relevance_grader_node
from app.services.research.nodes.outline_generator import outline_generator_node
from app.services.research.nodes.perspective_discovery import perspective_discovery_node
from app.services.research.nodes.planner import planner_node
from app.services.research.nodes.reviewer import reviewer_node
from app.services.research.nodes.synthesizer import synthesizer_node
from app.services.research.nodes.web_search import web_search_node
from app.services.research.state import ResearchState

logger = logging.getLogger(__name__)


def _with_timeout(node_name: str, fn: Callable) -> Callable:
    """노드 함수에 개별 타임아웃을 적용합니다. 타임아웃 시 빈 dict 반환 (graceful degradation)."""
    timeout = NODE_TIMEOUTS.get(node_name)
    if timeout is None:
        return fn

    @functools.wraps(fn)
    async def wrapper(state: ResearchState) -> dict:
        try:
            return await asyncio.wait_for(fn(state), timeout=timeout)
        except asyncio.TimeoutError:
            logger.error("[Timeout] Node '%s' timed out after %ds", node_name, timeout)
            return {"error": f"Node '{node_name}' timed out after {timeout}s"}

    return wrapper


def _review_decision(state: ResearchState) -> str:
    """리뷰 결과에 따라 다음 노드를 결정합니다."""
    if state.get("final_article"):
        return "end"
    if state.get("retry_count", 0) >= MAX_RETRY_COUNT:
        logger.warning("[Decision] Max retries reached, using current draft")
        return "end"
    return "revise"


def build_research_graph() -> CompiledStateGraph:
    """리서치 에이전트 11-node 그래프를 조립하고 컴파일합니다."""
    builder = StateGraph(ResearchState)

    # 노드 추가 (개별 타임아웃 적용)
    nodes = {
        "perspective_discovery": perspective_discovery_node,
        "planner": planner_node,
        "web_search": web_search_node,
        "academic_search": academic_search_node,
        "fact_check": fact_check_node,
        "relevance_grader": relevance_grader_node,
        "gap_analyzer": gap_analyzer_node,
        "outline_generator": outline_generator_node,
        "synthesizer": synthesizer_node,
        "citation_validator": citation_validator_node,
        "reviewer": reviewer_node,
    }
    for name, fn in nodes.items():
        builder.add_node(name, _with_timeout(name, fn))

    # START → perspective_discovery → planner
    builder.add_edge(START, "perspective_discovery")
    builder.add_edge("perspective_discovery", "planner")

    # planner → 3개 검색 병렬 (fan-out)
    builder.add_edge("planner", "web_search")
    builder.add_edge("planner", "academic_search")
    builder.add_edge("planner", "fact_check")

    # 3개 검색 → relevance_grader (fan-in) → gap_analyzer
    builder.add_edge("web_search", "relevance_grader")
    builder.add_edge("academic_search", "relevance_grader")
    builder.add_edge("fact_check", "relevance_grader")
    builder.add_edge("relevance_grader", "gap_analyzer")

    # gap_analyzer → outline_generator → synthesizer → citation_validator → reviewer
    builder.add_edge("gap_analyzer", "outline_generator")
    builder.add_edge("outline_generator", "synthesizer")
    builder.add_edge("synthesizer", "citation_validator")
    builder.add_edge("citation_validator", "reviewer")

    # reviewer → conditional: pass→END, fail→synthesizer (최대 2회 재시도)
    builder.add_conditional_edges(
        "reviewer",
        _review_decision,
        {
            "end": END,
            "revise": "synthesizer",
        },
    )

    graph = builder.compile()
    logger.info("[Graph] Research graph compiled (11 nodes, v5)")
    return graph
