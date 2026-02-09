"""
Web Search Service — Tavily primary, Brave fallback, SQLite cache.

Provides internet search for the chat assistant's "Check online" feature.
Returns clean, LLM-ready text results for synthesis with manual-based answers.
"""

import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Default marine diesel domains for focused search
DEFAULT_DOMAINS = [
    "caterpillar.com",
    "cat.com",
    "thedieselpage.com",
    "marineinsight.com",
    "barringtondieselclub.co.za",
    "marinediesels.info",
]


class WebSearchService:
    """Web search with Tavily primary, Brave fallback, and SQLite caching."""

    def __init__(
        self,
        tavily_api_key: str,
        brave_api_key: str = "",
        timeout: int = 10,
        cache_ttl: int = 86400,
        max_results: int = 5,
        cache_db_path: str = "",
    ):
        self.tavily_api_key = tavily_api_key
        self.brave_api_key = brave_api_key
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self.max_results = max_results
        self.cache_db_path = cache_db_path
        self._tavily_client = None

        if self.cache_db_path:
            self._init_cache_db()

    def _get_tavily_client(self):
        """Lazy-init Tavily client to avoid import at module load."""
        if self._tavily_client is None:
            from tavily import TavilyClient

            self._tavily_client = TavilyClient(api_key=self.tavily_api_key)
        return self._tavily_client

    def _init_cache_db(self) -> None:
        """Create cache table if it doesn't exist."""
        try:
            Path(self.cache_db_path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.cache_db_path)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS web_search_cache "
                "(query_hash TEXT PRIMARY KEY, results_json TEXT, created_at REAL)"
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.warning("Failed to initialize cache DB: %s", e)

    def _cache_key(
        self, query: str, equipment: str | None, domains: list[str] | None
    ) -> str:
        """Generate deterministic cache key from query parameters."""
        raw = f"{query}|{equipment or ''}|{','.join(sorted(domains or DEFAULT_DOMAINS))}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _cache_get(self, query_hash: str) -> list[dict] | None:
        """Return cached results if fresh, else None."""
        if not self.cache_db_path:
            return None
        try:
            conn = sqlite3.connect(self.cache_db_path)
            row = conn.execute(
                "SELECT results_json, created_at FROM web_search_cache WHERE query_hash = ?",
                (query_hash,),
            ).fetchone()
            conn.close()
            if row:
                age = time.time() - row[1]
                if age < self.cache_ttl:
                    return json.loads(row[0])
        except sqlite3.Error as e:
            logger.warning("Cache read error: %s", e)
        return None

    def _cache_set(self, query_hash: str, results: list[dict]) -> None:
        """Store results in cache."""
        if not self.cache_db_path:
            return
        try:
            conn = sqlite3.connect(self.cache_db_path)
            conn.execute(
                "INSERT OR REPLACE INTO web_search_cache "
                "(query_hash, results_json, created_at) VALUES (?, ?, ?)",
                (query_hash, json.dumps(results), time.time()),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.warning("Cache write error: %s", e)

    def search_online(
        self,
        query: str,
        equipment: str | None = None,
        domains: list[str] | None = None,
    ) -> list[dict] | None:
        """Search the web. Returns list of result dicts or None on total failure.

        Each result dict: {"title": str, "url": str, "content": str, "score": float}
        """
        search_query = (
            f"Caterpillar {equipment} {query}"
            if equipment
            else f"Caterpillar marine diesel {query}"
        )
        search_domains = domains or DEFAULT_DOMAINS

        # Check cache first
        cache_key = self._cache_key(query, equipment, domains)
        cached = self._cache_get(cache_key)
        if cached is not None:
            logger.info("Cache hit for web search: %s", query[:50])
            return cached

        # Try Tavily (primary)
        results = self._tavily_search(search_query, search_domains)

        # Fallback to Brave if Tavily failed
        if results is None and self.brave_api_key:
            logger.info("Tavily failed, falling back to Brave")
            results = self._brave_search(search_query, search_domains)

        # Cache successful results
        if results is not None:
            self._cache_set(cache_key, results)

        return results

    def _tavily_search(self, query: str, domains: list[str]) -> list[dict] | None:
        """Primary search via Tavily API."""
        try:
            client = self._get_tavily_client()
            response = client.search(
                query=query,
                search_depth="basic",
                max_results=self.max_results,
                include_domains=domains,
                include_raw_content=False,
                timeout=self.timeout,
            )
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", ""),
                    "score": r.get("score", 0.0),
                }
                for r in response.get("results", [])
            ]
        except (ConnectionError, TimeoutError) as e:
            logger.warning("Tavily search network error: %s", e)
            return None
        except Exception as e:  # Safety net for unexpected SDK errors
            logger.warning("Tavily search failed: %s", e)
            return None

    def _brave_search(self, query: str, domains: list[str]) -> list[dict] | None:
        """Fallback search via Brave REST API.

        Note: The domains parameter is accepted for interface consistency but
        not used here — Brave's API doesn't support include_domains natively.
        Domain filtering would require site: operators in the query string,
        which can be unreliable with multiple domains. The broad query still
        works well as a fallback since Tavily handles domain filtering.
        """
        try:
            headers = {
                "X-Subscription-Token": self.brave_api_key,
                "Accept": "application/json",
            }
            params = {
                "q": query,
                "count": self.max_results,
            }
            resp = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers=headers,
                params=params,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("description", ""),
                    "score": 0.0,
                }
                for r in data.get("web", {}).get("results", [])
            ]
        except (requests.Timeout, requests.ConnectionError) as e:
            logger.warning("Brave search network error: %s", e)
            return None
        except requests.RequestException as e:
            logger.warning("Brave search HTTP error: %s", e)
            return None
        except Exception as e:  # Safety net for unexpected response parsing errors
            logger.warning("Brave search failed: %s", e)
            return None


# Module-level singleton
_service: Optional[WebSearchService] = None


def create_web_search_service(app) -> Optional[WebSearchService]:
    """Initialize web search service from Flask app config.

    Returns None if TAVILY_API_KEY is not configured (graceful degradation).
    """
    global _service
    tavily_key = app.config.get("TAVILY_API_KEY", "")
    if not tavily_key:
        logger.info("TAVILY_API_KEY not set — web search disabled")
        return None

    cache_path = str(
        Path(app.config.get("BASE_DIR", ".")) / "data" / "web_search_cache.db"
    )

    _service = WebSearchService(
        tavily_api_key=tavily_key,
        brave_api_key=app.config.get("BRAVE_SEARCH_API_KEY", ""),
        timeout=app.config.get("WEB_SEARCH_TIMEOUT", 10),
        cache_ttl=app.config.get("WEB_SEARCH_CACHE_TTL", 86400),
        max_results=app.config.get("WEB_SEARCH_MAX_RESULTS", 5),
        cache_db_path=cache_path,
    )
    logger.info("Web search service initialized (Tavily primary)")
    return _service


def get_web_search_service() -> Optional[WebSearchService]:
    """Get the module-level web search service instance."""
    return _service
