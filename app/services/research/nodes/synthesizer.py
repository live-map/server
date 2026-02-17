"""
Synthesizer node — 아웃라인 기반으로 데이터 중심 아티클을 생성합니다.

v3: snippet 확장 (400→800, 300→600)으로 anti-hallucination 강화.
    아웃라인 기반 섹션별 작성. Pre-numbered source list.
"""

import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.research.config import ai_settings
from app.services.research.prompts.synthesizer_prompt import (
    SYNTHESIZER_REVISE_USER,
    SYNTHESIZER_SYSTEM,
    SYNTHESIZER_USER,
)
from app.services.research.state import ResearchState, SourceItem
from app.services.research.utils import CONCLUSION_RE

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

    for s in web_sources[:15]:
        if s["url"] in seen_urls:
            continue
        seen_urls.add(s["url"])
        ordered.append(s)
        snippet = s["content_snippet"][:800] if s.get("content_snippet") else ""
        parts.append(
            f"[{idx}] **{s['title']}**\n"
            f"   URL: {s['url']}\n"
            f"   신뢰도: {s['credibility']}\n"
            f"   내용: {snippet}"
        )
        idx += 1

    for s in academic_sources[:10]:
        if s["url"] in seen_urls:
            continue
        seen_urls.add(s["url"])
        ordered.append(s)
        snippet = s["content_snippet"][:600] if s.get("content_snippet") else ""
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
    for i, r in enumerate(results[:10], 1):
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
    for i, s in enumerate(sources[:15], 1):
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
    for i, s in enumerate(sources[:10], 1):
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


def _ensure_visual_elements(article: str) -> str:
    """테이블/blockquote가 없으면 시각 요소를 보강합니다.

    - blockquote 0개 → "> " 인용 스타일로 첫 번째 기관/전문가 발언 변환
    - table 0개 → 수치 비교 2개+ 있는 문단을 간이 테이블로 변환 시도하지 않고
      로그 경고만 (LLM이 생성하도록 프롬프트에서 강제하는 것이 우선)
    """
    has_table = "|" in article and "---" in article
    has_blockquote = "\n> " in article or article.startswith("> ")

    if has_table and has_blockquote:
        return article

    if not has_blockquote:
        # 기관/전문가 발언 패턴을 blockquote로 변환
        # "~에 따르면 "~"이라고/라며/밝혔다" 또는 "~은(는) "~"라고" 패턴
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
        logger.warning(
            "[Synthesizer] No table found in article. "
            "Prompt should enforce table usage for data comparisons."
        )

    return article


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
    if source_count >= 10 and avg_credibility >= 2.5:
        level = "HIGH"
    elif source_count >= 5 and avg_credibility >= 1.5:
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
    logger.info(f"[Synthesizer] {mode} article for: {state['poll_title'][:50]}")

    llm = ai_settings.get_chat_model(role="synthesizer", max_tokens=4096, temperature=0.4)

    web_sources = state.get("web_sources", [])
    academic_sources = state.get("academic_sources", [])

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
            title=state["poll_title"],
            description=state.get("poll_description", "") or "설명 없음",
            options=", ".join(state.get("poll_options", [])),
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
        logger.error(f"[Synthesizer] LLM call failed: {e}")
        return {
            "draft_article": state.get("draft_article", ""),
            "error": f"Synthesizer LLM failed: {e}",
        }

    article = _strip_conclusion(response.content)
    article = _ensure_bold_numbers(article)
    article = _ensure_visual_elements(article)

    # 최종 출처 목록 추출 (중복 제거)
    extracted = _extract_sources_from_state(state)

    # 신뢰도 점수 계산
    confidence = _compute_confidence(web_sources, academic_sources)

    logger.info(f"[Synthesizer] Generated article ({len(article)} chars), {len(extracted)} sources")

    return {
        "draft_article": article,
        "extracted_sources": extracted,
        "confidence": confidence,
    }


def _extract_sources_from_state(state: ResearchState) -> list[SourceItem]:
    """상태에서 최종 출처 목록을 추출합니다 (중복 제거)."""
    all_sources: list[SourceItem] = []
    seen_urls: set[str] = set()

    for source in state.get("web_sources", []) + state.get("academic_sources", []):
        if source["url"] and source["url"] not in seen_urls:
            seen_urls.add(source["url"])
            all_sources.append(source)

    return all_sources
