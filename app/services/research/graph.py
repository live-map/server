"""
LangGraph StateGraph assembly for the Research Agent.

v2: 9-node 그래프.
START → perspective_discovery → planner → [web|academic|fact_check] 병렬
→ gap_analyzer → outline_generator → synthesizer → reviewer → 조건부 재시도.
"""

import logging

from langgraph.graph import END, START, StateGraph

from app.services.research.nodes.academic_search import academic_search_node
from app.services.research.nodes.fact_check import fact_check_node
from app.services.research.nodes.gap_analyzer import gap_analyzer_node
from app.services.research.nodes.outline_generator import outline_generator_node
from app.services.research.nodes.perspective_discovery import perspective_discovery_node
from app.services.research.nodes.planner import planner_node
from app.services.research.nodes.reviewer import reviewer_node
from app.services.research.nodes.synthesizer import synthesizer_node
from app.services.research.nodes.web_search import web_search_node
from app.services.research.state import ResearchState

logger = logging.getLogger(__name__)


def _review_decision(state: ResearchState) -> str:
    """리뷰 결과에 따라 다음 노드를 결정합니다."""
    if state.get("final_article"):
        return "end"
    if state.get("retry_count", 0) >= 2:
        logger.warning("[Decision] Max retries reached, using current draft")
        return "end"
    return "revise"


def build_research_graph() -> StateGraph:
    """리서치 에이전트 9-node 그래프를 조립하고 컴파일합니다."""
    builder = StateGraph(ResearchState)

    # 노드 추가
    builder.add_node("perspective_discovery", perspective_discovery_node)
    builder.add_node("planner", planner_node)
    builder.add_node("web_search", web_search_node)
    builder.add_node("academic_search", academic_search_node)
    builder.add_node("fact_check", fact_check_node)
    builder.add_node("gap_analyzer", gap_analyzer_node)
    builder.add_node("outline_generator", outline_generator_node)
    builder.add_node("synthesizer", synthesizer_node)
    builder.add_node("reviewer", reviewer_node)

    # START → perspective_discovery → planner
    builder.add_edge(START, "perspective_discovery")
    builder.add_edge("perspective_discovery", "planner")

    # planner → 3개 검색 병렬 (fan-out)
    builder.add_edge("planner", "web_search")
    builder.add_edge("planner", "academic_search")
    builder.add_edge("planner", "fact_check")

    # 3개 검색 → gap_analyzer (fan-in)
    builder.add_edge("web_search", "gap_analyzer")
    builder.add_edge("academic_search", "gap_analyzer")
    builder.add_edge("fact_check", "gap_analyzer")

    # gap_analyzer → outline_generator → synthesizer → reviewer
    builder.add_edge("gap_analyzer", "outline_generator")
    builder.add_edge("outline_generator", "synthesizer")
    builder.add_edge("synthesizer", "reviewer")

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
    logger.info("[Graph] Research graph compiled (9 nodes, v2)")
    return graph
