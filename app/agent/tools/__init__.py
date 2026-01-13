"""
Investigation agent tools.

Priority-based search strategy (based on expert research):
1. GDELT (free) - News/events specialized, use FIRST
2. DuckDuckGo (free) - General web search
3. Tavily (paid) - High-quality fallback, use LAST

Core principles:
- Free tools first, paid tools as fallback
- Agent decides search queries
- Tool descriptions guide LLM tool selection
"""

from app.agent.tools.media import get_video_info, translate_text
from app.agent.tools.search import search_news_gdelt, search_web, search_web_free
from app.agent.tools.social import search_telegram, search_youtube

# All tools for LangGraph (ordered by priority: free first, paid last)
ALL_TOOLS = [
    # FREE - Use these first
    search_news_gdelt,  # FREE: News/events (GDELT)
    search_web_free,    # FREE: General web (DuckDuckGo)
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

=== FREE SEARCH TOOLS (Primary) ===

1. search_news_gdelt(query, timespan) - FREE news search
   - ALWAYS use FIRST for breaking news, conflicts, protests
   - 100,000+ global news sources, 100+ languages
   - timespan: 1h, 6h, 12h, 24h, 48h, 72h

2. search_web_free(query) - FREE general web search (DuckDuckGo)
   - Use for general information, articles, blogs
   - Good for background research
   - No API key needed

3. search_telegram(query, channel) - FREE real-time search
   - Field footage, local reports
   - Specify channel name recommended

4. search_youtube(query) - FREE video search
   - Protest, war, conflict videos

=== PAID SEARCH TOOLS (Fallback Only) ===

5. search_web(query) - PAID web search (Tavily)
   - Use ONLY when free tools return insufficient results
   - Higher accuracy (93.3%) but costs money
   - Last resort for important information

=== UTILITY TOOLS ===

6. get_video_info(url) - Extract video metadata
7. translate_text(text, target_lang) - Translation

COST OPTIMIZATION RULES:
1. Start with search_news_gdelt for news/events
2. Use search_web_free for general searches
3. Only use search_web (Tavily) if free tools fail
"""

__all__ = [
    "ALL_TOOLS",
    "TOOL_DESCRIPTIONS",
    "search_web",
    "search_web_free",
    "search_news_gdelt",
    "search_telegram",
    "search_youtube",
    "get_video_info",
    "translate_text",
]
