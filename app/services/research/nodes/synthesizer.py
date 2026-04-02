"""
Synthesizer node — 아웃라인 기반으로 데이터 중심 아티클을 생성합니다.

v3: snippet 확장 (400→800, 300→600)으로 anti-hallucination 강화.
    아웃라인 기반 섹션별 작성. Pre-numbered source list.
"""

import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.research.config import (
    ACADEMIC_SNIPPET_MAX,
    ACADEMIC_SOURCE_LIMIT,
    CONFIDENCE_HIGH_MIN_CREDIBILITY,
    CONFIDENCE_HIGH_MIN_SOURCES,
    CONFIDENCE_MEDIUM_MIN_CREDIBILITY,
    CONFIDENCE_MEDIUM_MIN_SOURCES,
    FACT_CHECK_DISPLAY_LIMIT,
    SYNTHESIZER_MAX_TOKENS,
    SYNTHESIZER_REVISION_TEMPERATURE,
    SYNTHESIZER_TEMPERATURE,
    WEB_SNIPPET_MAX,
    WEB_SOURCE_LIMIT,
    ai_settings,
)
from app.services.research.prompts.synthesizer_prompt import (
    SYNTHESIZER_REVISE_USER,
    SYNTHESIZER_SYSTEM,
    SYNTHESIZER_USER,
)
from app.services.research.state import ResearchState, SourceItem
from app.services.research.utils import CONCLUSION_RE, filter_by_graded_urls, sanitize_user_input

logger = logging.getLogger(__name__)


def _build_numbered_source_list(
    web_sources: list[SourceItem],
    academic_sources: list[SourceItem],
) -> tuple[str, list[SourceItem]]:
    """웹+학술 출처를 통합 번호로 매핑합니다.

    Returns:
        (numbered_text, ordered_sources)
    """
    ordered: list[SourceItem] = []
    seen_urls: set[str] = set()
    parts: list[str] = []
    idx = 1

    for s in web_sources[:WEB_SOURCE_LIMIT]:
        if s["url"] in seen_urls:
            continue
        seen_urls.add(s["url"])
        ordered.append(s)
        snippet = s["content_snippet"][:WEB_SNIPPET_MAX] if s.get("content_snippet") else ""
        parts.append(
            f"[{idx}] **{s['title']}**\n"
            f"   URL: {s['url']}\n"
            f"   신뢰도: {s['credibility']}\n"
            f"   내용: {snippet}"
        )
        idx += 1

    for s in academic_sources[:ACADEMIC_SOURCE_LIMIT]:
        if s["url"] in seen_urls:
            continue
        seen_urls.add(s["url"])
        ordered.append(s)
        snippet = s["content_snippet"][:ACADEMIC_SNIPPET_MAX] if s.get("content_snippet") else ""
        parts.append(
            f"[{idx}] **{s['title']}** (학술)\n"
            f"   저자: {s['description']}\n"
            f"   URL: {s['url']}\n"
            f"   초록: {snippet}"
        )
        idx += 1

    text = "\n\n".join(parts) if parts else "(출처 없음)"
    return text, ordered


def _format_outline(outline: list[dict]) -> str:
    """아웃라인을 프롬프트용 텍스트로 포맷합니다."""
    if not outline:
        return "(아웃라인 없음)"
    parts = []
    for section in outline:
        title = section.get("title", "## 섹션")
        points = "\n".join(f"  - {p}" for p in section.get("key_points", []))
        sources = section.get("source_numbers", [])
        source_str = f"  - 인용 출처: [{', '.join(str(n) for n in sources)}]" if sources else ""
        parts.append(f"{title}\n{points}\n{source_str}")
    return "\n\n".join(parts)


def _format_fact_checks(results: list[dict]) -> str:
    if not results:
        return "(팩트체크 결과 없음)"
    parts = []
    for i, r in enumerate(results[:FACT_CHECK_DISPLAY_LIMIT], 1):
        parts.append(
            f"{i}. **주장**: {r.get('claim_text', '')}\n"
            f"   **평가**: {r.get('rating', '알 수 없음')}\n"
            f"   **출처**: {r.get('publisher', '')} — {r.get('url', '')}"
        )
    return "\n\n".join(parts)


# reviewer.py에서 사용하는 포맷 함수 (하위 호환)
def _format_web_sources(sources: list[SourceItem]) -> str:
    if not sources:
        return "(검색 결과 없음)"
    parts = []
    for i, s in enumerate(sources[:WEB_SOURCE_LIMIT], 1):
        parts.append(
            f"{i}. **{s['title']}**\n"
            f"   URL: {s['url']}\n"
            f"   신뢰도: {s['credibility']}\n"
            f"   내용: {s['content_snippet'][:600]}"
        )
    return "\n\n".join(parts)


def _format_academic_sources(sources: list[SourceItem]) -> str:
    if not sources:
        return "(학술 논문 없음)"
    parts = []
    for i, s in enumerate(sources[:ACADEMIC_SOURCE_LIMIT], 1):
        parts.append(
            f"{i}. **{s['title']}**\n"
            f"   저자: {s['description']}\n"
            f"   URL: {s['url']}\n"
            f"   초록: {s['content_snippet'][:600]}"
        )
    return "\n\n".join(parts)


def _strip_conclusion(article: str) -> str:
    """결론/요약/정리/마무리 섹션을 프로그래밍적으로 제거합니다."""
    match = CONCLUSION_RE.search(article)
    if not match:
        return article

    # 결론 섹션 시작 위치에서 다음 ## 섹션이나 출처 목록까지 제거
    start = match.start()

    # 결론 이후 다음 ## 섹션이나 출처 목록([1], [2]) 찾기
    rest = article[match.end():]
    next_section = re.search(r"\n##\s|^\[[\d]+\]", rest, re.MULTILINE)
    if next_section:
        end = match.end() + next_section.start()
        article = article[:start] + "\n" + article[end:]
    else:
        # 결론이 마지막 섹션이면 그냥 제거
        article = article[:start]

    logger.info("[Synthesizer] Stripped conclusion section from article")
    return article.strip()


# 수치/퍼센트 볼드 처리 패턴: 이미 볼드가 아닌 독립 숫자
_NUMBER_RE = re.compile(
    r"(?<!\*\*)"  # 앞에 ** 아님
    r"(\d[\d,.]*\s*(?:%|퍼센트|조|억|만|명|위|개|건|곳|TWh|GW|MW))"
    r"(?!\*\*)"   # 뒤에 ** 아님
)


def _ensure_bold_numbers(article: str) -> str:
    """아티클에 **볼드**가 없으면 수치를 자동 볼드 처리합니다."""
    if "**" in article:
        return article

    bolded = _NUMBER_RE.sub(r"**\1**", article)
    if bolded != article:
        logger.info("[Synthesizer] Auto-bolded numbers in article")
    return bolded


# 수치 비교 패턴: "A는 X%, B는 Y%" 또는 "A X명, B Y명" 같은 패턴
_COMPARISON_RE = re.compile(
    r"(\*\*[\d,.]+\s*(?:%|퍼센트|조|억|만|명|위|개|건|곳|TWh|GW|MW)\*\*)"
    r"[^*\n]{0,80}"
    r"(\*\*[\d,.]+\s*(?:%|퍼센트|조|억|만|명|위|개|건|곳|TWh|GW|MW)\*\*)"
)


def _has_visual_elements(article: str) -> tuple[bool, bool]:
    """테이블과 blockquote 존재 여부를 반환합니다."""
    has_table = "|" in article and "---" in article
    has_blockquote = "\n> " in article or article.startswith("> ")
    return has_table, has_blockquote


def _ensure_visual_elements(article: str) -> str:
    """테이블/blockquote가 없으면 시각 요소를 보강합니다.

    - blockquote 0개 → "> " 인용 스타일로 첫 번째 기관/전문가 발언 변환
    - table 0개 → 로그 경고 (synthesizer_node에서 재시도 트리거)
    """
    has_table, has_blockquote = _has_visual_elements(article)

    if has_table and has_blockquote:
        return article

    if not has_blockquote:
        quote_pattern = re.compile(
            r"((?:[가-힣A-Za-z]+(?:은|는|에 따르면|관계자는|위원장은|장관은|총재는))\s*"
            r'"[^"]{10,}"'
            r"(?:이?라고|라며|밝혔다|전했다|분석했다|강조했다|설명했다|지적했다)[^\n]*)"
        )
        match = quote_pattern.search(article)
        if match:
            original = match.group(0)
            quoted = f"\n> {original}\n"
            article = article.replace(original, quoted, 1)
            logger.info("[Synthesizer] Auto-converted expert quote to blockquote")

    if not has_table:
        logger.warning("[Synthesizer] No table found in article")

    return article


def _build_fallback_source_table(
    web_sources: list[SourceItem],
    academic_sources: list[SourceItem],
) -> str:
    """소스 요약 테이블을 생성합니다 (visual element fallback)."""
    rows = []
    for s in (web_sources + academic_sources)[:5]:
        cred = s.get("credibility", "?")
        stype = s.get("source_type", "?")
        title = s.get("title", "")[:40]
        rows.append(f"| {title} | {stype} | {cred} |")

    if not rows:
        return ""

    header = "\n| 출처 | 유형 | 신뢰도 |\n|------|------|--------|\n"
    return header + "\n".join(rows) + "\n"


def _compute_confidence(
    web_sources: list[SourceItem],
    academic_sources: list[SourceItem],
) -> dict:
    """출처 기반 신뢰도 메타데이터를 계산합니다."""
    all_sources = web_sources + academic_sources
    total = len(all_sources) or 1

    # 한국어 출처 비율
    korean_re = re.compile(r"[가-힣]")
    korean_count = sum(1 for s in all_sources if korean_re.search(s.get("title", "")))

    # 평균 신뢰도 (HIGH=3, MEDIUM=2, LOW=1)
    cred_map = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    cred_scores = [cred_map.get(s.get("credibility", "LOW"), 1) for s in all_sources]
    avg_credibility = round(sum(cred_scores) / total, 2) if cred_scores else 0

    # 신뢰도 레벨
    source_count = len(all_sources)
    if source_count >= CONFIDENCE_HIGH_MIN_SOURCES and avg_credibility >= CONFIDENCE_HIGH_MIN_CREDIBILITY:
        level = "HIGH"
    elif source_count >= CONFIDENCE_MEDIUM_MIN_SOURCES and avg_credibility >= CONFIDENCE_MEDIUM_MIN_CREDIBILITY:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "source_count": source_count,
        "korean_ratio": round(korean_count / total, 2),
        "credibility_avg": avg_credibility,
        "has_academic": len(academic_sources) > 0,
        "level": level,
    }


async def synthesizer_node(state: ResearchState) -> dict:
    """수집된 자료와 아웃라인을 바탕으로 아티클을 생성합니다."""
    is_revision = bool(state.get("review_feedback"))
    mode = "Revising" if is_revision else "Synthesizing"
    logger.info("[Synthesizer] %s article for: %s", mode, state["poll_title"][:50])

    temperature = SYNTHESIZER_REVISION_TEMPERATURE if is_revision else SYNTHESIZER_TEMPERATURE
    llm = ai_settings.get_chat_model(role="synthesizer", max_tokens=SYNTHESIZER_MAX_TOKENS, temperature=temperature)

    web_sources = filter_by_graded_urls(
        state.get("web_sources", []), state.get("graded_web_urls", [])
    )
    academic_sources = filter_by_graded_urls(
        state.get("academic_sources", []), state.get("graded_academic_urls", [])
    )

    # 통합 번호 매핑
    numbered_text, ordered_sources = _build_numbered_source_list(
        web_sources, academic_sources
    )

    if is_revision:
        user_msg = SYNTHESIZER_REVISE_USER.format(
            draft_article=state.get("draft_article", ""),
            review_feedback=state.get("review_feedback", ""),
            numbered_sources=numbered_text,
        )
    else:
        outline = state.get("outline", [])
        user_msg = SYNTHESIZER_USER.format(
            title=sanitize_user_input(state["poll_title"], max_length=200, tag="title"),
            description=sanitize_user_input(state.get("poll_description", "") or "설명 없음", max_length=500, tag="description"),
            options=sanitize_user_input(", ".join(state.get("poll_options", [])), max_length=500, tag="options"),
            outline=_format_outline(outline),
            numbered_sources=numbered_text,
            fact_check_results=_format_fact_checks(state.get("fact_check_results", [])),
        )

    try:
        response = await llm.ainvoke([
            SystemMessage(content=SYNTHESIZER_SYSTEM),
            HumanMessage(content=user_msg),
        ])
    except Exception as e:
        logger.error("[Synthesizer] LLM call failed: %s", e)
        return {
            "draft_article": state.get("draft_article", ""),
            "error": f"Synthesizer LLM failed: {e}",
        }

    article = _strip_conclusion(response.content)
    article = _ensure_bold_numbers(article)
    article = _ensure_visual_elements(article)

    # 테이블 없으면 1회 재시도 (revision이 아닌 경우만)
    has_table, _ = _has_visual_elements(article)
    if not has_table and not is_revision:
        logger.info("[Synthesizer] No table found, retrying with visual emphasis")
        try:
            retry_msg = (
                user_msg
                + "\n\n⚠️ 중요: 이전 결과에 테이블이 없었습니다. "
                "반드시 마크다운 테이블(| 헤더 | ... | + |---|---| 형식)을 1개 이상 포함하세요. "
                "수치 비교, 현황 요약, 또는 관점별 정리를 테이블로 표현하세요."
            )
            retry_response = await llm.ainvoke([
                SystemMessage(content=SYNTHESIZER_SYSTEM),
                HumanMessage(content=retry_msg),
            ])
            retry_article = _strip_conclusion(retry_response.content)
            retry_article = _ensure_bold_numbers(retry_article)
            retry_article = _ensure_visual_elements(retry_article)
            has_table_retry, _ = _has_visual_elements(retry_article)
            if has_table_retry:
                article = retry_article
                logger.info("[Synthesizer] Retry succeeded — table included")
            else:
                # 2회 시도 후에도 없으면 fallback 소스 테이블 삽입
                fallback_table = _build_fallback_source_table(web_sources, academic_sources)
                if fallback_table:
                    article = article.rstrip() + "\n\n### 주요 출처 요약\n" + fallback_table
                    logger.info("[Synthesizer] Inserted fallback source summary table")
        except Exception as e:
            logger.warning("[Synthesizer] Visual retry failed: %s", e)

    # 최종 출처 목록 추출 (중복 제거, 필터링 반영)
    extracted = _extract_sources(web_sources, academic_sources)

    # 신뢰도 점수 계산
    confidence = _compute_confidence(web_sources, academic_sources)

    logger.info("[Synthesizer] Generated article (%d chars), %d sources", len(article), len(extracted))

    return {
        "draft_article": article,
        "extracted_sources": extracted,
        "confidence": confidence,
    }


def _extract_sources(
    web_sources: list[SourceItem],
    academic_sources: list[SourceItem],
) -> list[SourceItem]:
    """출처 목록에서 중복을 제거하여 반환합니다."""
    all_sources: list[SourceItem] = []
    seen_urls: set[str] = set()

    for source in web_sources + academic_sources:
        if source["url"] and source["url"] not in seen_urls:
            seen_urls.add(source["url"])
            all_sources.append(source)

    return all_sources
