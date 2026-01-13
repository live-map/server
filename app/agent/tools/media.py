"""
Media tools for investigation agent.

- get_video_info: Extract video metadata
- translate_text: Multilingual translation
"""

import asyncio
import logging

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
async def get_video_info(url: str) -> dict:
    """
    Extract metadata from video URL.

    Supports most video platforms including YouTube, Twitter, Telegram.
    Extracts information without actual download.

    Args:
        url: Video URL

    Returns:
        Video info {title, description, duration, uploader, upload_date, view_count, thumbnail}
    """
    try:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.get_event_loop().run_in_executor(
                None, lambda: ydl.extract_info(url, download=False)
            )

            return {
                "title": info.get("title", ""),
                "description": (info.get("description", "") or "")[:500],
                "duration": info.get("duration", 0),
                "uploader": info.get("uploader", ""),
                "upload_date": info.get("upload_date", ""),
                "view_count": info.get("view_count", 0),
                "thumbnail": info.get("thumbnail", ""),
                "url": url,
                "platform": info.get("extractor", "unknown"),
            }

    except Exception as e:
        logger.error(f"Video info extraction error: {e}")
        return {"error": str(e), "url": url}


@tool
async def translate_text(text: str, target_lang: str = "en", source_lang: str | None = None) -> dict:
    """
    Translate text.

    Use for translating multilingual content like Persian, Arabic, Russian, Ukrainian.

    Args:
        text: Text to translate
        target_lang: Target language (default: en)
        source_lang: Source language (None for auto-detect)

    Returns:
        {original, translated, source_lang, target_lang}
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Using LibreTranslate public instance
            response = await client.post(
                "https://libretranslate.com/translate",
                json={
                    "q": text[:1000],  # Max 1000 chars
                    "source": source_lang or "auto",
                    "target": target_lang,
                },
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "original": text,
                    "translated": data.get("translatedText", ""),
                    "source_lang": source_lang or "auto",
                    "target_lang": target_lang,
                }
            else:
                return {
                    "original": text,
                    "error": f"Translation failed: {response.status_code}",
                    "note": "LibreTranslate may have rate limits. Consider self-hosting.",
                }

    except Exception as e:
        logger.error(f"Translation error: {e}")
        return {"original": text, "error": str(e)}
