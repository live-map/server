"""
Reviewer node — 크로스 모델로 아티클 품질을 검증합니다.

v4: 프로그래밍 검증을 primary gate로 전환.
    LLM 스코어는 메타데이터로만 사용 (< 60일 때만 retry 트리거).
"""

import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.research.config import (
    DEFAULT_MAX_TOKENS,
    REVIEWER_BLOCKED_DOMAINS,
    REVIEWER_DEFAULT_SCORE,
    REVIEWER_MIN_VISUAL_ELEMENTS,
    REVIEWER_PASS_SCORE,
    REVIEWER_TEMPERATURE,
    ai_settings,
)
from app.services.research.nodes.synthesizer import (
    _format_academic_sources,
    _format_web_sources,
)
from app.services.research.prompts.reviewer_prompt import (
    REVIEWER_SYSTEM,
    REVIEWER_USER,
)
from app.services.research.schemas import ReviewerOutput
from app.services.research.state import ResearchState
from app.services.research.utils import CONCLUSION_KEYWORDS_RE, filter_by_graded_urls

logger = logging.getLogger(__name__)


def _programmatic_review(article: str) -> tuple[bool, list[str]]:
    """LLM 우회 불가한 프로그래밍 검증.

    Returns:
        (passed, list of failure reasons)
    """
    failures: list[str] = []

    # 1. 결론 섹션 체크
    if CONCLUSION_KEYWORDS_RE.search(article):
        failures.append("결론/요약/정리 섹션이 존재합니다.")

    # 2. 차단 도메인 인용 체크
    for domain in REVIEWER_BLOCKED_DOMAINS:
        if domain in article:
            failures.append(f"차단 도메인 '{domain}'이 아티클에 포함되어 있습니다.")

    # 3. 시각 요소 체크 (볼드 + 테이블 또는 blockquote = 2개+ 필수)
    has_bold = "**" in article
    has_table = "|" in article and "---" in article
    has_blockquote = "\n> " in article or article.startswith("> ")
    visual_count = sum([has_bold, has_table, has_blockquote])
    if visual_count < REVIEWER_MIN_VISUAL_ELEMENTS:
        failures.append(
            f"시각 요소 2개+ 필수 (현재: bold={has_bold}, table={has_table}, "
            f"blockquote={has_blockquote}). 테이블 또는 blockquote를 추가하세요."
        )

    # 4. [^출처명|URL] 레거시 형식 체크
    if re.search(r"\[\^[^\]]+\|[^\]]+\]", article):
        failures.append("[^출처명|URL] 레거시 인용 형식이 사용되었습니다.")

    passed = len(failures) == 0
    return passed, failures


async def reviewer_node(state: ResearchState) -> dict:
    """아티클 품질을 검증하고 pass/fail 판정을 내립니다."""
    logger.info("[Reviewer] Reviewing article...")

    article = state.get("draft_article", "")

    # ── Step 1: 프로그래밍 검증 (LLM 우회 불가) ──
    prog_passed, prog_failures = _programmatic_review(article)
    if not prog_passed:
        logger.warning("[Reviewer] Programmatic check FAILED: %s", prog_failures)
        feedback = "프로그래밍 검증 실패:\n" + "\n".join(f"- {f}" for f in prog_failures)
        return {
            "review_feedback": feedback,
            "retry_count": state.get("retry_count", 0) + 1,
            "review_score": 0,
        }

    # ── Step 2: LLM 크로스 모델 리뷰 ──
    llm = ai_settings.get_chat_model(role="reviewer", max_tokens=DEFAULT_MAX_TOKENS, temperature=REVIEWER_TEMPERATURE)
    structured_llm = llm.with_structured_output(ReviewerOutput)

    poll_options = ", ".join(state.get("poll_options", []))
    user_msg = REVIEWER_USER.format(
        article=article,
        poll_options=poll_options or "(선택지 없음)",
        web_sources=_format_web_sources(
            filter_by_graded_urls(state.get("web_sources", []), state.get("graded_web_urls", []))
        ),
        academic_sources=_format_academic_sources(
            filter_by_graded_urls(state.get("academic_sources", []), state.get("graded_academic_urls", []))
        ),
    )

    try:
        result: ReviewerOutput = await structured_llm.ainvoke([
            SystemMessage(content=REVIEWER_SYSTEM),
            HumanMessage(content=user_msg),
        ])

        score = result.score
        feedback = result.feedback

    except Exception as e:
        logger.warning("[Reviewer] Structured output failed: %s. Defaulting to pass.", e)
        score = REVIEWER_DEFAULT_SCORE
        feedback = ""

    # v4: 프로그래밍 검증 통과 = primary gate 통과.
    # LLM 스코어 < 60일 때만 retry 트리거 (극히 낮은 품질만 걸러냄)
    passed = score >= REVIEWER_PASS_SCORE
    logger.info("[Reviewer] LLM Score: %d, Pass: %s", score, passed)

    if passed:
        return {
            "final_article": article,
            "review_feedback": "",
            "review_score": score,
        }
    else:
        logger.info("[Reviewer] Score < 60, triggering retry. Feedback: %s", feedback[:200])
        return {
            "review_feedback": feedback,
            "retry_count": state.get("retry_count", 0) + 1,
            "review_score": score,
        }
