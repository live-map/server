"""
Citation Validator node — 아티클의 [N] 인용이 실제 소스와 일치하는지 검증합니다.

검증 항목:
1. [N] 번호가 소스 리스트 범위 내인지
2. [N] 주변 문장이 source[N].content_snippet의 키워드와 매칭되는지
"""

import logging
import re

from app.services.research.config import WEB_SOURCE_LIMIT, ACADEMIC_SOURCE_LIMIT
from app.services.research.state import ResearchState, SourceItem
from app.services.research.utils import filter_by_graded_urls

logger = logging.getLogger(__name__)

_CITATION_RE = re.compile(r"\[(\d+)\]")


def _build_source_list(
    web_sources: list[SourceItem],
    academic_sources: list[SourceItem],
) -> list[SourceItem]:
    """synthesizer와 동일한 순서로 소스 리스트를 구성합니다."""
    ordered: list[SourceItem] = []
    seen_urls: set[str] = set()
    for s in web_sources[:WEB_SOURCE_LIMIT]:
        if s["url"] not in seen_urls:
            seen_urls.add(s["url"])
            ordered.append(s)
    for s in academic_sources[:ACADEMIC_SOURCE_LIMIT]:
        if s["url"] not in seen_urls:
            seen_urls.add(s["url"])
            ordered.append(s)
    return ordered


def _extract_context(article: str, match: re.Match, window: int = 100) -> str:
    """[N] 주변 텍스트를 추출합니다."""
    start = max(0, match.start() - window)
    end = min(len(article), match.end() + window)
    return article[start:end]


# 한국어 조사 패턴 (단어 끝에서 제거)
_PARTICLE_RE = re.compile(
    r"(은|는|이|가|을|를|의|에서|에|으로|로|도|만|까지|부터|와|과|라는|라고|이라|처럼|에선)$"
)


def _strip_particles(word: str) -> str:
    """한국어 조사를 제거합니다."""
    stripped = _PARTICLE_RE.sub("", word)
    return stripped if len(stripped) >= 2 else word


def _keyword_overlap(context: str, snippet: str, min_matches: int = 2) -> bool:
    """컨텍스트와 스니펫의 키워드 겹침을 확인합니다."""
    if not snippet:
        return False
    # 2글자 이상 단어 추출 + 조사 제거
    raw_context = re.findall(r"[\w가-힣]{2,}", context.lower())
    raw_snippet = re.findall(r"[\w가-힣]{2,}", snippet.lower())
    context_words = {_strip_particles(w) for w in raw_context}
    snippet_words = {_strip_particles(w) for w in raw_snippet}
    overlap = context_words & snippet_words
    return len(overlap) >= min_matches


async def citation_validator_node(state: ResearchState) -> dict:
    """아티클의 [N] 인용을 검증합니다."""
    article = state.get("draft_article", "")
    if not article:
        return {"citation_issues": []}

    web_sources = filter_by_graded_urls(
        state.get("web_sources", []), state.get("graded_web_urls", [])
    )
    academic_sources = filter_by_graded_urls(
        state.get("academic_sources", []), state.get("graded_academic_urls", [])
    )
    source_list = _build_source_list(web_sources, academic_sources)
    max_source_id = len(source_list)

    issues: list[str] = []
    citations = list(_CITATION_RE.finditer(article))

    if not citations:
        issues.append("아티클에 [N] 형식의 인용이 없습니다.")
        logger.warning("[CitationValidator] No citations found in article")
        return {"citation_issues": issues}

    out_of_range = []
    mismatch = []

    for match in citations:
        n = int(match.group(1))
        # 범위 검증
        if n < 1 or n > max_source_id:
            out_of_range.append(n)
            continue
        # 키워드 매칭 검증
        source = source_list[n - 1]
        context = _extract_context(article, match)
        snippet = source.get("content_snippet", "")
        if not _keyword_overlap(context, snippet):
            mismatch.append(n)

    if out_of_range:
        issues.append(f"범위 외 인용: {out_of_range} (최대 소스 번호: {max_source_id})")
    if mismatch:
        issues.append(f"내용 불일치 의심 인용: {mismatch}")

    if issues:
        logger.warning("[CitationValidator] Issues found: %s", issues)
    else:
        logger.info(
            "[CitationValidator] All %d citations validated against %d sources",
            len(citations), max_source_id,
        )

    return {"citation_issues": issues}
