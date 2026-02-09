"""Web Search Service stub — full impl in agent/1-web-search-service branch."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_DOMAINS = [
    "caterpillar.com",
    "cat.com",
    "thedieselpage.com",
    "marineinsight.com",
    "barringtondieselclub.co.za",
    "marinediesels.info",
]


class WebSearchService:
    """Web search with Tavily primary, Brave fallback."""

    def __init__(self, tavily_api_key: str, **kwargs):
        self.tavily_api_key = tavily_api_key

    def search_online(
        self,
        query: str,
        equipment: str | None = None,
        domains: list[str] | None = None,
    ) -> list[dict] | None:
        """Search the web. Returns list of result dicts or None."""
        return None  # Stub


_service: Optional[WebSearchService] = None


def create_web_search_service(app) -> Optional[WebSearchService]:
    """Initialize the web search service from Flask app config.

    Returns None if Tavily API key is not configured (graceful degradation).
    """
    global _service
    tavily_key = app.config.get("TAVILY_API_KEY", "")
    if not tavily_key:
        logger.info("TAVILY_API_KEY not set — web search disabled")
        return None
    _service = WebSearchService(tavily_api_key=tavily_key)
    return _service


def get_web_search_service() -> Optional[WebSearchService]:
    """Get the module-level web search service instance."""
    return _service
