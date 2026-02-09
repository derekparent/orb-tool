"""Tests for src/services/web_search_service.py.

Covers:
  - WebSearchService.__init__ and cache initialization
  - search_online() — Tavily success, Brave fallback, both fail
  - Cache: hit, miss, expired TTL
  - Equipment prefix and custom domains
  - _tavily_search() / _brave_search() error handling
  - create_web_search_service() factory — with key, without key
  - get_web_search_service() singleton access
"""

import json
import sqlite3
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.web_search_service import (
    DEFAULT_DOMAINS,
    WebSearchService,
    create_web_search_service,
    get_web_search_service,
)


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

SAMPLE_TAVILY_RESPONSE = {
    "results": [
        {
            "title": "CAT 3516 Maintenance",
            "url": "https://cat.com/3516-maintenance",
            "content": "Regular maintenance intervals for the 3516...",
            "score": 0.95,
        },
        {
            "title": "Marine Diesel Tips",
            "url": "https://marineinsight.com/diesel-tips",
            "content": "Important maintenance considerations...",
            "score": 0.82,
        },
    ]
}

SAMPLE_BRAVE_RESPONSE = {
    "web": {
        "results": [
            {
                "title": "Brave Result 1",
                "url": "https://example.com/1",
                "description": "Brave found this about diesel engines...",
            },
        ]
    }
}


def _make_service(tmp_path, **kwargs):
    """Create a WebSearchService with a temp cache DB."""
    defaults = {
        "tavily_api_key": "tvly-test-key",
        "brave_api_key": "brave-test-key",
        "timeout": 5,
        "cache_ttl": 3600,
        "max_results": 5,
        "cache_db_path": str(tmp_path / "test_cache.db"),
    }
    defaults.update(kwargs)
    return WebSearchService(**defaults)


# ─────────────────────────────────────────────────────────────────
# Initialization
# ─────────────────────────────────────────────────────────────────


class TestInit:

    def test_creates_cache_db(self, tmp_path):
        svc = _make_service(tmp_path)
        assert Path(svc.cache_db_path).exists()

        # Verify table was created
        conn = sqlite3.connect(svc.cache_db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='web_search_cache'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_no_cache_db_when_path_empty(self):
        svc = WebSearchService(tavily_api_key="tvly-test", cache_db_path="")
        assert svc.cache_db_path == ""

    def test_stores_config_values(self, tmp_path):
        svc = _make_service(
            tmp_path,
            timeout=15,
            cache_ttl=7200,
            max_results=3,
        )
        assert svc.timeout == 15
        assert svc.cache_ttl == 7200
        assert svc.max_results == 3

    def test_lazy_tavily_client_not_created_at_init(self, tmp_path):
        svc = _make_service(tmp_path)
        assert svc._tavily_client is None


# ─────────────────────────────────────────────────────────────────
# Tavily search (primary)
# ─────────────────────────────────────────────────────────────────


class TestTavilySearch:

    @patch("services.web_search_service.WebSearchService._get_tavily_client")
    def test_tavily_success(self, mock_get_client, tmp_path):
        svc = _make_service(tmp_path)
        mock_client = MagicMock()
        mock_client.search.return_value = SAMPLE_TAVILY_RESPONSE
        mock_get_client.return_value = mock_client

        results = svc.search_online("oil pressure alarm")
        assert results is not None
        assert len(results) == 2
        assert results[0]["title"] == "CAT 3516 Maintenance"
        assert results[0]["score"] == 0.95
        assert results[1]["url"] == "https://marineinsight.com/diesel-tips"

    @patch("services.web_search_service.WebSearchService._get_tavily_client")
    def test_tavily_exception_triggers_brave_fallback(
        self, mock_get_client, tmp_path
    ):
        svc = _make_service(tmp_path)
        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("Tavily API down")
        mock_get_client.return_value = mock_client

        with patch.object(svc, "_brave_search", return_value=[{"title": "brave result", "url": "", "content": "", "score": 0.0}]) as mock_brave:
            results = svc.search_online("oil pressure")
            mock_brave.assert_called_once()
            assert results is not None
            assert results[0]["title"] == "brave result"

    @patch("services.web_search_service.WebSearchService._get_tavily_client")
    def test_tavily_timeout_triggers_brave_fallback(
        self, mock_get_client, tmp_path
    ):
        svc = _make_service(tmp_path)
        mock_client = MagicMock()
        mock_client.search.side_effect = TimeoutError("Tavily timeout")
        mock_get_client.return_value = mock_client

        with patch.object(svc, "_brave_search", return_value=[{"title": "brave fallback", "url": "", "content": "", "score": 0.0}]) as mock_brave:
            results = svc.search_online("coolant leak")
            mock_brave.assert_called_once()
            assert results[0]["title"] == "brave fallback"


# ─────────────────────────────────────────────────────────────────
# Brave search (fallback)
# ─────────────────────────────────────────────────────────────────


class TestBraveSearch:

    @patch("services.web_search_service.requests.get")
    @patch("services.web_search_service.WebSearchService._get_tavily_client")
    def test_brave_success_after_tavily_fails(
        self, mock_get_client, mock_requests_get, tmp_path
    ):
        svc = _make_service(tmp_path)
        # Tavily fails
        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("Tavily down")
        mock_get_client.return_value = mock_client

        # Brave succeeds
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_BRAVE_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_resp

        results = svc.search_online("fuel injector")
        assert results is not None
        assert len(results) == 1
        assert results[0]["title"] == "Brave Result 1"
        assert results[0]["content"] == "Brave found this about diesel engines..."
        # Brave results don't have scores
        assert results[0]["score"] == 0.0

    @patch("services.web_search_service.requests.get")
    @patch("services.web_search_service.WebSearchService._get_tavily_client")
    def test_both_fail_returns_none(
        self, mock_get_client, mock_requests_get, tmp_path
    ):
        svc = _make_service(tmp_path)
        # Tavily fails
        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("Tavily down")
        mock_get_client.return_value = mock_client

        # Brave also fails
        mock_requests_get.side_effect = Exception("Brave down")

        results = svc.search_online("engine overheating")
        assert results is None

    @patch("services.web_search_service.WebSearchService._get_tavily_client")
    def test_no_brave_key_skips_fallback(self, mock_get_client, tmp_path):
        svc = _make_service(tmp_path, brave_api_key="")
        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("Tavily down")
        mock_get_client.return_value = mock_client

        results = svc.search_online("turbo failure")
        assert results is None


# ─────────────────────────────────────────────────────────────────
# Cache
# ─────────────────────────────────────────────────────────────────


class TestCache:

    @patch("services.web_search_service.WebSearchService._get_tavily_client")
    def test_cache_hit_skips_api_call(self, mock_get_client, tmp_path):
        svc = _make_service(tmp_path, cache_ttl=3600)

        # Pre-populate cache
        cache_key = svc._cache_key("oil pressure", None, None)
        cached_results = [{"title": "Cached", "url": "", "content": "from cache", "score": 0.9}]
        svc._cache_set(cache_key, cached_results)

        results = svc.search_online("oil pressure")
        assert results == cached_results
        # Tavily client should never have been called
        mock_get_client.assert_not_called()

    @patch("services.web_search_service.WebSearchService._get_tavily_client")
    def test_cache_miss_calls_api_and_stores(self, mock_get_client, tmp_path):
        svc = _make_service(tmp_path, cache_ttl=3600)
        mock_client = MagicMock()
        mock_client.search.return_value = SAMPLE_TAVILY_RESPONSE
        mock_get_client.return_value = mock_client

        # First call — cache miss
        results = svc.search_online("fuel filter replacement")
        assert results is not None
        assert len(results) == 2

        # Verify stored in cache
        cache_key = svc._cache_key("fuel filter replacement", None, None)
        cached = svc._cache_get(cache_key)
        assert cached is not None
        assert len(cached) == 2

    @patch("services.web_search_service.time.time")
    @patch("services.web_search_service.WebSearchService._get_tavily_client")
    def test_expired_cache_triggers_fresh_api_call(
        self, mock_get_client, mock_time, tmp_path
    ):
        svc = _make_service(tmp_path, cache_ttl=3600)

        # Insert cache entry at time 1000
        mock_time.return_value = 1000.0
        cache_key = svc._cache_key("coolant", None, None)
        svc._cache_set(cache_key, [{"title": "Old", "url": "", "content": "", "score": 0.0}])

        # Now time is 1000 + 3601 — expired
        mock_time.return_value = 4601.0
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "results": [{"title": "Fresh", "url": "https://fresh.com", "content": "new data", "score": 0.88}]
        }
        mock_get_client.return_value = mock_client

        results = svc.search_online("coolant")
        assert results is not None
        assert results[0]["title"] == "Fresh"

    def test_cache_disabled_when_no_path(self):
        svc = WebSearchService(tavily_api_key="tvly-test", cache_db_path="")
        # These should be no-ops, not errors
        assert svc._cache_get("any-hash") is None
        svc._cache_set("any-hash", [{"title": "test"}])  # should not raise


# ─────────────────────────────────────────────────────────────────
# Query building
# ─────────────────────────────────────────────────────────────────


class TestQueryBuilding:

    @patch("services.web_search_service.WebSearchService._get_tavily_client")
    def test_equipment_prefix_prepended(self, mock_get_client, tmp_path):
        svc = _make_service(tmp_path)
        mock_client = MagicMock()
        mock_client.search.return_value = {"results": []}
        mock_get_client.return_value = mock_client

        svc.search_online("oil pressure alarm", equipment="3516B")

        call_args = mock_client.search.call_args
        query_sent = call_args.kwargs.get("query") or call_args[1].get("query")
        assert "Caterpillar 3516B" in query_sent
        assert "oil pressure alarm" in query_sent

    @patch("services.web_search_service.WebSearchService._get_tavily_client")
    def test_default_query_without_equipment(self, mock_get_client, tmp_path):
        svc = _make_service(tmp_path)
        mock_client = MagicMock()
        mock_client.search.return_value = {"results": []}
        mock_get_client.return_value = mock_client

        svc.search_online("turbocharger maintenance")

        call_args = mock_client.search.call_args
        query_sent = call_args.kwargs.get("query") or call_args[1].get("query")
        assert "Caterpillar marine diesel" in query_sent
        assert "turbocharger maintenance" in query_sent

    @patch("services.web_search_service.WebSearchService._get_tavily_client")
    def test_custom_domains_override_defaults(self, mock_get_client, tmp_path):
        svc = _make_service(tmp_path)
        mock_client = MagicMock()
        mock_client.search.return_value = {"results": []}
        mock_get_client.return_value = mock_client

        custom_domains = ["example.com", "custom-marine.org"]
        svc.search_online("fuel pump", domains=custom_domains)

        call_args = mock_client.search.call_args
        domains_sent = call_args.kwargs.get("include_domains") or call_args[1].get("include_domains")
        assert domains_sent == custom_domains

    @patch("services.web_search_service.WebSearchService._get_tavily_client")
    def test_default_domains_used_when_none(self, mock_get_client, tmp_path):
        svc = _make_service(tmp_path)
        mock_client = MagicMock()
        mock_client.search.return_value = {"results": []}
        mock_get_client.return_value = mock_client

        svc.search_online("coolant system")

        call_args = mock_client.search.call_args
        domains_sent = call_args.kwargs.get("include_domains") or call_args[1].get("include_domains")
        assert domains_sent == DEFAULT_DOMAINS


# ─────────────────────────────────────────────────────────────────
# Cache key determinism
# ─────────────────────────────────────────────────────────────────


class TestCacheKey:

    def test_same_inputs_produce_same_key(self, tmp_path):
        svc = _make_service(tmp_path)
        key1 = svc._cache_key("oil pressure", "3516B", ["cat.com"])
        key2 = svc._cache_key("oil pressure", "3516B", ["cat.com"])
        assert key1 == key2

    def test_different_queries_produce_different_keys(self, tmp_path):
        svc = _make_service(tmp_path)
        key1 = svc._cache_key("oil pressure", None, None)
        key2 = svc._cache_key("coolant leak", None, None)
        assert key1 != key2

    def test_different_equipment_produces_different_keys(self, tmp_path):
        svc = _make_service(tmp_path)
        key1 = svc._cache_key("oil pressure", "3516B", None)
        key2 = svc._cache_key("oil pressure", "3512", None)
        assert key1 != key2

    def test_domain_order_does_not_matter(self, tmp_path):
        svc = _make_service(tmp_path)
        key1 = svc._cache_key("q", None, ["b.com", "a.com"])
        key2 = svc._cache_key("q", None, ["a.com", "b.com"])
        assert key1 == key2


# ─────────────────────────────────────────────────────────────────
# Factory: create_web_search_service / get_web_search_service
# ─────────────────────────────────────────────────────────────────


class TestFactory:

    def test_no_api_key_returns_none(self):
        import services.web_search_service as mod

        old = mod._service
        try:
            app = MagicMock()
            app.config.get.side_effect = lambda k, d="": {
                "TAVILY_API_KEY": "",
            }.get(k, d)

            result = create_web_search_service(app)
            assert result is None
        finally:
            mod._service = old

    def test_with_tavily_key_creates_service(self, tmp_path):
        import services.web_search_service as mod

        old = mod._service
        try:
            app = MagicMock()
            app.config.get.side_effect = lambda k, d="": {
                "TAVILY_API_KEY": "tvly-real-key",
                "BRAVE_SEARCH_API_KEY": "brave-key",
                "WEB_SEARCH_TIMEOUT": 15,
                "WEB_SEARCH_CACHE_TTL": 7200,
                "WEB_SEARCH_MAX_RESULTS": 3,
                "BASE_DIR": str(tmp_path),
            }.get(k, d)

            result = create_web_search_service(app)
            assert result is not None
            assert isinstance(result, WebSearchService)
            assert result.tavily_api_key == "tvly-real-key"
            assert result.brave_api_key == "brave-key"
            assert result.timeout == 15
            assert result.cache_ttl == 7200
            assert result.max_results == 3

            # Singleton stored
            assert mod._service is result
        finally:
            mod._service = old

    def test_get_returns_singleton(self, tmp_path):
        import services.web_search_service as mod

        old = mod._service
        try:
            app = MagicMock()
            app.config.get.side_effect = lambda k, d="": {
                "TAVILY_API_KEY": "tvly-key",
                "BRAVE_SEARCH_API_KEY": "",
                "WEB_SEARCH_TIMEOUT": 10,
                "WEB_SEARCH_CACHE_TTL": 86400,
                "WEB_SEARCH_MAX_RESULTS": 5,
                "BASE_DIR": str(tmp_path),
            }.get(k, d)

            created = create_web_search_service(app)
            fetched = get_web_search_service()
            assert fetched is created
        finally:
            mod._service = old

    def test_get_returns_none_before_init(self):
        import services.web_search_service as mod

        old = mod._service
        try:
            mod._service = None
            assert get_web_search_service() is None
        finally:
            mod._service = old

    def test_tavily_only_no_brave_key(self, tmp_path):
        import services.web_search_service as mod

        old = mod._service
        try:
            app = MagicMock()
            app.config.get.side_effect = lambda k, d="": {
                "TAVILY_API_KEY": "tvly-key",
                "BRAVE_SEARCH_API_KEY": "",
                "WEB_SEARCH_TIMEOUT": 10,
                "WEB_SEARCH_CACHE_TTL": 86400,
                "WEB_SEARCH_MAX_RESULTS": 5,
                "BASE_DIR": str(tmp_path),
            }.get(k, d)

            result = create_web_search_service(app)
            assert result is not None
            assert result.brave_api_key == ""
        finally:
            mod._service = old
