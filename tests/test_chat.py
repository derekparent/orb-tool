"""Tests for LLM Manuals Assistant feature."""

import json
import pytest
from unittest.mock import patch, MagicMock

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ─────────────────────────────────────────────────────────────────
# Unit Tests: Prompt building
# ─────────────────────────────────────────────────────────────────

class TestFormatContext:
    """Test context formatting for LLM."""

    def test_empty_results(self):
        from prompts.manuals_assistant import format_context

        ctx = format_context([])
        assert "<context>" in ctx
        assert "No relevant manual excerpts found" in ctx

    def test_formats_results_with_citations(self):
        from prompts.manuals_assistant import format_context

        results = [
            {
                "content": "Torque to 45 Nm",
                "filename": "3516_testing.pdf",
                "page_num": 12,
                "equipment": "3516",
                "doc_type": "testing",
                "authority": "primary",
            }
        ]
        ctx = format_context(results)
        assert "Excerpt 1" in ctx
        assert "[PRIMARY]" in ctx
        assert "3516_testing.pdf" in ctx
        assert "Page 12" in ctx
        assert "Torque to 45 Nm" in ctx

    def test_multiple_results(self):
        from prompts.manuals_assistant import format_context

        results = [
            {
                "content": "Step 1",
                "filename": "a.pdf",
                "page_num": 1,
                "equipment": "3516",
                "doc_type": "testing",
                "authority": "primary",
            },
            {
                "content": "Step 2",
                "filename": "b.pdf",
                "page_num": 5,
                "equipment": "C18",
                "doc_type": "service",
                "authority": "unset",
            },
        ]
        ctx = format_context(results)
        assert "Excerpt 1" in ctx
        assert "Excerpt 2" in ctx
        assert "a.pdf" in ctx
        assert "b.pdf" in ctx

    def test_unset_authority_no_label(self):
        from prompts.manuals_assistant import format_context

        results = [
            {
                "content": "Content",
                "filename": "doc.pdf",
                "page_num": 1,
                "equipment": "C32",
                "doc_type": "O&M",
                "authority": "unset",
            }
        ]
        ctx = format_context(results)
        assert "[UNSET]" not in ctx
        assert "Excerpt 1 ---" in ctx


class TestBuildMessages:
    """Test message assembly."""

    def test_builds_system_with_context(self):
        from prompts.manuals_assistant import build_messages

        system, messages = build_messages("<context>test</context>", [], "my query")
        assert "<context>test</context>" in system
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "my query"

    def test_includes_history(self):
        from prompts.manuals_assistant import build_messages

        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        system, messages = build_messages("<context/>", history, "follow up")
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "hello"
        assert messages[2]["content"] == "follow up"


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
# Unit Tests: get_context_for_llm
# ─────────────────────────────────────────────────────────────────

class TestGetContextForLLM:
    """Test RAG context retrieval."""

    @patch("services.manuals_service.load_manuals_database")
    def test_returns_empty_when_no_db(self, mock_db):
        from services.manuals_service import get_context_for_llm

        mock_db.return_value = None
        results = get_context_for_llm("test query")
        assert results == []

    @patch("services.manuals_service.load_manuals_database")
    def test_returns_structured_results(self, mock_db):
        from services.manuals_service import get_context_for_llm

        # Set up mock DB
        mock_conn = MagicMock()
        mock_db.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock row data
        mock_row = {
            "filepath": "/path/to/doc.pdf",
            "filename": "doc.pdf",
            "equipment": "3516",
            "doc_type": "testing",
            "page_num": 5,
            "content": "Torque value is 45 Nm",
            "score": -2.5,
        }
        mock_cursor.fetchall.return_value = [mock_row]

        # Mock authority lookup
        mock_cursor.fetchone.side_effect = [
            {"name": "doc_authority"},  # table exists check
            {"authority_level": "primary"},  # authority lookup
        ]

        results = get_context_for_llm("torque specs")

        assert len(results) == 1
        assert results[0]["content"] == "Torque value is 45 Nm"
        assert results[0]["filename"] == "doc.pdf"
        assert results[0]["equipment"] == "3516"


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
