"""
Investigation agent tools.

Core principles:
- No hardcoded source lists
- Agent decides search queries
- Tool descriptions guide LLM tool selection
"""

from app.agent.tools.media import get_video_info, translate_text
from app.agent.tools.search import search_news_gdelt, search_web
from app.agent.tools.social import search_telegram, search_youtube

# All tools for LangGraph
ALL_TOOLS = [
    search_web,
    search_news_gdelt,
    search_telegram,
    search_youtube,
    get_video_info,
    translate_text,
]

# Tool descriptions for agent prompts
TOOL_DESCRIPTIONS = """
Available tools:

1. search_web(query) - Tavily-based web search
   - Search news articles, blogs, official sites
   - Can include source name in query (e.g., "Iran International protest")
   - Most versatile tool

2. search_news_gdelt(query, timespan) - GDELT news search (free)
   - Search 100,000+ global news sources
   - Recent 1h to 72h news
   - Search by keywords without specifying sources

3. search_telegram(query, channel) - Telegram search
   - Real-time field footage, local reports
   - Only searches subscribed channels
   - Specify channel name recommended

4. search_youtube(query) - YouTube video search
   - Protest, war, conflict videos
   - Free API

5. get_video_info(url) - Extract video metadata
   - YouTube, Twitter, Telegram video info
   - Extract info without download

6. translate_text(text, target_lang) - Translation
   - Persian, Arabic, Russian translation
   - Essential for multilingual content

Core principles:
- Source lists are NOT hardcoded
- Agent decides appropriate search queries based on situation
- Example: Iran protest -> Include "Iran International" in search query
"""

__all__ = [
    "ALL_TOOLS",
    "TOOL_DESCRIPTIONS",
    "search_web",
    "search_news_gdelt",
    "search_telegram",
    "search_youtube",
    "get_video_info",
    "translate_text",
]
