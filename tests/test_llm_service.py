"""Tests for src/services/llm_service.py.

Covers:
  - LLMService.__init__ validation
  - complete() — success, retry on rate limit, retry on 5xx, no retry on 4xx,
    retry on connection error, max retries exhausted
  - stream() — success with token tracking, error wrapping
  - count_tokens() heuristic
  - cost_summary property
  - create_llm_service() factory — with key, without key, model override
  - get_llm_service() singleton access
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import anthropic
from services.llm_service import (
    LLMService,
    LLMServiceError,
    create_llm_service,
    get_llm_service,
)


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _make_response(text="ok", input_tokens=10, output_tokens=5):
    """Build a mock Anthropic response."""
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    resp.usage.input_tokens = input_tokens
    resp.usage.output_tokens = output_tokens
    return resp


def _make_rate_limit_error():
    """Build a mock RateLimitError."""
    resp = MagicMock()
    resp.status_code = 429
    resp.headers = {}
    return anthropic.RateLimitError(
        message="rate limited",
        response=resp,
        body={"error": {"message": "rate limited"}},
    )


def _make_api_status_error(status_code=500):
    """Build a mock APIStatusError with given status code."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = {}
    return anthropic.APIStatusError(
        message="server error",
        response=resp,
        body={"error": {"message": "server error"}},
    )


def _make_connection_error():
    """Build a mock APIConnectionError."""
    return anthropic.APIConnectionError(request=MagicMock())


# ─────────────────────────────────────────────────────────────────
# LLMService.__init__
# ─────────────────────────────────────────────────────────────────

class TestLLMServiceInit:

    def test_raises_on_empty_key(self):
        with pytest.raises(LLMServiceError, match="not set"):
            LLMService(api_key="")

    def test_raises_on_none_key(self):
        with pytest.raises(LLMServiceError, match="not set"):
            LLMService(api_key=None)

    @patch("services.llm_service.anthropic.Anthropic")
    def test_default_model(self, mock_cls):
        svc = LLMService(api_key="sk-test")
        assert svc.model == "claude-sonnet-4-5-20250929"

    @patch("services.llm_service.anthropic.Anthropic")
    def test_custom_model(self, mock_cls):
        svc = LLMService(api_key="sk-test", model="claude-haiku-4-5-20251001")
        assert svc.model == "claude-haiku-4-5-20251001"

    @patch("services.llm_service.anthropic.Anthropic")
    def test_passes_timeout_to_client(self, mock_cls):
        LLMService(api_key="sk-test", timeout=60)
        mock_cls.assert_called_once_with(api_key="sk-test", timeout=60)

    @patch("services.llm_service.anthropic.Anthropic")
    def test_initial_token_counts_zero(self, mock_cls):
        svc = LLMService(api_key="sk-test")
        assert svc.total_input_tokens == 0
        assert svc.total_output_tokens == 0


# ─────────────────────────────────────────────────────────────────
# LLMService.complete()
# ─────────────────────────────────────────────────────────────────

class TestComplete:

    @patch("services.llm_service.anthropic.Anthropic")
    def test_success(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _make_response("hello", 20, 10)

        svc = LLMService(api_key="sk-test")
        result = svc.complete("sys", [{"role": "user", "content": "hi"}])

        assert result == "hello"
        assert svc.total_input_tokens == 20
        assert svc.total_output_tokens == 10

    @patch("services.llm_service.anthropic.Anthropic")
    def test_accumulates_tokens_across_calls(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _make_response("ok", 10, 5)

        svc = LLMService(api_key="sk-test")
        svc.complete("sys", [{"role": "user", "content": "a"}])
        svc.complete("sys", [{"role": "user", "content": "b"}])

        assert svc.total_input_tokens == 20
        assert svc.total_output_tokens == 10

    @patch("services.llm_service.time.sleep")
    @patch("services.llm_service.anthropic.Anthropic")
    def test_retries_on_rate_limit(self, mock_cls, mock_sleep):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.side_effect = [
            _make_rate_limit_error(),
            _make_response("recovered"),
        ]

        svc = LLMService(api_key="sk-test", max_retries=3)
        result = svc.complete("sys", [{"role": "user", "content": "test"}])

        assert result == "recovered"
        mock_sleep.assert_called_once_with(2)  # 2^1

    @patch("services.llm_service.time.sleep")
    @patch("services.llm_service.anthropic.Anthropic")
    def test_rate_limit_exhausts_retries(self, mock_cls, mock_sleep):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.side_effect = _make_rate_limit_error()

        svc = LLMService(api_key="sk-test", max_retries=2)
        with pytest.raises(LLMServiceError, match="Rate limited"):
            svc.complete("sys", [{"role": "user", "content": "test"}])

    @patch("services.llm_service.time.sleep")
    @patch("services.llm_service.anthropic.Anthropic")
    def test_retries_on_5xx(self, mock_cls, mock_sleep):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.side_effect = [
            _make_api_status_error(500),
            _make_response("ok"),
        ]

        svc = LLMService(api_key="sk-test", max_retries=3)
        result = svc.complete("sys", [{"role": "user", "content": "test"}])
        assert result == "ok"

    @patch("services.llm_service.anthropic.Anthropic")
    def test_no_retry_on_4xx(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.side_effect = _make_api_status_error(401)

        svc = LLMService(api_key="sk-test", max_retries=3)
        with pytest.raises(LLMServiceError, match="API error"):
            svc.complete("sys", [{"role": "user", "content": "test"}])

        # Should not have retried — only 1 call
        assert mock_client.messages.create.call_count == 1

    @patch("services.llm_service.time.sleep")
    @patch("services.llm_service.anthropic.Anthropic")
    def test_retries_on_connection_error(self, mock_cls, mock_sleep):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.side_effect = [
            _make_connection_error(),
            _make_response("ok"),
        ]

        svc = LLMService(api_key="sk-test", max_retries=3)
        result = svc.complete("sys", [{"role": "user", "content": "test"}])
        assert result == "ok"

    @patch("services.llm_service.time.sleep")
    @patch("services.llm_service.anthropic.Anthropic")
    def test_connection_error_exhausts_retries(self, mock_cls, mock_sleep):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.side_effect = _make_connection_error()

        svc = LLMService(api_key="sk-test", max_retries=2)
        with pytest.raises(LLMServiceError, match="Cannot reach"):
            svc.complete("sys", [{"role": "user", "content": "test"}])

    @patch("services.llm_service.anthropic.Anthropic")
    def test_passes_max_tokens(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _make_response()

        svc = LLMService(api_key="sk-test")
        svc.complete("sys", [{"role": "user", "content": "hi"}], max_tokens=512)

        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs.get("max_tokens") == 512 or call_kwargs[1].get("max_tokens") == 512


# ─────────────────────────────────────────────────────────────────
# LLMService.stream()
# ─────────────────────────────────────────────────────────────────

class TestStream:

    @patch("services.llm_service.anthropic.Anthropic")
    def test_yields_text_deltas(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        # Mock the context manager returned by client.messages.stream()
        mock_stream_cm = MagicMock()
        mock_stream = MagicMock()
        mock_stream.text_stream = iter(["Hello", " ", "world"])
        final_msg = _make_response("Hello world", 30, 15)
        mock_stream.get_final_message.return_value = final_msg

        mock_stream_cm.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream_cm.__exit__ = MagicMock(return_value=False)
        mock_client.messages.stream.return_value = mock_stream_cm

        svc = LLMService(api_key="sk-test")
        chunks = list(svc.stream("sys", [{"role": "user", "content": "hi"}]))

        assert chunks == ["Hello", " ", "world"]
        assert svc.total_input_tokens == 30
        assert svc.total_output_tokens == 15

    @patch("services.llm_service.anthropic.Anthropic")
    def test_stream_rate_limit_raises(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_stream_cm = MagicMock()
        mock_stream_cm.__enter__ = MagicMock(side_effect=_make_rate_limit_error())
        mock_stream_cm.__exit__ = MagicMock(return_value=False)
        mock_client.messages.stream.return_value = mock_stream_cm

        svc = LLMService(api_key="sk-test")
        with pytest.raises(LLMServiceError, match="Rate limited"):
            list(svc.stream("sys", [{"role": "user", "content": "hi"}]))

    @patch("services.llm_service.anthropic.Anthropic")
    def test_stream_api_error_raises(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_stream_cm = MagicMock()
        mock_stream_cm.__enter__ = MagicMock(side_effect=_make_api_status_error(500))
        mock_stream_cm.__exit__ = MagicMock(return_value=False)
        mock_client.messages.stream.return_value = mock_stream_cm

        svc = LLMService(api_key="sk-test")
        with pytest.raises(LLMServiceError, match="API error"):
            list(svc.stream("sys", [{"role": "user", "content": "hi"}]))

    @patch("services.llm_service.anthropic.Anthropic")
    def test_stream_connection_error_raises(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_stream_cm = MagicMock()
        mock_stream_cm.__enter__ = MagicMock(side_effect=_make_connection_error())
        mock_stream_cm.__exit__ = MagicMock(return_value=False)
        mock_client.messages.stream.return_value = mock_stream_cm

        svc = LLMService(api_key="sk-test")
        with pytest.raises(LLMServiceError, match="Cannot reach"):
            list(svc.stream("sys", [{"role": "user", "content": "hi"}]))


# ─────────────────────────────────────────────────────────────────
# count_tokens / cost_summary
# ─────────────────────────────────────────────────────────────────

class TestTokensAndCost:

    @patch("services.llm_service.anthropic.Anthropic")
    def test_count_tokens_heuristic(self, mock_cls):
        svc = LLMService(api_key="sk-test")
        assert svc.count_tokens("a" * 100) == 25
        assert svc.count_tokens("") == 0
        assert svc.count_tokens("hi") == 0  # 2 // 4 = 0

    @patch("services.llm_service.anthropic.Anthropic")
    def test_cost_summary_initial(self, mock_cls):
        svc = LLMService(api_key="sk-test")
        assert svc.cost_summary == {"input_tokens": 0, "output_tokens": 0}

    @patch("services.llm_service.anthropic.Anthropic")
    def test_cost_summary_after_complete(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _make_response("ok", 100, 50)

        svc = LLMService(api_key="sk-test")
        svc.complete("sys", [{"role": "user", "content": "q"}])

        assert svc.cost_summary == {"input_tokens": 100, "output_tokens": 50}


# ─────────────────────────────────────────────────────────────────
# Module-level factory: create_llm_service / get_llm_service
# ─────────────────────────────────────────────────────────────────

class TestFactory:

    @patch("services.llm_service.anthropic.Anthropic")
    def test_create_with_key(self, mock_cls):
        import services.llm_service as mod

        app = MagicMock()
        app.config.get.side_effect = lambda k, d="": {
            "ANTHROPIC_API_KEY": "sk-real",
            "ANTHROPIC_MODEL": "claude-sonnet-4-5-20250929",
            "CHAT_TIMEOUT": 30,
        }.get(k, d)

        result = create_llm_service(app)
        assert result is not None
        assert isinstance(result, LLMService)

        # Singleton stored
        assert mod._service is result

    def test_create_without_key_returns_none(self):
        import services.llm_service as mod

        old = mod._service
        try:
            app = MagicMock()
            app.config.get.side_effect = lambda k, d="": {
                "ANTHROPIC_API_KEY": "",
            }.get(k, d)

            result = create_llm_service(app)
            assert result is None
        finally:
            mod._service = old

    @patch("services.llm_service.anthropic.Anthropic")
    def test_create_with_custom_model(self, mock_cls):
        app = MagicMock()
        app.config.get.side_effect = lambda k, d="": {
            "ANTHROPIC_API_KEY": "sk-real",
            "ANTHROPIC_MODEL": "claude-haiku-4-5-20251001",
            "CHAT_TIMEOUT": 15,
        }.get(k, d)

        svc = create_llm_service(app)
        assert svc.model == "claude-haiku-4-5-20251001"

    @patch("services.llm_service.anthropic.Anthropic")
    def test_get_llm_service_returns_singleton(self, mock_cls):
        import services.llm_service as mod

        app = MagicMock()
        app.config.get.side_effect = lambda k, d="": {
            "ANTHROPIC_API_KEY": "sk-real",
            "ANTHROPIC_MODEL": "claude-sonnet-4-5-20250929",
            "CHAT_TIMEOUT": 30,
        }.get(k, d)

        created = create_llm_service(app)
        fetched = get_llm_service()
        assert fetched is created

    def test_get_llm_service_returns_none_before_init(self):
        import services.llm_service as mod

        old = mod._service
        try:
            mod._service = None
            assert get_llm_service() is None
        finally:
            mod._service = old
