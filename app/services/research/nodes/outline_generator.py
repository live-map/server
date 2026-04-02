"""
Outline Generator node — STORM식 아웃라인을 생성합니다.

v3: 관점 1:1 매핑 검증 + 결론 섹션 자동 제거.
"""

import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.research.config import (
    OUTLINE_MAPPING_THRESHOLD,
    OUTLINE_MAX_TOKENS,
    OUTLINE_TEMPERATURE,
    ai_settings,
)
from app.services.research.prompts.outline_prompt import (
    OUTLINE_SYSTEM,
    OUTLINE_USER,
)
from app.services.research.schemas import OutlineOutput
from app.services.research.state import ResearchState
from app.services.research.utils import build_numbered_sources_brief, sanitize_user_input

logger = logging.getLogger(__name__)

# 결론류 섹션 키워드
_CONCLUSION_KEYWORDS = re.compile(r"결론|요약|정리|마무리|맺음|종합")


def _format_perspectives(perspectives: list[dict]) -> str:
    parts = []
    for p in perspectives:
        questions = "\n".join(f"  - {q}" for q in p.get("key_questions", []))
        parts.append(f"### {p['label']}\n{p['description']}\n{questions}")
    return "\n\n".join(parts)


def _remove_conclusion_sections(sections: list[dict]) -> list[dict]:
    """결론/요약/정리/마무리 섹션을 자동 제거합니다."""
    filtered = []
    for s in sections:
        title = s.get("title", "")
        if _CONCLUSION_KEYWORDS.search(title):
            logger.info("[OutlineGenerator] Removed conclusion section: %s", title)
            continue
        filtered.append(s)
    # 최소 2개 섹션은 유지
    return filtered if len(filtered) >= 2 else sections


def _check_perspective_mapping(
    sections: list[dict], poll_options: list[str]
) -> bool:
    """섹션 제목의 >50%가 poll option과 1:1 매핑되면 True (=문제 있음)."""
    if not poll_options or not sections:
        return False

    option_labels = [opt.lower().strip() for opt in poll_options]
    match_count = 0

    for s in sections:
        title = s.get("title", "").lower().replace("##", "").strip()
        for opt in option_labels:
            # 섹션 제목이 option 텍스트를 포함하거나 매우 유사하면 매칭
            if opt in title or title in opt:
                match_count += 1
                break

    ratio = match_count / len(sections) if sections else 0
    if ratio > OUTLINE_MAPPING_THRESHOLD:
        logger.warning(
            "[OutlineGenerator] %.0f%% sections match poll options 1:1 (%d/%d)",
            ratio * 100, match_count, len(sections),
        )
        return True
    return False


async def outline_generator_node(state: ResearchState) -> dict:
    """수집된 자료를 바탕으로 아티클 아웃라인을 생성합니다."""
    logger.info("[OutlineGenerator] Generating outline for: %s", state["poll_title"][:50])

    llm = ai_settings.get_chat_model(role="synthesizer", max_tokens=OUTLINE_MAX_TOKENS, temperature=OUTLINE_TEMPERATURE)
    structured_llm = llm.with_structured_output(OutlineOutput)

    perspectives = state.get("perspectives", [])
    gap_report = state.get("gap_report", {})
    poll_options = state.get("poll_options", [])

    user_msg = OUTLINE_USER.format(
        title=sanitize_user_input(state["poll_title"], max_length=200, tag="title"),
        description=sanitize_user_input(state.get("poll_description", "") or "설명 없음", max_length=500, tag="description"),
        options=sanitize_user_input(", ".join(poll_options), max_length=500, tag="options"),
        perspectives=_format_perspectives(perspectives),
        gap_summary=gap_report.get("summary", "갭 분석 없음"),
        numbered_sources=build_numbered_sources_brief(
            state.get("web_sources", []),
            state.get("academic_sources", []),
        ),
    )

    try:
        result: OutlineOutput = await structured_llm.ainvoke([
            SystemMessage(content=OUTLINE_SYSTEM),
            HumanMessage(content=user_msg),
        ])

        outline = [
            {
                "title": s.title,
                "key_points": s.key_points,
                "source_numbers": s.source_numbers,
            }
            for s in result.sections
        ]

        # 결론 섹션 자동 제거
        outline = _remove_conclusion_sections(outline)

        # 관점 1:1 매핑 검증 — 문제 시 1회 재생성
        if _check_perspective_mapping(outline, poll_options):
            logger.info("[OutlineGenerator] Perspective 1:1 mapping detected, regenerating...")
            try:
                retry_msg = (
                    user_msg
                    + "\n\n⚠️ 이전 시도에서 섹션 제목이 선택지와 1:1 대응했습니다. "
                    "반드시 다른 구조를 사용하세요. 섹션 제목에 선택지 텍스트를 직접 쓰지 마세요."
                )
                result2: OutlineOutput = await structured_llm.ainvoke([
                    SystemMessage(content=OUTLINE_SYSTEM),
                    HumanMessage(content=retry_msg),
                ])
                outline = [
                    {
                        "title": s.title,
                        "key_points": s.key_points,
                        "source_numbers": s.source_numbers,
                    }
                    for s in result2.sections
                ]
                outline = _remove_conclusion_sections(outline)
            except Exception as e:
                logger.warning("[OutlineGenerator] Retry failed, using first result: %s", e)
                # 첫 번째 결과를 그대로 사용

        logger.info(
            "[OutlineGenerator] Created outline with %d sections: %s",
            len(outline), [s["title"][:30] for s in outline],
        )
        logger.info("[OutlineGenerator] Rationale: %s", result.structure_rationale[:100])

        return {"outline": outline}

    except Exception as e:
        logger.error("[OutlineGenerator] Failed: %s", e, exc_info=True)
        # fallback: 기본 3-section outline
        return {
            "outline": [
                {
                    "title": "## 현황과 배경",
                    "key_points": ["주제 배경", "주요 데이터"],
                    "source_numbers": [],
                },
                {
                    "title": "## 핵심 쟁점 분석",
                    "key_points": ["각 관점의 핵심 논거"],
                    "source_numbers": [],
                },
                {
                    "title": "## 사례와 전망",
                    "key_points": ["해외 사례", "향후 전망"],
                    "source_numbers": [],
                },
            ]
        }
