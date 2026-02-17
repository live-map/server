"""
Jina Reader — URL에서 LLM-friendly 마크다운 본문을 추출합니다.

Tavily raw_content가 없거나 불완전할 때 fallback으로 사용.
무료, 한국어 지원.
"""

import logging

import httpx

logger = logging.getLogger(__name__)


class JinaReader:
    """Jina Reader API를 통한 웹 본문 추출."""

    BASE_URL = "https://r.jina.ai"

    async def extract(self, url: str, max_chars: int = 2000) -> str:
        """URL에서 LLM-friendly 마크다운 본문을 추출합니다."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/{url}",
                    headers={
                        "Accept": "application/json",
                        "X-Return-Format": "markdown",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("data", {}).get("content", "")
                    return content[:max_chars] if content else ""
        except Exception as e:
            logger.debug("[JinaReader] Failed to extract %s: %s", url[:60], e)
        return ""
