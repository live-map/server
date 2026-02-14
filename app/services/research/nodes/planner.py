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

logger = logging.getLogger(__name__)


def _format_perspectives(perspectives: list[dict]) -> str:
    """관점 목록을 프롬프트용 텍스트로 변환합니다."""
    parts = []
    for p in perspectives:
        questions = ", ".join(p.get("key_questions", []))
        parts.append(f"- **{p['label']}**: {p['description']} (핵심 질문: {questions})")
    return "\n".join(parts)


async def planner_node(state: ResearchState) -> dict:
    """여론조사 주제를 분석하고 관점별 맞춤 검색 쿼리를 생성합니다."""
    logger.info(f"[Planner] Starting for poll: {state['poll_title'][:50]}")

    llm = ai_settings.get_chat_model(role="planner", max_tokens=1024, temperature=0.3)
    structured_llm = llm.with_structured_output(PlannerOutput)

    perspectives = state.get("perspectives", [])
    user_msg = PLANNER_USER.format(
        title=state["poll_title"],
        description=state.get("poll_description", "") or "설명 없음",
        category=state.get("poll_category", "") or "일반",
        options=", ".join(state.get("poll_options", [])),
        perspectives=_format_perspectives(perspectives) if perspectives else "(관점 발견 결과 없음)",
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
        logger.warning(f"[Planner] Structured output failed, using fallback: {e}")
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
        f"[Planner] Generated {len(output['search_queries'])} web queries, "
        f"{len(output['academic_queries'])} academic queries, "
        f"{len(output['fact_check_claims'])} fact check claims"
    )
    return output
