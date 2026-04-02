"""
Perspective Discovery node — 관점/이해관계자를 발견합니다.

Stanford STORM 패턴: 리서치 전에 어떤 관점이 존재하는지 먼저 발견하여
균형 잡힌 검색 쿼리와 아티클 구조를 보장합니다.
"""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.research.config import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE, FALLBACK_PERSPECTIVES_LIMIT, ai_settings
from app.services.research.prompts.perspective_prompt import (
    PERSPECTIVE_SYSTEM,
    PERSPECTIVE_USER,
)
from app.services.research.schemas import PerspectiveOutput
from app.services.research.state import ResearchState
from app.services.research.utils import sanitize_user_input

logger = logging.getLogger(__name__)


async def perspective_discovery_node(state: ResearchState) -> dict:
    """여론조사 주제의 관점과 이해관계자를 발견합니다."""
    logger.info("[PerspectiveDiscovery] Analyzing: %s", state["poll_title"][:50])

    llm = ai_settings.get_chat_model(role="planner", max_tokens=DEFAULT_MAX_TOKENS, temperature=DEFAULT_TEMPERATURE)
    structured_llm = llm.with_structured_output(PerspectiveOutput)

    user_msg = PERSPECTIVE_USER.format(
        title=sanitize_user_input(state["poll_title"], max_length=200, tag="title"),
        description=sanitize_user_input(state.get("poll_description", "") or "설명 없음", max_length=500, tag="description"),
        category=state.get("poll_category", "") or "일반",
        options=sanitize_user_input(", ".join(state.get("poll_options", [])), max_length=500, tag="options"),
    )

    try:
        result: PerspectiveOutput = await structured_llm.ainvoke([
            SystemMessage(content=PERSPECTIVE_SYSTEM),
            HumanMessage(content=user_msg),
        ])

        perspectives = [
            {
                "label": p.label,
                "description": p.description,
                "key_questions": p.key_questions,
            }
            for p in result.perspectives
        ]

        logger.info(
            "[PerspectiveDiscovery] Found %d perspectives: %s",
            len(perspectives),
            [p["label"] for p in perspectives],
        )
        return {"perspectives": perspectives}

    except Exception as e:
        logger.error("[PerspectiveDiscovery] Failed: %s", e, exc_info=True)
        # fallback: 선택지를 관점으로 사용
        options = state.get("poll_options", [])
        fallback = [
            {
                "label": opt,
                "description": f"'{opt}' 선택지에 해당하는 관점",
                "key_questions": [f"{opt}에 대한 근거는?"],
            }
            for opt in options[:FALLBACK_PERSPECTIVES_LIMIT]
        ]
        return {"perspectives": fallback}
