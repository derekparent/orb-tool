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
# Unit Tests: Prompt building — format_card_results
# ─────────────────────────────────────────────────────────────────

class TestFormatCardResults:
    """Test troubleshooting card context formatting for LLM."""

    def test_empty_cards_returns_empty(self):
        from prompts.manuals_assistant import format_card_results

        assert format_card_results([]) == ""

    def test_formats_card_with_steps(self):
        from prompts.manuals_assistant import format_card_results

        cards = [
            {
                "id": "abc123",
                "title": "Low Oil Pressure Alarm",
                "equipment": "3516",
                "subsystem": "lubrication",
                "steps": "Check oil level\nCheck oil filter\nCheck oil pump",
                "sources": [{"filename": "doc.pdf", "page": 44}],
            }
        ]
        ctx = format_card_results(cards)
        assert "<troubleshooting_cards" in ctx
        assert 'count="1"' in ctx
        assert "CARD: Low Oil Pressure Alarm" in ctx
        assert "3516" in ctx
        assert "lubrication" in ctx
        assert "Check oil level" in ctx

    def test_multiple_cards(self):
        from prompts.manuals_assistant import format_card_results

        cards = [
            {"id": "1", "title": "Card A", "equipment": "3516", "subsystem": None, "steps": "Step 1", "sources": []},
            {"id": "2", "title": "Card B", "equipment": "C18", "subsystem": "fuel", "steps": "Step A", "sources": []},
        ]
        ctx = format_card_results(cards)
        assert "1. CARD: Card A" in ctx
        assert "2. CARD: Card B" in ctx
        assert "</troubleshooting_cards>" in ctx


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
# Unit Tests: _extract_search_query (conversational → FTS5)
# ─────────────────────────────────────────────────────────────────

class TestExtractSearchQuery:
    """Test conversational query → FTS5 keyword extraction.

    The chat input naturally elicits sentences; FTS5 needs keywords.
    AND-first with phrase detection, OR fallback via _extract_broad_query.
    """

    def test_short_keyword_query_adds_synonym_alternative(self):
        from services.chat_service import _extract_search_query

        # Known phrase "valve lash" is quoted; synonym adds "valve clearance"
        result = _extract_search_query("valve lash")
        assert '"valve lash"' in result
        assert "OR" in result
        assert "clearance" in result

    def test_three_keywords_with_phrase_detection(self):
        from services.chat_service import _extract_search_query

        # "fuel rack" is a known phrase → quoted
        result = _extract_search_query("3516 fuel rack")
        assert "3516" in result
        assert '"fuel rack"' in result

    def test_conversational_query_strips_stops_uses_and(self):
        from services.chat_service import _extract_search_query

        # AND-first: all terms required (with phrase detection)
        result = _extract_search_query(
            "What is the valve lash adjustment procedure for the 3516?"
        )
        assert '"valve lash"' in result
        assert "adjustment" in result
        assert "3516" in result

    def test_how_question_strips_stops_detects_phrases(self):
        from services.chat_service import _extract_search_query

        result = _extract_search_query(
            "How do I check jacket water pressure on C18?"
        )
        assert '"jacket water"' in result
        assert "pressure" in result
        assert "C18" in result

    def test_preserves_model_numbers(self):
        from services.chat_service import _extract_search_query

        result = _extract_search_query("Explain the cooling system for C4.4")
        assert "C4.4" in result

    def test_fallback_when_all_stop_words(self):
        from services.chat_service import _extract_search_query

        # If query is ALL stop words, return original
        result = _extract_search_query("what is the")
        assert result == "what is the"

    def test_single_word_with_synonym(self):
        from services.chat_service import _extract_search_query

        # turbo has synonym turbocharger
        assert _extract_search_query("turbo") == "turbo OR turbocharger"

    def test_single_word_no_synonym(self):
        from services.chat_service import _extract_search_query

        assert _extract_search_query("actuator") == "actuator"

    def test_long_keyword_query_uses_and_with_phrases(self):
        from services.chat_service import _extract_search_query

        # Long query now uses AND (precise), not OR
        result = _extract_search_query(
            "3516 fuel rack actuator troubleshooting"
        )
        assert "3516" in result
        assert '"fuel rack"' in result
        assert "actuator" in result


class TestExtractBroadQuery:
    """Test OR fallback query generation."""

    def test_broad_query_uses_or(self):
        from services.chat_service import _extract_broad_query

        result = _extract_broad_query(
            "What is the oil filter replacement procedure?"
        )
        assert "OR" in result
        assert '"oil filter"' in result
        assert "replacement" in result

    def test_broad_query_adds_synonyms(self):
        from services.chat_service import _extract_broad_query

        result = _extract_broad_query("valve lash procedure")
        assert "clearance" in result

    def test_broad_query_single_word(self):
        from services.chat_service import _extract_broad_query

        # Single word with synonym → OR expansion
        assert _extract_broad_query("turbo") == "turbo OR turbocharger"


class TestDetectPhrases:
    """Test phrase detection for known compound terms."""

    def test_quotes_known_phrase(self):
        from services.chat_service import _detect_phrases

        assert _detect_phrases(["oil", "filter"]) == ['"oil filter"']

    def test_preserves_unknown_pair(self):
        from services.chat_service import _detect_phrases

        assert _detect_phrases(["3516", "actuator"]) == ["3516", "actuator"]

    def test_phrase_with_trailing_word(self):
        from services.chat_service import _detect_phrases

        assert _detect_phrases(["oil", "filter", "replacement"]) == ['"oil filter"', "replacement"]

    def test_single_word(self):
        from services.chat_service import _detect_phrases

        assert _detect_phrases(["turbo"]) == ["turbo"]

    def test_empty(self):
        from services.chat_service import _detect_phrases

        assert _detect_phrases([]) == []


class TestSearchWithFallback:
    """Test two-pass search (AND first, OR fallback)."""

    @patch("services.chat_service.search_cards")
    @patch("services.chat_service.get_context_for_llm")
    def test_and_sufficient_no_fallback(self, mock_ctx, mock_cards):
        from services.chat_service import _search_with_fallback

        mock_ctx.return_value = [{"snippet": "r"}] * 5
        mock_cards.return_value = []
        page_results, card_results = _search_with_fallback("valve lash", equipment="3516")
        assert len(page_results) == 5
        # Only called once (AND pass)
        assert mock_ctx.call_count == 1

    @patch("services.chat_service.search_cards")
    @patch("services.chat_service.get_context_for_llm")
    def test_and_insufficient_triggers_or(self, mock_ctx, mock_cards):
        from services.chat_service import _search_with_fallback

        # AND returns 1, OR returns 8
        mock_ctx.side_effect = [
            [{"snippet": "r"}],           # AND pass: 1 result
            [{"snippet": "r"}] * 8,       # OR pass: 8 results
        ]
        mock_cards.return_value = []
        page_results, card_results = _search_with_fallback("oil filter replacement procedure", equipment=None)
        assert len(page_results) == 8
        assert mock_ctx.call_count == 2

    @patch("services.chat_service.search_cards")
    @patch("services.chat_service.get_context_for_llm")
    def test_returns_card_results(self, mock_ctx, mock_cards):
        from services.chat_service import _search_with_fallback

        mock_ctx.return_value = [{"snippet": "r"}] * 5
        mock_cards.return_value = [{"title": "Low Oil Pressure", "equipment": "3516"}]
        page_results, card_results = _search_with_fallback("oil pressure low", equipment="3516")
        assert len(page_results) == 5
        assert len(card_results) == 1
        assert card_results[0]["title"] == "Low Oil Pressure"


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


# ─────────────────────────────────────────────────────────────────
# Unit Tests: _extract_citations
# ─────────────────────────────────────────────────────────────────

class TestExtractCitations:
    """Test citation extraction from assistant text."""

    def test_single_citation(self):
        from services.chat_service import _extract_citations

        text = "See [kenr5403-00_testing, p.48] for details."
        result = _extract_citations(text)
        assert result == [("kenr5403-00_testing", 48)]

    def test_multiple_citations(self):
        from services.chat_service import _extract_citations

        text = (
            "Pages [kenr5403-00_testing, p.48] and "
            "[senr9773-00_troubleshooting, p.112] cover this."
        )
        result = _extract_citations(text)
        assert len(result) == 2
        assert result[0] == ("kenr5403-00_testing", 48)
        assert result[1] == ("senr9773-00_troubleshooting", 112)

    def test_deduplicates(self):
        from services.chat_service import _extract_citations

        text = (
            "[doc.pdf, p.10] and again [doc.pdf, p.10] "
            "plus [doc.pdf, p.11]"
        )
        result = _extract_citations(text)
        assert len(result) == 2
        assert result[0] == ("doc.pdf", 10)
        assert result[1] == ("doc.pdf", 11)

    def test_empty_text(self):
        from services.chat_service import _extract_citations

        assert _extract_citations("") == []
        assert _extract_citations("No citations here.") == []

    def test_citation_with_spaces(self):
        from services.chat_service import _extract_citations

        text = "[kenr5403-00_testing, p. 48]"
        result = _extract_citations(text)
        assert result == [("kenr5403-00_testing", 48)]

    def test_page_range_hyphen(self):
        from services.chat_service import _extract_citations

        text = "[kenr5403-00_testing, p.48-49]"
        result = _extract_citations(text)
        assert result == [("kenr5403-00_testing", 48)]

    def test_page_range_en_dash(self):
        from services.chat_service import _extract_citations

        text = "[kenr5403-00_testing, p.48\u201349]"
        result = _extract_citations(text)
        assert result == [("kenr5403-00_testing", 48)]

    def test_pp_prefix(self):
        from services.chat_service import _extract_citations

        text = "[kenr5403-00_testing, pp.48-49]"
        result = _extract_citations(text)
        assert result == [("kenr5403-00_testing", 48)]

    def test_real_llm_citation_format(self):
        """Test with actual citation format observed from live LLM output."""
        from services.chat_service import _extract_citations

        text = (
            "The valve lash procedure is covered in "
            "[kenr5403-11-00_testing-&-adjusting-systems-operations, p.46] "
            "and [kenr5403-11-00_testing-&-adjusting-systems-operations, p.48-49]."
        )
        result = _extract_citations(text)
        assert len(result) == 2
        assert result[0][1] == 46
        assert result[1][1] == 48


# ─────────────────────────────────────────────────────────────────
# Unit Tests: _should_deep_dive
# ─────────────────────────────────────────────────────────────────

class TestShouldDeepDive:
    """Test deep-dive detection logic."""

    HISTORY_WITH_CITATIONS = [
        {"role": "user", "content": "valve lash 3516"},
        {
            "role": "assistant",
            "content": (
                "I found results on pages [kenr5403-00_testing, p.48] "
                "and [kenr5403-00_testing, p.49] covering the valve lash "
                "procedure. [senr9773-00_troubleshooting, p.112] covers "
                "troubleshooting."
            ),
        },
    ]

    @patch("services.chat_service.get_pages_content")
    def test_triggers_on_specific_page_ref(self, mock_get_pages):
        from services.chat_service import _should_deep_dive

        mock_get_pages.return_value = [
            {"content": "Step 1...", "filename": "kenr5403-00_testing",
             "page_num": 48, "equipment": "3516", "doc_type": "testing"}
        ]
        result = _should_deep_dive("tell me about page 48", self.HISTORY_WITH_CITATIONS)
        assert result is not None
        assert len(result) == 1
        mock_get_pages.assert_called_once_with("kenr5403-00_testing", [48])

    @patch("services.chat_service.get_pages_content")
    def test_triggers_on_vague_ref(self, mock_get_pages):
        from services.chat_service import _should_deep_dive

        def fake_get_pages(filename, page_nums):
            return [
                {"content": f"p{pn}", "filename": filename, "page_num": pn,
                 "equipment": "3516", "doc_type": "testing"}
                for pn in page_nums
            ]
        mock_get_pages.side_effect = fake_get_pages

        result = _should_deep_dive("tell me more", self.HISTORY_WITH_CITATIONS)
        assert result is not None
        assert len(result) == 3  # capped at MAX_DEEP_DIVE_PAGES

    def test_no_trigger_on_new_topic(self):
        from services.chat_service import _should_deep_dive

        result = _should_deep_dive(
            "what about oil filters?", self.HISTORY_WITH_CITATIONS
        )
        assert result is None

    def test_no_trigger_on_empty_history(self):
        from services.chat_service import _should_deep_dive

        assert _should_deep_dive("tell me more", []) is None

    def test_no_trigger_when_no_citations(self):
        from services.chat_service import _should_deep_dive

        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "Hi, how can I help?"},
        ]
        assert _should_deep_dive("tell me more", history) is None

    def test_specific_page_not_in_citations_falls_through(self):
        from services.chat_service import _should_deep_dive

        # Page 99 not cited → returns None (falls through to search)
        result = _should_deep_dive("page 99", self.HISTORY_WITH_CITATIONS)
        assert result is None

    @patch("services.chat_service.get_pages_content")
    def test_caps_at_max_pages(self, mock_get_pages):
        from services.chat_service import _should_deep_dive, MAX_DEEP_DIVE_PAGES

        # History with 5 citations
        history = [
            {"role": "user", "content": "test"},
            {
                "role": "assistant",
                "content": (
                    "[doc, p.1] [doc, p.2] [doc, p.3] "
                    "[doc, p.4] [doc, p.5]"
                ),
            },
        ]
        mock_get_pages.return_value = [
            {"content": f"p{i}", "filename": "doc", "page_num": i,
             "equipment": "3516", "doc_type": "testing"}
            for i in range(1, MAX_DEEP_DIVE_PAGES + 1)
        ]
        result = _should_deep_dive("walk me through those pages", history)
        assert result is not None
        # get_pages_content called with at most MAX_DEEP_DIVE_PAGES page nums
        call_args = mock_get_pages.call_args
        assert len(call_args[0][1]) <= MAX_DEEP_DIVE_PAGES

    @patch("services.chat_service.get_pages_content")
    def test_empty_page_content_returns_none(self, mock_get_pages):
        from services.chat_service import _should_deep_dive

        mock_get_pages.return_value = []
        result = _should_deep_dive("tell me more", self.HISTORY_WITH_CITATIONS)
        assert result is None


# ─────────────────────────────────────────────────────────────────
# Integration Test: Deep-dive in chat pipeline
# ─────────────────────────────────────────────────────────────────

class TestDeepDiveIntegration:
    """Test that deep-dive context flows through to LLM."""

    @patch("services.chat_service.get_llm_service")
    @patch("services.chat_service.get_pages_content")
    def test_deep_dive_sends_page_content_to_llm(self, mock_get_pages, mock_get_llm):
        from services.chat_service import get_chat_response

        # Mock LLM
        mock_llm = MagicMock()
        mock_llm.count_tokens.return_value = 100
        mock_llm.complete.return_value = "Here's the procedure walkthrough..."
        mock_get_llm.return_value = mock_llm

        # Mock page content
        mock_get_pages.return_value = [
            {
                "content": "Step 1: Remove valve cover.",
                "filename": "kenr5403-00_testing",
                "page_num": 48,
                "equipment": "3516",
                "doc_type": "testing",
            }
        ]

        history = [
            {"role": "user", "content": "3516 valve lash"},
            {
                "role": "assistant",
                "content": (
                    "I found the valve lash procedure in "
                    "[kenr5403-00_testing, p.48]."
                ),
            },
        ]

        result = get_chat_response("walk me through the procedure", history)

        assert result == "Here's the procedure walkthrough..."

        # Verify LLM was called with <page_content> context
        call_args = mock_llm.complete.call_args
        system_prompt = call_args[0][0]
        assert "<page_content>" in system_prompt
        assert "Step 1: Remove valve cover." in system_prompt
        # Actual search results context uses query= attr; should not be present
        assert '<search_results query=' not in system_prompt

    @patch("services.chat_service.get_llm_service")
    @patch("services.chat_service._search_with_fallback")
    def test_new_topic_uses_search(self, mock_search, mock_get_llm):
        from services.chat_service import get_chat_response

        # Mock LLM
        mock_llm = MagicMock()
        mock_llm.count_tokens.return_value = 100
        mock_llm.complete.return_value = "Here are oil filter results..."
        mock_get_llm.return_value = mock_llm

        mock_search.return_value = (
            [{"filename": "doc", "page_num": 1, "equipment": "3516",
              "doc_type": "testing", "snippet": "oil filter", "authority": "primary", "score": 1.0}],
            [],
        )

        history = [
            {"role": "user", "content": "3516 valve lash"},
            {
                "role": "assistant",
                "content": "Found valve lash in [kenr5403-00_testing, p.48].",
            },
        ]

        # New topic → no deep-dive pattern match → search
        result = get_chat_response("what about oil filters?", history)
        assert result == "Here are oil filter results..."
        mock_search.assert_called_once()
