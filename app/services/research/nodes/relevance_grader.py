"""
Relevance Grader node — CRAG 패턴 문서 관련성 평가.

fan-in 직후, gap_analyzer 전에 실행됩니다.
각 문서를 0-1 점수로 평가하여:
- CORRECT (≥0.7): graded_*_urls에 추가
- AMBIGUOUS (0.3-0.7): graded_*_urls에 추가 + requery 수집
- INCORRECT (<0.3): 제외 (URL이 허용 목록에 포함되지 않음)

실패 시 Fail-Open: graded_*_urls를 채우지 않으면 downstream이
모든 소스를 사용함 (기존 동작 유지).
"""

import asyncio
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.research.config import (
    DEFAULT_MAX_TOKENS,
    GRADER_AMBIGUOUS_THRESHOLD,
    GRADER_BATCH_SIZE,
    GRADER_CORRECT_THRESHOLD,
    GRADER_MAX_REQUERY,
    GRADER_MIN_CORRECT_SOURCES,
    GRADER_SNIPPET_MAX,
    ai_settings,
)
from app.services.research.prompts.relevance_grader_prompt import (
    GRADER_SYSTEM,
    GRADER_USER,
)
from app.services.research.schemas import RelevanceGraderOutput
from app.services.research.state import ResearchState, SourceItem
from app.services.research.utils import sanitize_user_input

logger = logging.getLogger(__name__)


def _format_documents(sources: list[SourceItem]) -> str:
    """소스 목록을 프롬프트용 텍스트로 포맷합니다."""
    if not sources:
        return "(없음)"
    parts = []
    for s in sources:
        snippet = s.get("content_snippet", "")[:GRADER_SNIPPET_MAX]
        parts.append(
            f"---\n"
            f"URL: {s['url']}\n"
            f"Title: {s['title']}\n"
            f"Credibility: {s.get('credibility', 'UNKNOWN')}\n"
            f"Snippet: {snippet}\n"
            f"---"
        )
    return "\n".join(parts)


async def _grade_batch(
    sources: list[SourceItem],
    poll_title: str,
    poll_description: str,
) -> RelevanceGraderOutput | None:
    """소스 배치를 LLM으로 관련성 평가합니다."""
    if not sources:
        return None

    llm = ai_settings.get_chat_model(
        role="grader",
        max_tokens=DEFAULT_MAX_TOKENS,
        temperature=0.1,
    )
    structured_llm = llm.with_structured_output(RelevanceGraderOutput)

    user_msg = GRADER_USER.format(
        poll_title=sanitize_user_input(poll_title, max_length=200, tag="title"),
        poll_description=sanitize_user_input(
            poll_description or "설명 없음", max_length=500, tag="description"
        ),
        doc_count=len(sources),
        documents_text=_format_documents(sources),
    )

    return await structured_llm.ainvoke([
        SystemMessage(content=GRADER_SYSTEM),
        HumanMessage(content=user_msg),
    ])


async def _grade_sources(
    sources: list[SourceItem],
    poll_title: str,
    poll_description: str,
) -> RelevanceGraderOutput | None:
    """소스를 배치 단위로 나누어 평가합니다."""
    if not sources:
        return None

    if len(sources) <= GRADER_BATCH_SIZE:
        return await _grade_batch(sources, poll_title, poll_description)

    # 대량 소스: 배치 분할 + 병렬 실행
    batches = [
        sources[i : i + GRADER_BATCH_SIZE]
        for i in range(0, len(sources), GRADER_BATCH_SIZE)
    ]
    results = await asyncio.gather(
        *[_grade_batch(batch, poll_title, poll_description) for batch in batches],
        return_exceptions=True,
    )

    all_grades = []
    for r in results:
        if isinstance(r, Exception):
            logger.warning("[RelevanceGrader] Batch failed: %s", r)
            continue
        if r is not None:
            all_grades.extend(r.grades)

    if not all_grades:
        return None
    return RelevanceGraderOutput(grades=all_grades)


async def relevance_grader_node(state: ResearchState) -> dict:
    """검색된 문서의 관련성을 평가하고 CORRECT/AMBIGUOUS/INCORRECT로 분류합니다."""
    web_sources = state.get("web_sources", [])
    academic_sources = state.get("academic_sources", [])

    total = len(web_sources) + len(academic_sources)
    if total == 0:
        logger.info("[RelevanceGrader] No sources to grade, skipping")
        return {}

    poll_title = state.get("poll_title", "")
    poll_description = state.get("poll_description", "")

    logger.info(
        "[RelevanceGrader] Grading %d web + %d academic sources",
        len(web_sources),
        len(academic_sources),
    )

    try:
        # 웹/학술 소스를 병렬로 평가
        web_result, academic_result = await asyncio.gather(
            _grade_sources(web_sources, poll_title, poll_description),
            _grade_sources(academic_sources, poll_title, poll_description),
            return_exceptions=True,
        )

        # 예외 처리
        if isinstance(web_result, Exception):
            logger.error("[RelevanceGrader] Web grading failed: %s", web_result)
            web_result = None
        if isinstance(academic_result, Exception):
            logger.error("[RelevanceGrader] Academic grading failed: %s", academic_result)
            academic_result = None

        # 결과 분류
        graded_web_urls: list[str] = []
        graded_academic_urls: list[str] = []
        ambiguous_requery: list[str] = []
        correct_count = 0

        web_url_set = {s["url"] for s in web_sources}

        for result in [web_result, academic_result]:
            if result is None:
                continue
            for grade in result.grades:
                is_web = grade.url in web_url_set
                score = grade.relevance_score

                if score >= GRADER_CORRECT_THRESHOLD:
                    # CORRECT
                    if is_web:
                        graded_web_urls.append(grade.url)
                    else:
                        graded_academic_urls.append(grade.url)
                    correct_count += 1
                elif score >= GRADER_AMBIGUOUS_THRESHOLD:
                    # AMBIGUOUS: 허용목록에 포함하되 requery 수집
                    if is_web:
                        graded_web_urls.append(grade.url)
                    else:
                        graded_academic_urls.append(grade.url)
                    if grade.requery:
                        ambiguous_requery.append(grade.requery)
                # INCORRECT (<0.3): 허용목록에서 제외

                logger.debug(
                    "[RelevanceGrader] %s → %s (%.2f): %s",
                    grade.url[:60],
                    grade.verdict,
                    score,
                    grade.reason[:80],
                )

        # Fail-open: CORRECT가 너무 적으면 전체 통과
        if correct_count < GRADER_MIN_CORRECT_SOURCES:
            logger.warning(
                "[RelevanceGrader] Only %d CORRECT sources (min: %d). "
                "Fail-open: passing all sources through.",
                correct_count,
                GRADER_MIN_CORRECT_SOURCES,
            )
            return {}

        # requery 수 제한
        ambiguous_requery = ambiguous_requery[:GRADER_MAX_REQUERY]

        discarded_web = len(web_sources) - len(graded_web_urls)
        discarded_academic = len(academic_sources) - len(graded_academic_urls)
        logger.info(
            "[RelevanceGrader] Result: %d/%d web passed, %d/%d academic passed, "
            "%d ambiguous requeries",
            len(graded_web_urls),
            len(web_sources),
            len(graded_academic_urls),
            len(academic_sources),
            len(ambiguous_requery),
        )
        if discarded_web + discarded_academic > 0:
            logger.info(
                "[RelevanceGrader] Discarded %d irrelevant sources (web: %d, academic: %d)",
                discarded_web + discarded_academic,
                discarded_web,
                discarded_academic,
            )

        return {
            "graded_web_urls": graded_web_urls,
            "graded_academic_urls": graded_academic_urls,
            "ambiguous_requery": ambiguous_requery,
        }

    except Exception as e:
        logger.error("[RelevanceGrader] Unexpected error, fail-open: %s", e)
        return {}
