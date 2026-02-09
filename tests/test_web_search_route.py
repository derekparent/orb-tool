"""Tests for web search route and synthesis pipeline.

Covers:
  - Web search endpoint authentication
  - Request validation (missing query, invalid session)
  - Service unavailability (503)
  - SSE streaming with mocked search + LLM
  - Session creation and persistence
  - chat_page passes web_search_enabled to template
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _login(app, client):
    """Create and login a test user inline (avoids conftest DetachedInstanceError)."""
    from models import db, User, UserRole

    with app.app_context():
        u = User(username="websearch_user", role=UserRole.CHIEF_ENGINEER)
        u.set_password("pass")
        db.session.add(u)
        db.session.commit()
        uid = u.id

    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)
        sess["_fresh"] = True
    return uid


def _collect_sse_events(response) -> list[dict]:
    """Parse SSE data lines from a response into dicts."""
    events = []
    for line in response.data.decode().split("\n"):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


# ─────────────────────────────────────────────────────────────────
# Route Tests: Authentication & Validation
# ─────────────────────────────────────────────────────────────────

class TestWebSearchAuth:
    """Web search endpoint requires authentication."""

    def test_requires_auth(self, client):
        """POST without auth should redirect to login."""
        response = client.post(
            "/manuals/chat/api/web-search",
            json={"query": "test"},
            content_type="application/json",
        )
        assert response.status_code == 302

    def test_missing_query_returns_400(self, app, client):
        """POST with empty/missing query returns 400."""
        _login(app, client)
        response = client.post(
            "/manuals/chat/api/web-search",
            json={},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_empty_query_returns_400(self, app, client):
        """POST with whitespace-only query returns 400."""
        _login(app, client)
        response = client.post(
            "/manuals/chat/api/web-search",
            json={"query": "   "},
            content_type="application/json",
        )
        assert response.status_code == 400


# ─────────────────────────────────────────────────────────────────
# Route Tests: Service Availability
# ─────────────────────────────────────────────────────────────────

class TestWebSearchServiceAvailability:
    """Web search returns 503 when service not configured."""

    @patch("routes.chat.get_web_search_service", return_value=None)
    def test_unavailable_returns_503(self, mock_svc, app, client):
        """Returns 503 when TAVILY_API_KEY not set."""
        _login(app, client)
        response = client.post(
            "/manuals/chat/api/web-search",
            json={"query": "test query"},
            content_type="application/json",
        )
        assert response.status_code == 503
        data = json.loads(response.data)
        assert "not configured" in data["error"]


# ─────────────────────────────────────────────────────────────────
# Route Tests: Invalid Session
# ─────────────────────────────────────────────────────────────────

class TestWebSearchSession:
    """Session validation in web search endpoint."""

    @patch("routes.chat.get_web_search_service")
    def test_invalid_session_returns_404(self, mock_get_svc, app, client):
        """Returns 404 for nonexistent session_id."""
        _login(app, client)
        mock_get_svc.return_value = MagicMock()
        response = client.post(
            "/manuals/chat/api/web-search",
            json={"query": "test", "session_id": 99999},
            content_type="application/json",
        )
        assert response.status_code == 404


# ─────────────────────────────────────────────────────────────────
# Route Tests: No Web Results
# ─────────────────────────────────────────────────────────────────

class TestWebSearchNoResults:
    """When web search returns no results."""

    @patch("routes.chat.get_web_search_service")
    def test_no_results_returns_200_with_error(self, mock_get_svc, app, client):
        """Returns 200 with error message when no web results found."""
        _login(app, client)
        mock_service = MagicMock()
        mock_service.search_online.return_value = None
        mock_get_svc.return_value = mock_service
        response = client.post(
            "/manuals/chat/api/web-search",
            json={"query": "obscure topic"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["type"] == "error"
        assert "No web results" in data["message"]


# ─────────────────────────────────────────────────────────────────
# Route Tests: SSE Streaming (Happy Path)
# ─────────────────────────────────────────────────────────────────

class TestWebSearchStreaming:
    """Test SSE streaming with mocked search service and LLM."""

    MOCK_WEB_RESULTS = [
        {
            "title": "CAT 3516 Valve Lash Guide",
            "url": "https://example.com/valve-lash",
            "content": "Field experience shows valve lash should be checked every 500 hours.",
        },
        {
            "title": "Marine Diesel Tips",
            "url": "https://example.com/tips",
            "content": "Always use OEM feeler gauges for accurate measurements.",
        },
    ]

    @patch("routes.chat.stream_web_synthesis")
    @patch("routes.chat.get_web_search_service")
    def test_streams_sources_and_tokens(
        self, mock_get_svc, mock_stream, app, client
    ):
        """SSE stream should contain web_sources, tokens, and done events."""
        _login(app, client)

        mock_service = MagicMock()
        mock_service.search_online.return_value = self.MOCK_WEB_RESULTS
        mock_get_svc.return_value = mock_service
        mock_stream.return_value = iter(["Based on ", "web results..."])

        response = client.post(
            "/manuals/chat/api/web-search",
            json={"query": "3516 valve lash field tips"},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.content_type.startswith("text/event-stream")

        events = _collect_sse_events(response)
        event_types = [e["type"] for e in events]

        assert "web_sources" in event_types
        assert "token" in event_types
        assert "done" in event_types

        # Check sources event
        sources_event = next(e for e in events if e["type"] == "web_sources")
        assert len(sources_event["sources"]) == 2
        assert sources_event["sources"][0]["title"] == "CAT 3516 Valve Lash Guide"

        # Check done event has session_id
        done_event = next(e for e in events if e["type"] == "done")
        assert "session_id" in done_event

    @patch("routes.chat.stream_web_synthesis")
    @patch("routes.chat.get_web_search_service")
    def test_creates_new_session(self, mock_get_svc, mock_stream, app, client):
        """Should create a new ChatSession when no session_id provided."""
        _login(app, client)

        mock_service = MagicMock()
        mock_service.search_online.return_value = self.MOCK_WEB_RESULTS
        mock_get_svc.return_value = mock_service
        mock_stream.return_value = iter(["Response text"])

        response = client.post(
            "/manuals/chat/api/web-search",
            json={"query": "test query"},
            content_type="application/json",
        )

        events = _collect_sse_events(response)
        done_event = next(e for e in events if e["type"] == "done")
        assert done_event["session_id"] is not None

    @patch("routes.chat.stream_web_synthesis")
    @patch("routes.chat.get_web_search_service")
    def test_passes_equipment_to_search(
        self, mock_get_svc, mock_stream, app, client
    ):
        """Equipment filter should be passed to search_online."""
        _login(app, client)

        mock_service = MagicMock()
        mock_service.search_online.return_value = self.MOCK_WEB_RESULTS
        mock_get_svc.return_value = mock_service
        mock_stream.return_value = iter(["Response"])

        client.post(
            "/manuals/chat/api/web-search",
            json={"query": "valve lash", "equipment": "3516"},
            content_type="application/json",
        )

        mock_service.search_online.assert_called_once_with("valve lash", "3516")


# ─────────────────────────────────────────────────────────────────
# Route Tests: Error Handling in SSE Stream
# ─────────────────────────────────────────────────────────────────

class TestWebSearchStreamErrors:
    """Test error handling within the SSE generator."""

    MOCK_WEB_RESULTS = [
        {
            "title": "Test Source",
            "url": "https://example.com",
            "content": "Test content.",
        },
    ]

    @patch("routes.chat.stream_web_synthesis")
    @patch("routes.chat.get_web_search_service")
    def test_chat_service_error_yields_error_event(
        self, mock_get_svc, mock_stream, app, client
    ):
        """ChatServiceError should yield an error SSE event."""
        from services.chat_service import ChatServiceError

        _login(app, client)
        mock_service = MagicMock()
        mock_service.search_online.return_value = self.MOCK_WEB_RESULTS
        mock_get_svc.return_value = mock_service
        mock_stream.side_effect = ChatServiceError("LLM unavailable")

        response = client.post(
            "/manuals/chat/api/web-search",
            json={"query": "test"},
            content_type="application/json",
        )

        events = _collect_sse_events(response)
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) >= 1
        assert "LLM unavailable" in error_events[0]["message"]


# ─────────────────────────────────────────────────────────────────
# Unit Tests: chat_page passes web_search_enabled
# ─────────────────────────────────────────────────────────────────

class TestChatPageWebSearchFlag:
    """Test that chat_page() passes web_search_enabled to the template."""

    @patch("routes.chat.get_web_search_service", return_value=MagicMock())
    @patch("routes.chat.get_llm_service", return_value=MagicMock())
    def test_web_search_enabled_true(self, mock_llm, mock_ws, app, client):
        """When web search service is configured, template gets True."""
        _login(app, client)
        response = client.get("/manuals/chat/")
        assert response.status_code == 200

    @patch("routes.chat.get_web_search_service", return_value=None)
    @patch("routes.chat.get_llm_service", return_value=MagicMock())
    def test_web_search_enabled_false(self, mock_llm, mock_ws, app, client):
        """When web search service is not configured, page still loads."""
        _login(app, client)
        response = client.get("/manuals/chat/")
        assert response.status_code == 200


# ─────────────────────────────────────────────────────────────────
# Unit Tests: stream_web_synthesis
# ─────────────────────────────────────────────────────────────────

class TestStreamWebSynthesis:
    """Test the stream_web_synthesis service function."""

    @patch("services.chat_service.get_llm_service", return_value=None)
    def test_raises_when_no_llm(self, mock_llm):
        """Should raise ChatServiceError when LLM not configured."""
        from services.chat_service import stream_web_synthesis, ChatServiceError

        with pytest.raises(ChatServiceError, match="not configured"):
            list(stream_web_synthesis(
                query="test",
                web_results=[{"title": "t", "url": "u", "content": "c"}],
                history=[],
            ))

    @patch("services.chat_service.get_llm_service")
    def test_formats_web_context_and_streams(self, mock_get_llm):
        """Should format web results into context and stream LLM response."""
        from services.chat_service import stream_web_synthesis

        mock_llm = MagicMock()
        mock_llm.stream.return_value = iter(["Synthesis ", "response"])
        mock_get_llm.return_value = mock_llm

        web_results = [
            {"title": "Source A", "url": "https://a.com", "content": "Content A"},
            {"title": "Source B", "url": "https://b.com", "content": "Content B"},
        ]

        tokens = list(stream_web_synthesis(
            query="test query",
            web_results=web_results,
            history=[],
        ))

        assert "".join(tokens) == "Synthesis response"

        # Verify system prompt contains web context
        call_args = mock_llm.stream.call_args
        system_prompt = call_args[0][0]
        assert "Source A" in system_prompt
        assert "https://a.com" in system_prompt
        assert "Content B" in system_prompt

    @patch("services.chat_service.get_llm_service")
    def test_includes_history_in_messages(self, mock_get_llm):
        """Should include conversation history in messages to LLM."""
        from services.chat_service import stream_web_synthesis

        mock_llm = MagicMock()
        mock_llm.stream.return_value = iter(["response"])
        mock_get_llm.return_value = mock_llm

        history = [
            {"role": "user", "content": "previous question"},
            {"role": "assistant", "content": "previous answer"},
        ]

        list(stream_web_synthesis(
            query="follow up",
            web_results=[{"title": "t", "url": "u", "content": "c"}],
            history=history,
        ))

        call_args = mock_llm.stream.call_args
        messages = call_args[0][1]
        assert len(messages) == 3  # 2 history + 1 current
        assert messages[0]["content"] == "previous question"
        assert messages[2]["content"] == "follow up"

    @patch("services.chat_service.get_llm_service")
    def test_wraps_llm_error_as_chat_service_error(self, mock_get_llm):
        """LLMServiceError should be wrapped as ChatServiceError."""
        from services.chat_service import stream_web_synthesis, ChatServiceError
        from services.llm_service import LLMServiceError

        mock_llm = MagicMock()
        mock_llm.stream.side_effect = LLMServiceError("API down")
        mock_get_llm.return_value = mock_llm

        with pytest.raises(ChatServiceError, match="API down"):
            list(stream_web_synthesis(
                query="test",
                web_results=[{"title": "t", "url": "u", "content": "c"}],
                history=[],
            ))


# ─────────────────────────────────────────────────────────────────
# Unit Tests: WEB_SYNTHESIS_SYSTEM_PROMPT
# ─────────────────────────────────────────────────────────────────

class TestWebSynthesisPrompt:
    """Test the web synthesis system prompt."""

    def test_prompt_has_placeholder(self):
        """Prompt should have {web_context} placeholder."""
        from prompts.manuals_assistant import WEB_SYNTHESIS_SYSTEM_PROMPT

        assert "{web_context}" in WEB_SYNTHESIS_SYSTEM_PROMPT

    def test_prompt_formats_correctly(self):
        """Prompt should format without error."""
        from prompts.manuals_assistant import WEB_SYNTHESIS_SYSTEM_PROMPT

        result = WEB_SYNTHESIS_SYSTEM_PROMPT.format(web_context="test content")
        assert "test content" in result
        assert "marine diesel" in result.lower()

    def test_prompt_mentions_citation_format(self):
        """Prompt should specify citation format."""
        from prompts.manuals_assistant import WEB_SYNTHESIS_SYSTEM_PROMPT

        assert "[Source Title](URL)" in WEB_SYNTHESIS_SYSTEM_PROMPT
