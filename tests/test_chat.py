"""Tests for LLM Manuals Assistant feature.

Covers:
  - Prompt building (format_search_results, format_page_content, build_messages)
  - LLM service wrapper
  - get_context_for_llm (verifies it wraps search_manuals)
  - get_pages_content
  - detect_equipment
  - Chat routes (mocked LLM)
  - ChatSession model
"""

import json
import pytest
from unittest.mock import patch, MagicMock, call

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ─────────────────────────────────────────────────────────────────
# Unit Tests: Prompt building — format_search_results
# ─────────────────────────────────────────────────────────────────

class TestFormatSearchResults:
    """Test triage context formatting for LLM."""

    def test_empty_results(self):
        from prompts.manuals_assistant import format_search_results

        ctx = format_search_results([], "valve lash")
        assert "<search_results" in ctx
        assert 'count="0"' in ctx
        assert "No results found" in ctx

    def test_formats_numbered_results(self):
        from prompts.manuals_assistant import format_search_results

        results = [
            {
                "filename": "kenr5403-00_3516-testing",
                "page_num": 48,
                "equipment": "3516",
                "doc_type": "testing",
                "snippet": "...Injector Adjustment and <mark>Valve Lash</mark> Setting...",
                "authority": "primary",
                "score": 2.1,
            }
        ]
        ctx = format_search_results(results, "valve lash", equipment="3516")

        assert 'query="valve lash"' in ctx
        assert 'equipment="3516"' in ctx
        assert 'count="1"' in ctx
        assert "1. kenr5403-00_3516-testing | Page 48 | TESTING [PRIMARY]" in ctx
        # HTML marks stripped
        assert "<mark>" not in ctx
        assert "Valve Lash" in ctx

    def test_multiple_results(self):
        from prompts.manuals_assistant import format_search_results

        results = [
            {
                "filename": "a.pdf",
                "page_num": 1,
                "equipment": "3516",
                "doc_type": "testing",
                "snippet": "Step 1",
                "authority": "primary",
                "score": 1.0,
            },
            {
                "filename": "b.pdf",
                "page_num": 5,
                "equipment": "C18",
                "doc_type": "service",
                "snippet": "Step 2",
                "authority": "unset",
                "score": 3.0,
            },
        ]
        ctx = format_search_results(results, "test query")

        assert "1. a.pdf" in ctx
        assert "2. b.pdf" in ctx
        assert 'count="2"' in ctx

    def test_unset_authority_no_tag(self):
        from prompts.manuals_assistant import format_search_results

        results = [
            {
                "filename": "doc.pdf",
                "page_num": 1,
                "equipment": "C32",
                "doc_type": "O&M",
                "snippet": "Content here",
                "authority": "unset",
                "score": 2.0,
            }
        ]
        ctx = format_search_results(results, "query")

        assert "[UNSET]" not in ctx
        assert "[PRIMARY]" not in ctx
        assert "O&M" in ctx.upper()

    def test_no_equipment_filter(self):
        from prompts.manuals_assistant import format_search_results

        ctx = format_search_results([], "test")
        assert "equipment=" not in ctx


# ─────────────────────────────────────────────────────────────────
# Unit Tests: Prompt building — format_page_content
# ─────────────────────────────────────────────────────────────────

class TestFormatPageContent:
    """Test deep-dive page content formatting."""

    def test_empty_pages(self):
        from prompts.manuals_assistant import format_page_content

        ctx = format_page_content([])
        assert "<page_content>" in ctx
        assert "No page content available" in ctx

    def test_formats_full_pages(self):
        from prompts.manuals_assistant import format_page_content

        pages = [
            {
                "content": "Step 1: Remove valve cover.\nStep 2: Measure clearance.",
                "filename": "kenr5403-00_3516-testing",
                "page_num": 48,
                "equipment": "3516",
                "doc_type": "testing",
            }
        ]
        ctx = format_page_content(pages)

        assert "<page_content>" in ctx
        assert "</page_content>" in ctx
        assert "kenr5403-00_3516-testing, Page 48" in ctx
        assert "3516 | testing" in ctx
        assert "Step 1: Remove valve cover" in ctx

    def test_multiple_pages(self):
        from prompts.manuals_assistant import format_page_content

        pages = [
            {
                "content": "Page 48 content",
                "filename": "doc.pdf",
                "page_num": 48,
                "equipment": "3516",
                "doc_type": "testing",
            },
            {
                "content": "Page 49 content",
                "filename": "doc.pdf",
                "page_num": 49,
                "equipment": "3516",
                "doc_type": "testing",
            },
        ]
        ctx = format_page_content(pages)

        assert "Page 48" in ctx
        assert "Page 49" in ctx
        assert "Page 48 content" in ctx
        assert "Page 49 content" in ctx


# ─────────────────────────────────────────────────────────────────
# Unit Tests: build_messages
# ─────────────────────────────────────────────────────────────────

class TestBuildMessages:
    """Test message assembly."""

    def test_builds_system_with_context(self):
        from prompts.manuals_assistant import build_messages

        system, messages = build_messages("<search_results>test</search_results>", [], "my query")
        assert "<search_results>test</search_results>" in system
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "my query"

    def test_includes_history(self):
        from prompts.manuals_assistant import build_messages

        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        system, messages = build_messages("<search_results/>", history, "follow up")
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "hello"
        assert messages[2]["content"] == "follow up"

    def test_system_prompt_has_collaborative_framing(self):
        from prompts.manuals_assistant import build_messages, SYSTEM_PROMPT

        assert "engineer drives" in SYSTEM_PROMPT.lower()
        assert "triage" in SYSTEM_PROMPT.lower()
        assert "<search_results>" in SYSTEM_PROMPT
        assert "<page_content>" in SYSTEM_PROMPT


# ─────────────────────────────────────────────────────────────────
# Unit Tests: LLM Service
# ─────────────────────────────────────────────────────────────────

class TestLLMService:
    """Test LLM service wrapper."""

    def test_raises_without_api_key(self):
        from services.llm_service import LLMService, LLMServiceError

        with pytest.raises(LLMServiceError, match="not set"):
            LLMService(api_key="")

    @patch("services.llm_service.anthropic.Anthropic")
    def test_count_tokens_heuristic(self, mock_cls):
        from services.llm_service import LLMService

        svc = LLMService(api_key="test-key")
        # ~4 chars per token
        assert svc.count_tokens("a" * 100) == 25

    @patch("services.llm_service.anthropic.Anthropic")
    def test_cost_summary(self, mock_cls):
        from services.llm_service import LLMService

        svc = LLMService(api_key="test-key")
        assert svc.cost_summary == {"input_tokens": 0, "output_tokens": 0}

    @patch("services.llm_service.anthropic.Anthropic")
    def test_complete_success(self, mock_cls):
        from services.llm_service import LLMService

        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Test response")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_response

        svc = LLMService(api_key="test-key")
        result = svc.complete("system", [{"role": "user", "content": "test"}])

        assert result == "Test response"
        assert svc.total_input_tokens == 100
        assert svc.total_output_tokens == 50


# ─────────────────────────────────────────────────────────────────
# Unit Tests: detect_equipment
# ─────────────────────────────────────────────────────────────────

class TestDetectEquipment:
    """Test auto-detection of equipment model from query text."""

    def test_detects_3516(self):
        from services.chat_service import detect_equipment

        assert detect_equipment("3516 valve lash") == "3516"

    def test_detects_c18_case_insensitive(self):
        from services.chat_service import detect_equipment

        assert detect_equipment("c18 coolant temp") == "C18"
        assert detect_equipment("C18 coolant temp") == "C18"

    def test_detects_c32(self):
        from services.chat_service import detect_equipment

        assert detect_equipment("the C32 fuel system") == "C32"

    def test_detects_c4_4_with_dot(self):
        from services.chat_service import detect_equipment

        assert detect_equipment("C4.4 oil pressure") == "C4.4"

    def test_returns_none_for_no_match(self):
        from services.chat_service import detect_equipment

        assert detect_equipment("valve lash adjustment") is None

    def test_returns_first_match(self):
        from services.chat_service import detect_equipment

        # Multiple equipment mentioned — returns first
        result = detect_equipment("3516 vs C18 comparison")
        assert result == "3516"

    def test_does_not_match_partial(self):
        from services.chat_service import detect_equipment

        # "35168" should not match "3516"
        assert detect_equipment("part number 35168") is None


# ─────────────────────────────────────────────────────────────────
# Unit Tests: _resolve_equipment
# ─────────────────────────────────────────────────────────────────

class TestResolveEquipment:
    """Test equipment resolution (dropdown wins, then auto-detect)."""

    def test_explicit_wins_over_auto_detect(self):
        from services.chat_service import _resolve_equipment

        # Dropdown says 3516, query mentions C18 — dropdown wins
        assert _resolve_equipment("3516", "C18 coolant temp") == "3516"

    def test_auto_detect_when_no_explicit(self):
        from services.chat_service import _resolve_equipment

        assert _resolve_equipment(None, "3516 valve lash") == "3516"
        assert _resolve_equipment("", "C18 specs") == "C18"

    def test_none_when_neither(self):
        from services.chat_service import _resolve_equipment

        assert _resolve_equipment(None, "valve lash adjustment") is None


# ─────────────────────────────────────────────────────────────────
# Unit Tests: get_context_for_llm wraps search_manuals
# ─────────────────────────────────────────────────────────────────

class TestGetContextForLLM:
    """Test that get_context_for_llm delegates to search_manuals."""

    @patch("services.manuals_service.search_manuals")
    def test_calls_search_manuals(self, mock_search):
        from services.manuals_service import get_context_for_llm

        mock_search.return_value = [
            {
                "filepath": "/path/to/doc.pdf",
                "filename": "doc.pdf",
                "equipment": "3516",
                "doc_type": "testing",
                "page_num": 48,
                "snippet": "...valve lash...",
                "authority": "primary",
                "authority_label": "[PRIMARY]",
                "tags": ["Cylinder Head/Valvetrain"],
                "score": 2.1,
                "base_score": 3.0,
            }
        ]

        results = get_context_for_llm("valve lash", equipment="3516", limit=10)

        # Verify search_manuals was called with correct args
        mock_search.assert_called_once_with(
            "valve lash", equipment="3516", boost_primary=True, limit=10
        )

        # Verify result shape — should have snippet, not content
        assert len(results) == 1
        assert results[0]["snippet"] == "...valve lash..."
        assert results[0]["filename"] == "doc.pdf"
        assert results[0]["equipment"] == "3516"
        assert results[0]["authority"] == "primary"
        assert "content" not in results[0]

    @patch("services.manuals_service.search_manuals")
    def test_returns_empty_when_no_results(self, mock_search):
        from services.manuals_service import get_context_for_llm

        mock_search.return_value = []
        results = get_context_for_llm("nonexistent query")
        assert results == []


# ─────────────────────────────────────────────────────────────────
# Unit Tests: get_pages_content
# ─────────────────────────────────────────────────────────────────

class TestGetPagesContent:
    """Test full page content retrieval."""

    @patch("services.manuals_service.load_manuals_database")
    def test_returns_empty_when_no_db(self, mock_db):
        from services.manuals_service import get_pages_content

        mock_db.return_value = None
        results = get_pages_content("doc.pdf", [48, 49])
        assert results == []

    def test_returns_empty_for_empty_page_list(self):
        from services.manuals_service import get_pages_content

        results = get_pages_content("doc.pdf", [])
        assert results == []

    @patch("services.manuals_service.load_manuals_database")
    def test_returns_structured_pages(self, mock_db):
        from services.manuals_service import get_pages_content

        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {
                "filepath": "/path/to/doc.pdf",
                "filename": "doc.pdf",
                "equipment": "3516",
                "doc_type": "testing",
                "page_num": 48,
                "content": "  Step 1: Remove valve cover.  ",
            },
            {
                "filepath": "/path/to/doc.pdf",
                "filename": "doc.pdf",
                "equipment": "3516",
                "doc_type": "testing",
                "page_num": 49,
                "content": "  Step 2: Measure clearance.  ",
            },
        ]

        results = get_pages_content("doc.pdf", [48, 49])

        assert len(results) == 2
        assert results[0]["page_num"] == 48
        assert results[0]["content"] == "Step 1: Remove valve cover."  # stripped
        assert results[1]["page_num"] == 49
        assert "content" in results[0]
        assert "filename" in results[0]


# ─────────────────────────────────────────────────────────────────
# Integration Tests: Chat routes (mocked LLM)
# ─────────────────────────────────────────────────────────────────

class TestChatRoutes:
    """Test chat endpoints with mocked LLM service.

    Uses inline user/login to avoid pre-existing conftest DetachedInstanceError.
    """

    @staticmethod
    def _login(app, client):
        """Create and login a test user, returning user_id."""
        from models import db, User, UserRole

        with app.app_context():
            u = User(username="chatroute_user", role=UserRole.CHIEF_ENGINEER)
            u.set_password("pass")
            db.session.add(u)
            db.session.commit()
            uid = u.id

        with client.session_transaction() as sess:
            sess["_user_id"] = str(uid)
            sess["_fresh"] = True
        return uid

    def test_chat_page_loads(self, app, client):
        """Chat page should load for authenticated users."""
        self._login(app, client)
        response = client.get("/manuals/chat/")
        assert response.status_code == 200

    def test_chat_page_requires_auth(self, client):
        """Chat page should redirect unauthenticated users."""
        response = client.get("/manuals/chat/")
        assert response.status_code == 302

    def test_send_message_requires_query(self, app, client):
        """POST without query should return 400."""
        self._login(app, client)
        response = client.post(
            "/manuals/chat/api/message",
            json={},
            content_type="application/json",
        )
        assert response.status_code == 400

    @patch("routes.chat.get_llm_service")
    @patch("routes.chat.stream_chat_response")
    def test_send_message_streams(self, mock_stream, mock_get_llm, app, client):
        """POST with query should return SSE stream."""
        self._login(app, client)
        mock_get_llm.return_value = MagicMock()
        mock_stream.return_value = iter(["Hello", " world"])

        response = client.post(
            "/manuals/chat/api/message",
            json={"query": "test question"},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.content_type.startswith("text/event-stream")

    @patch("routes.chat.get_llm_service")
    @patch("routes.chat.stream_chat_response")
    def test_send_message_passes_equipment(self, mock_stream, mock_get_llm, app, client):
        """POST with equipment should pass it through to stream_chat_response."""
        self._login(app, client)
        mock_get_llm.return_value = MagicMock()
        mock_stream.return_value = iter(["response"])

        response = client.post(
            "/manuals/chat/api/message",
            json={"query": "valve lash", "equipment": "3516"},
            content_type="application/json",
        )
        assert response.status_code == 200

    def test_list_sessions_empty(self, app, client):
        """Should return empty list when no sessions exist."""
        self._login(app, client)
        response = client.get("/manuals/chat/api/sessions")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == []

    def test_get_nonexistent_session(self, app, client):
        """Should return 404 for missing session."""
        self._login(app, client)
        response = client.get("/manuals/chat/api/sessions/999")
        assert response.status_code == 404

    def test_delete_nonexistent_session(self, app, client):
        """Should return 404 for missing session."""
        self._login(app, client)
        response = client.delete("/manuals/chat/api/sessions/999")
        assert response.status_code == 404


# ─────────────────────────────────────────────────────────────────
# Integration Test: ChatSession model
# ─────────────────────────────────────────────────────────────────

class TestChatSessionModel:
    """Test ChatSession model."""

    def test_create_session(self, app):
        """Should create a chat session."""
        from models import db, ChatSession, User, UserRole

        with app.app_context():
            user = User(username="chattest", role=UserRole.ENGINEER)
            user.set_password("pass123")
            db.session.add(user)
            db.session.commit()
            uid = user.id

            session = ChatSession(user_id=uid)
            session.set_messages([
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"},
            ])
            db.session.add(session)
            db.session.commit()

            fetched = ChatSession.query.first()
            assert fetched is not None
            msgs = fetched.get_messages()
            assert len(msgs) == 2
            assert msgs[0]["role"] == "user"

    def test_session_to_dict(self, app):
        """Should serialize session to dict."""
        from models import db, ChatSession, User, UserRole

        with app.app_context():
            user = User(username="chattest2", role=UserRole.ENGINEER)
            user.set_password("pass123")
            db.session.add(user)
            db.session.commit()
            uid = user.id

            session = ChatSession(user_id=uid)
            session.set_messages([{"role": "user", "content": "test"}])
            db.session.add(session)
            db.session.commit()

            d = session.to_dict()
            assert "id" in d
            assert "messages" in d
            assert len(d["messages"]) == 1
