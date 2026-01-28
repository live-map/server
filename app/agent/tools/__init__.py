"""
Investigation agent tools.

Phase 6 Strategy:
- Trigger Scan: Currents, WorldNews, Brave (limited API quotas)
- Investigator: GDELT, DDG only (unlimited, free)

Priority-based search strategy:
1. GDELT (free, unlimited) - News/events specialized, use FIRST
2. DuckDuckGo News (free, unlimited) - Recent news only
3. DuckDuckGo Web (free, unlimited) - General web search (filtered)
4. Tavily (paid) - High-quality fallback, use LAST

Core principles:
- Unlimited free tools for investigation
- Paid/limited APIs reserved for initial trigger scan
- Agent decides search queries
- Tool descriptions guide LLM tool selection
"""

from app.agent.tools.media import get_video_info, translate_text
from app.agent.tools.search import (
    search_news_brave,
    search_news_ddg,
    search_news_gdelt,
    search_web,
    search_web_free,
)
from app.agent.tools.social import search_telegram, search_youtube

# Investigator tools - ONLY unlimited/free APIs (Phase 6 optimization)
# Brave is used in trigger scan, not investigation
INVESTIGATOR_TOOLS = [
    # FREE NEWS (unlimited) - Use for evidence
    search_news_gdelt,  # FREE: News/events (GDELT) - ALWAYS use first
    search_news_ddg,    # FREE: Recent news (DuckDuckGo News)
    # FREE WEB (unlimited) - For general info
    search_web_free,    # FREE: General web (DuckDuckGo, filtered)
    search_telegram,    # FREE: Real-time social
    search_youtube,     # FREE: Video search
    # PAID - Fallback only (use sparingly)
    search_web,         # PAID: High-quality fallback (Tavily)
    # Utilities
    get_video_info,
    translate_text,
]

# All tools including Brave (for backward compatibility)
ALL_TOOLS = [
    search_news_gdelt,
    search_news_ddg,
    search_news_brave,  # Limited: 2000/month - used in trigger scan
    search_web_free,
    search_telegram,
    search_youtube,
    search_web,
    get_video_info,
    translate_text,
]

# Tool descriptions for investigator (Phase 6: no Brave - reserved for trigger scan)
TOOL_DESCRIPTIONS = """
Available tools (UNLIMITED FREE TOOLS for investigation):

=== FREE NEWS SEARCH TOOLS (Unlimited) ===

1. search_news_gdelt(query, timespan) - FREE news search (GDELT)
   - ALWAYS use FIRST for breaking news, conflicts, protests
   - 100,000+ global news sources, 100+ languages
   - timespan: 1h, 6h, 12h, 24h, 48h, 72h
   - Auto-translates non-English queries

2. search_news_ddg(query) - FREE news search (DuckDuckGo News)
   - Returns ONLY recent news articles
   - Filters out Wikipedia and old content
   - Auto-translates non-English queries

=== FREE WEB SEARCH TOOLS (Unlimited) ===

3. search_web_free(query) - FREE general web search (DuckDuckGo)
   - Automatically filters Wikipedia and old URLs
   - Use for background research
   - No API key needed

4. search_telegram(query, channel) - FREE real-time search
   - Field footage, local reports
   - Specify channel name recommended

5. search_youtube(query) - FREE video search
   - Protest, war, conflict videos

=== PAID SEARCH TOOLS (Fallback Only) ===

6. search_web(query) - PAID web search (Tavily)
   - Use ONLY when free tools return insufficient results
   - Higher accuracy (93.3%) but costs money
   - Last resort for important information

=== UTILITY TOOLS ===

7. get_video_info(url) - Extract video metadata
8. translate_text(text, target_lang) - Translation

INVESTIGATION RULES:
1. ALWAYS start with search_news_gdelt for news/events
2. Use search_news_ddg for additional recent news
3. Use search_web_free for background research
4. Only use search_web (Tavily) if free tools fail
5. Focus on getting diverse sources from different outlets
"""

__all__ = [
    "ALL_TOOLS",
    "INVESTIGATOR_TOOLS",
    "TOOL_DESCRIPTIONS",
    "search_web",
    "search_web_free",
    "search_news_gdelt",
    "search_news_ddg",
    "search_news_brave",
    "search_telegram",
    "search_youtube",
    "get_video_info",
    "translate_text",
]
