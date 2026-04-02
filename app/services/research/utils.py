"""
Shared utilities for the Research Agent nodes.

중복되던 포맷팅/유틸 함수를 통합합니다.
"""

import re
from urllib.parse import urlparse

from app.services.research.config import (
    CRED_SCORE_ACADEMIC_DOMAIN,
    CRED_SCORE_DEFAULT_DOMAIN,
    CRED_SCORE_GOV_DOMAIN,
    CRED_SCORE_NEWS_DOMAIN,
    CRED_SCORE_TRUSTED_DOMAIN,
    CRED_SNIPPET_QUALITY_DIVISOR,
    CRED_SOURCE_TYPE_SCORES,
    CRED_WEIGHT_CONTENT,
    CRED_WEIGHT_DOMAIN,
    CRED_WEIGHT_SOURCE_TYPE,
    ACADEMIC_DOMAINS,
    GOV_DOMAINS,
    NEWS_DOMAINS,
    TRUSTED_DOMAINS,
)
from app.services.research.state import SourceItem


# 결론 섹션 패턴 (synthesizer, reviewer 공용)
CONCLUSION_RE = re.compile(
    r"\n#{2,3}\s*(결론|요약|정리|마무리|맺음|종합)[^\n]*\n",
    re.MULTILINE,
)

# 결론 키워드 (presence-only 체크용)
CONCLUSION_KEYWORDS_RE = re.compile(r"#{2,3}\s*(결론|요약|정리|마무리|맺음|종합)")


def sanitize_user_input(
    text: str,
    max_length: int = 1000,
    tag: str = "user_input",
) -> str:
    """사용자 입력을 LLM 프롬프트용으로 안전하게 래핑합니다.

    - 길이 제한 적용
    - XML 태그로 래핑하여 프롬프트 인젝션 방지
    """
    truncated = text[:max_length] if text else ""
    return f"<{tag}>{truncated}</{tag}>"


def format_perspectives_inline(perspectives: list[dict]) -> str:
    """관점 목록을 인라인 bullet 형식으로 포맷합니다 (planner, gap_analyzer용)."""
    parts = []
    for p in perspectives:
        questions = ", ".join(p.get("key_questions", []))
        parts.append(f"- **{p['label']}**: {p['description']} (핵심 질문: {questions})")
    return "\n".join(parts)


def build_numbered_sources_brief(
    web_sources: list[SourceItem],
    academic_sources: list[SourceItem],
) -> str:
    """출처를 통합 번호로 매핑하여 간략 텍스트로 반환합니다 (outline_generator용)."""
    seen_urls: set[str] = set()
    parts: list[str] = []
    idx = 1

    for s in web_sources[:15]:
        if s["url"] in seen_urls:
            continue
        seen_urls.add(s["url"])
        snippet = s["content_snippet"][:200] if s.get("content_snippet") else ""
        parts.append(f"[{idx}] {s['title']} ({s['credibility']}) — {snippet}")
        idx += 1

    for s in academic_sources[:10]:
        if s["url"] in seen_urls:
            continue
        seen_urls.add(s["url"])
        snippet = s["content_snippet"][:200] if s.get("content_snippet") else ""
        parts.append(f"[{idx}] {s['title']} (학술) — {snippet}")
        idx += 1

    return "\n".join(parts) if parts else "(출처 없음)"


def filter_by_graded_urls(
    sources: list[SourceItem],
    graded_urls: list[str],
) -> list[SourceItem]:
    """graded_urls가 비어 있으면 모든 sources 반환 (fail-open).

    비어 있지 않으면 URL이 허용목록에 포함된 sources만 반환.
    """
    if not graded_urls:
        return sources
    url_set = set(graded_urls)
    return [s for s in sources if s["url"] in url_set]


def compute_credibility_score(
    url: str,
    source_type: str,
    snippet: str,
    *,
    api_score: float | None = None,
    citation_count: int | None = None,
) -> float:
    """다중 요소 기반 0.0-1.0 신뢰도 점수를 계산합니다.

    Args:
        url: 소스 URL
        source_type: NEWS | PAPER | ARTICLE | OTHER
        snippet: 콘텐츠 스니펫
        api_score: 검색 API 제공 점수 (Tavily score 등, 0-1)
        citation_count: 학술 인용 수 (Semantic Scholar)
    """
    import math

    # 1. 도메인 신뢰도
    domain = urlparse(url).netloc.lower() if url else ""
    if any(d in domain for d in TRUSTED_DOMAINS):
        domain_score = CRED_SCORE_TRUSTED_DOMAIN
    elif any(d in domain for d in GOV_DOMAINS):
        domain_score = CRED_SCORE_GOV_DOMAIN
    elif any(d in domain for d in ACADEMIC_DOMAINS):
        domain_score = CRED_SCORE_ACADEMIC_DOMAIN
    elif any(d in domain for d in NEWS_DOMAINS):
        domain_score = CRED_SCORE_NEWS_DOMAIN
    else:
        domain_score = CRED_SCORE_DEFAULT_DOMAIN

    # 2. 콘텐츠 품질 (API 점수 우선, 없으면 스니펫 길이 기반)
    if api_score is not None:
        content_score = min(max(api_score, 0.0), 1.0)
    elif citation_count is not None:
        # 학술: 인용수 기반 (log 스케일, 1000회 이상 → 1.0)
        content_score = min(math.log(citation_count + 1) / math.log(1000), 1.0)
    else:
        content_score = min(len(snippet) / CRED_SNIPPET_QUALITY_DIVISOR, 1.0)

    # 3. 소스 유형
    type_score = CRED_SOURCE_TYPE_SCORES.get(source_type, 0.5)

    score = (
        CRED_WEIGHT_DOMAIN * domain_score
        + CRED_WEIGHT_CONTENT * content_score
        + CRED_WEIGHT_SOURCE_TYPE * type_score
    )
    return round(min(max(score, 0.0), 1.0), 3)
