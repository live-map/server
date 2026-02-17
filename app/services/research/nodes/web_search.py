"""
Web Search node — Tavily API로 웹 검색을 수행합니다.

v2: Jina Reader로 content_snippet 보강, Tavily exclude_domains로
    API 수준 차단 (post-filtering은 2차 안전장치).
"""

import asyncio
import logging
import re
from urllib.parse import urlparse

from app.services.research.state import ResearchState, SourceItem
from app.services.research.tools.jina_reader import JinaReader
from app.services.research.tools.tavily_client import TavilyClient

logger = logging.getLogger(__name__)

# ── 2차 차단 도메인 (Tavily exclude_domains를 통과한 것들의 안전장치) ──
_BLOCKED_DOMAINS = {
    "wiktionary.org", "merriam-webster.com", "dictionary.com", "thesaurus.com",
    "namu.wiki", "ko.wikipedia.org", "en.wikipedia.org", "wikipedia.org",
    "blog.naver.com", "m.blog.naver.com", "tistory.com", "brunch.co.kr",
    "medium.com", "velog.io", "notion.so",
    "reddit.com", "quora.com", "dcinside.com", "fmkorea.com", "theqoo.net",
    "clien.net", "ruliweb.com", "ppomppu.co.kr",
    "maxpreps.com", "espn.com", "sports.yahoo.com",
    "imdb.com", "rottentomatoes.com",
    "amazon.com", "ebay.com", "coupang.com",
    "youtube.com",
}

_BLOCKED_URL_PATTERNS = re.compile(
    r"(blog\.|/blog/|tistory\.com|brunch\.co\.kr|velog\.io|/PostView|"
    r"namu\.wiki|wikipedia\.org|reddit\.com|youtube\.com)",
    re.IGNORECASE,
)

# ── 신뢰 도메인 (공공기관/주요언론/연구기관) ──
_TRUSTED_DOMAINS = {
    "korea.kr", "molit.go.kr", "fsc.go.kr", "law.go.kr",
    "nec.go.kr", "kostat.go.kr", "bok.or.kr",
    "yna.co.kr", "yonhapnews.co.kr",
    "news.kbs.co.kr", "imnews.imbc.com", "news.sbs.co.kr",
    "chosun.com", "joongang.co.kr", "donga.com",
    "hani.co.kr", "khan.co.kr", "mk.co.kr", "hankyung.com",
    "koreaherald.com", "koreatimes.co.kr",
    "kdi.re.kr", "kiep.go.kr", "krei.re.kr", "keei.re.kr",
    "bbc.com", "reuters.com", "apnews.com", "nytimes.com",
    "theguardian.com", "economist.com",
}


def _get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _is_trusted_domain(url: str) -> bool:
    domain = _get_domain(url)
    return any(trusted in domain for trusted in _TRUSTED_DOMAINS)


def _is_relevant_source(source: SourceItem) -> bool:
    url = source.get("url", "")
    for domain in _BLOCKED_DOMAINS:
        if domain in url:
            return False
    if _BLOCKED_URL_PATTERNS.search(url):
        return False
    snippet = source.get("content_snippet", "")
    if len(snippet) < 50:
        return False
    return True


def _boost_trusted_credibility(source: SourceItem) -> SourceItem:
    if _is_trusted_domain(source.get("url", "")):
        return SourceItem(
            title=source["title"],
            url=source["url"],
            source_type=source["source_type"],
            description=source["description"],
            content_snippet=source["content_snippet"],
            credibility="HIGH",
        )
    return source


async def _enrich_with_jina(sources: list[SourceItem]) -> list[SourceItem]:
    """content_snippet이 짧은 출처를 Jina Reader로 병렬 보강합니다."""
    reader = JinaReader()
    sem = asyncio.Semaphore(5)

    async def _enrich_one(source: SourceItem) -> SourceItem:
        async with sem:
            snippet = source.get("content_snippet", "")
            if len(snippet) < 200:
                content = await reader.extract(source["url"], max_chars=1500)
                if content and len(content) > len(snippet):
                    enriched = SourceItem(
                        title=source["title"],
                        url=source["url"],
                        source_type=source["source_type"],
                        description=source["description"],
                        content_snippet=content[:1500],
                        credibility=source["credibility"],
                    )
                    logger.debug(f"[WebSearch] Enriched via Jina: {source['title'][:40]}")
                    return enriched
            return source

    return await asyncio.gather(*[_enrich_one(s) for s in sources])


async def web_search_node(state: ResearchState) -> dict:
    """모든 웹 검색 쿼리를 병렬로 실행합니다."""
    queries = state.get("search_queries", [])
    if not queries:
        logger.warning("[WebSearch] No search queries provided")
        return {"web_sources": []}

    logger.info(f"[WebSearch] Searching {len(queries)} queries")

    client = TavilyClient()
    tasks = [client.search(q, max_results=5) for q in queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_sources: list[SourceItem] = []
    seen_urls: set[str] = set()
    filtered_count = 0

    for result in results:
        if isinstance(result, Exception):
            logger.error(f"[WebSearch] Query failed: {result}")
            continue
        for source in result:
            if source["url"] in seen_urls:
                continue
            seen_urls.add(source["url"])
            if _is_relevant_source(source):
                all_sources.append(_boost_trusted_credibility(source))
            else:
                filtered_count += 1

    if filtered_count:
        logger.info(f"[WebSearch] Filtered out {filtered_count} irrelevant sources")

    # Jina Reader로 짧은 snippet 보강 (상위 결과만, 나머지 보존)
    if all_sources:
        short_count = sum(1 for s in all_sources if len(s.get("content_snippet", "")) < 200)
        if short_count > 0:
            logger.info(f"[WebSearch] Enriching {short_count} sources with short snippets via Jina")
            enriched = await _enrich_with_jina(all_sources[:20])
            all_sources = enriched + all_sources[20:]

    # 신뢰 도메인 출처를 상위로 정렬
    all_sources.sort(
        key=lambda s: (0 if s["credibility"] == "HIGH" else 1, s["title"])
    )

    logger.info(f"[WebSearch] Collected {len(all_sources)} unique relevant sources")
    return {"web_sources": all_sources}
