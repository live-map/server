"""
Planner node — 관점별 맞춤 검색 쿼리를 생성합니다.

v2: 관점 발견 결과를 바탕으로 타겟 쿼리 생성 + structured output.
"""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.research.config import ai_settings
from app.services.research.prompts.planner_prompt import (
    PLANNER_SYSTEM,
    PLANNER_USER,
)
from app.services.research.schemas import PlannerOutput
from app.services.research.state import ResearchState
from app.services.research.utils import format_perspectives_inline, sanitize_user_input

logger = logging.getLogger(__name__)


async def planner_node(state: ResearchState) -> dict:
    """여론조사 주제를 분석하고 관점별 맞춤 검색 쿼리를 생성합니다."""
    logger.info("[Planner] Starting for poll: %s", state["poll_title"][:50])

    llm = ai_settings.get_chat_model(role="planner", max_tokens=1024, temperature=0.3)
    structured_llm = llm.with_structured_output(PlannerOutput)

    perspectives = state.get("perspectives", [])
    user_msg = PLANNER_USER.format(
        title=sanitize_user_input(state["poll_title"], max_length=200, tag="title"),
        description=sanitize_user_input(state.get("poll_description", "") or "설명 없음", max_length=500, tag="description"),
        category=state.get("poll_category", "") or "일반",
        options=sanitize_user_input(", ".join(state.get("poll_options", [])), max_length=500, tag="options"),
        perspectives=format_perspectives_inline(perspectives) if perspectives else "(관점 발견 결과 없음)",
    )

    try:
        result: PlannerOutput = await structured_llm.ainvoke([
            SystemMessage(content=PLANNER_SYSTEM),
            HumanMessage(content=user_msg),
        ])

        output = {
            "search_queries": result.search_queries[:8],
            "academic_queries": result.academic_queries[:4],
            "fact_check_claims": result.fact_check_claims[:4],
        }

    except Exception as e:
        logger.warning("[Planner] Structured output failed, using fallback: %s", e)
        # fallback: 관점 기반 기본 쿼리 생성
        queries = []
        for p in perspectives:
            queries.append(f"{state['poll_title']} {p['label']}")
            if p.get("key_questions"):
                queries.append(p["key_questions"][0])
        if not queries:
            queries = [state["poll_title"]]

        output = {
            "search_queries": queries[:8],
            "academic_queries": [state["poll_title"]][:3],
            "fact_check_claims": [],
        }

    logger.info(
        "[Planner] Generated %d web queries, %d academic queries, %d fact check claims",
        len(output["search_queries"]),
        len(output["academic_queries"]),
        len(output["fact_check_claims"]),
    )
    return output
