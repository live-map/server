"""
Shared utilities for the Research Agent nodes.

중복되던 포맷팅/유틸 함수를 통합합니다.
"""

import re

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
