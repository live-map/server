"""
Perspective Discovery node — 관점/이해관계자를 발견합니다.

Stanford STORM 패턴: 리서치 전에 어떤 관점이 존재하는지 먼저 발견하여
균형 잡힌 검색 쿼리와 아티클 구조를 보장합니다.
"""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.research.config import ai_settings
from app.services.research.prompts.perspective_prompt import (
    PERSPECTIVE_SYSTEM,
    PERSPECTIVE_USER,
)
from app.services.research.schemas import PerspectiveOutput
from app.services.research.state import ResearchState

logger = logging.getLogger(__name__)


async def perspective_discovery_node(state: ResearchState) -> dict:
    """여론조사 주제의 관점과 이해관계자를 발견합니다."""
    logger.info(f"[PerspectiveDiscovery] Analyzing: {state['poll_title'][:50]}")

    llm = ai_settings.get_chat_model(role="planner", max_tokens=1024, temperature=0.3)
    structured_llm = llm.with_structured_output(PerspectiveOutput)

    user_msg = PERSPECTIVE_USER.format(
        title=state["poll_title"],
        description=state.get("poll_description", "") or "설명 없음",
        category=state.get("poll_category", "") or "일반",
        options=", ".join(state.get("poll_options", [])),
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
            f"[PerspectiveDiscovery] Found {len(perspectives)} perspectives: "
            f"{[p['label'] for p in perspectives]}"
        )
        return {"perspectives": perspectives}

    except Exception as e:
        logger.error(f"[PerspectiveDiscovery] Failed: {e}", exc_info=True)
        # fallback: 선택지를 관점으로 사용
        options = state.get("poll_options", [])
        fallback = [
            {
                "label": opt,
                "description": f"'{opt}' 선택지에 해당하는 관점",
                "key_questions": [f"{opt}에 대한 근거는?"],
            }
            for opt in options[:4]
        ]
        return {"perspectives": fallback}
