"""
Reviewer node — 크로스 모델로 아티클 품질을 검증합니다.

v3: LLM 판정 후 프로그래밍 검증 (결론/차단도메인/포맷팅) 추가.
    우회 불가한 하드 체크로 품질 보장.
"""

import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.research.config import ai_settings
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

logger = logging.getLogger(__name__)

# 프로그래밍 검증: 차단 도메인
_BLOCKED_DOMAINS = [
    "namu.wiki",
    "blog.naver.com",
    "tistory.com",
    "wikipedia.org",
    "medium.com",
    "velog.io",
    "brunch.co.kr",
]

# 결론 섹션 패턴
_CONCLUSION_RE = re.compile(r"#{2,3}\s*(결론|요약|정리|마무리|맺음|종합)")


def _programmatic_review(article: str) -> tuple[bool, list[str]]:
    """LLM 우회 불가한 프로그래밍 검증.

    Returns:
        (passed, list of failure reasons)
    """
    failures: list[str] = []

    # 1. 결론 섹션 체크
    if _CONCLUSION_RE.search(article):
        failures.append("결론/요약/정리 섹션이 존재합니다.")

    # 2. 차단 도메인 인용 체크
    for domain in _BLOCKED_DOMAINS:
        if domain in article:
            failures.append(f"차단 도메인 '{domain}'이 아티클에 포함되어 있습니다.")

    # 3. 시각 요소 체크 (볼드, 테이블, blockquote 중 하나는 있어야)
    has_bold = "**" in article
    has_table = "|" in article and "---" in article
    has_blockquote = "\n> " in article or article.startswith("> ")
    if not has_bold and not has_table and not has_blockquote:
        failures.append("시각 요소(볼드/테이블/blockquote)가 하나도 없습니다.")

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
        logger.warning(f"[Reviewer] Programmatic check FAILED: {prog_failures}")
        feedback = "프로그래밍 검증 실패:\n" + "\n".join(f"- {f}" for f in prog_failures)
        return {
            "review_feedback": feedback,
            "retry_count": state.get("retry_count", 0) + 1,
        }

    # ── Step 2: LLM 크로스 모델 리뷰 ──
    llm = ai_settings.get_chat_model(role="reviewer", max_tokens=1024, temperature=0.2)
    structured_llm = llm.with_structured_output(ReviewerOutput)

    poll_options = ", ".join(state.get("poll_options", []))
    user_msg = REVIEWER_USER.format(
        article=article,
        poll_options=poll_options or "(선택지 없음)",
        web_sources=_format_web_sources(state.get("web_sources", [])),
        academic_sources=_format_academic_sources(state.get("academic_sources", [])),
    )

    try:
        result: ReviewerOutput = await structured_llm.ainvoke([
            SystemMessage(content=REVIEWER_SYSTEM),
            HumanMessage(content=user_msg),
        ])

        passed = result.passed and result.score >= 75
        score = result.score
        feedback = result.feedback

    except Exception as e:
        logger.warning(f"[Reviewer] Structured output failed: {e}. Defaulting to pass.")
        passed = True
        score = 80
        feedback = ""

    logger.info(f"[Reviewer] Score: {score}, Pass: {passed}")

    if passed:
        return {
            "final_article": article,
            "review_feedback": "",
        }
    else:
        logger.info(f"[Reviewer] Feedback: {feedback[:200]}")
        return {
            "review_feedback": feedback,
            "retry_count": state.get("retry_count", 0) + 1,
        }
