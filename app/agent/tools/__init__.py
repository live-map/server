"""
Investigation agent tools.

Priority-based search strategy (P1 Enhanced):
1. GDELT (free) - News/events specialized, use FIRST
2. DuckDuckGo News (free) - Recent news only
3. Brave Search (free tier) - P1: 2000 queries/month
4. DuckDuckGo Web (free) - General web search (filtered)
5. Tavily (paid) - High-quality fallback, use LAST

P1 Enhancements:
- Multi-engine parallel search
- Non-English query translation
- Response caching (15 min TTL)
- Brave Search integration

Core principles:
- Free tools first, paid tools as fallback
- NEWS tools for evidence gathering (not general web)
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

# All tools for LangGraph (ordered by priority: free first, paid last)
ALL_TOOLS = [
    # FREE NEWS - Use these first for evidence
    search_news_gdelt,  # FREE: News/events (GDELT)
    search_news_ddg,    # FREE: Recent news (DuckDuckGo News)
    search_news_brave,  # FREE: Brave Search (P1: 2000/month)
    # FREE WEB - For general info
    search_web_free,    # FREE: General web (DuckDuckGo, filtered)
    search_telegram,    # FREE: Real-time social
    search_youtube,     # FREE: Video search
    # PAID - Fallback only
    search_web,         # PAID: High-quality fallback (Tavily)
    # Utilities
    get_video_info,
    translate_text,
]

# Tool descriptions for agent prompts (with priority guidance)
TOOL_DESCRIPTIONS = """
Available tools (USE FREE TOOLS FIRST to save costs):

=== FREE NEWS SEARCH TOOLS (Use for Evidence) ===

1. search_news_gdelt(query, timespan) - FREE news search (GDELT)
   - ALWAYS use FIRST for breaking news, conflicts, protests
   - 100,000+ global news sources, 100+ languages
   - timespan: 1h, 6h, 12h, 24h, 48h, 72h
   - P1: Auto-translates non-English queries

2. search_news_ddg(query) - FREE news search (DuckDuckGo News)
   - Returns ONLY recent news articles
   - Filters out Wikipedia and old content
   - P1: Auto-translates non-English queries

3. search_news_brave(query) - FREE news search (Brave Search, P1)
   - 2000 queries/month free tier
   - High-quality results with freshness filter
   - Use as additional source for better coverage

=== FREE WEB SEARCH TOOLS (Filtered) ===

4. search_web_free(query) - FREE general web search (DuckDuckGo)
   - Automatically filters Wikipedia and old URLs
   - Use for background research
   - No API key needed

5. search_telegram(query, channel) - FREE real-time search
   - Field footage, local reports
   - Specify channel name recommended

6. search_youtube(query) - FREE video search
   - Protest, war, conflict videos

=== PAID SEARCH TOOLS (Fallback Only) ===

7. search_web(query) - PAID web search (Tavily)
   - Use ONLY when free tools return insufficient results
   - Higher accuracy (93.3%) but costs money
   - Last resort for important information

=== UTILITY TOOLS ===

8. get_video_info(url) - Extract video metadata
9. translate_text(text, target_lang) - Translation

COST OPTIMIZATION RULES:
1. Start with search_news_gdelt for news/events
2. Use search_news_ddg if GDELT has no results
3. Try search_news_brave for broader coverage (P1)
4. Use search_web_free for general searches (filtered)
5. Only use search_web (Tavily) if free tools fail
"""

__all__ = [
    "ALL_TOOLS",
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
