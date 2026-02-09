"""Tests for specific exception handling in routes.

Covers:
  - TypeError/ValueError in manuals search
  - ConnectionError/TimeoutError in chat SSE
  - OperationalError in health check
"""

import json
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ─────────────────────────────────────────────────────────────────
# Tests: Manuals Search Exception Handling
# ─────────────────────────────────────────────────────────────────

class TestManualsSearchExceptions:
    """Test specific exception handling in manuals search route."""

    def test_type_error_returns_invalid_query_error(self, client, logged_in_engineer):
        """Test that TypeError in search query processing returns 'Invalid search query'."""
        # Mock is_manuals_db_available to return True so we get past the early return
        with patch('routes.manuals.is_manuals_db_available', return_value=True), \
             patch('routes.manuals.prepare_smart_query') as mock_prepare, \
             patch('routes.manuals.get_tag_facets', return_value=[]):
            # Trigger TypeError in query preparation
            mock_prepare.side_effect = TypeError("unsupported operand type(s)")

            response = client.get('/manuals/?q=test+query')
            assert response.status_code == 200

            # Check that error message is present in response
            data = response.data.decode('utf-8')
            assert 'Invalid search query' in data

    def test_value_error_returns_invalid_query_error(self, client, logged_in_engineer):
        """Test that ValueError in search query processing returns 'Invalid search query'."""
        # Mock is_manuals_db_available to return True so we get past the early return
        with patch('routes.manuals.is_manuals_db_available', return_value=True), \
             patch('routes.manuals.prepare_smart_query') as mock_prepare, \
             patch('routes.manuals.get_tag_facets', return_value=[]):
            # Trigger ValueError in query preparation
            mock_prepare.side_effect = ValueError("invalid literal for int()")

            response = client.get('/manuals/?q=test+query')
            assert response.status_code == 200

            # Check that error message is present in response
            data = response.data.decode('utf-8')
            assert 'Invalid search query' in data


# ─────────────────────────────────────────────────────────────────
# Tests: Chat SSE Exception Handling
# ─────────────────────────────────────────────────────────────────

class TestChatSSEExceptions:
    """Test specific exception handling in chat SSE stream."""

    def test_connection_error_returns_timeout_message(self, client, logged_in_engineer):
        """Test that ConnectionError in LLM call returns 'Connection to AI service timed out'."""
        # Patch the actual generator function to make it raise ConnectionError
        def mock_generator(*args, **kwargs):
            raise ConnectionError("Connection refused")
            yield  # Never reached but needed for generator syntax

        with patch('routes.chat.stream_chat_response', side_effect=mock_generator), \
             patch('routes.chat.get_fallback_results', return_value=[]):
            response = client.post(
                '/manuals/chat/api/message',
                json={'query': 'test question'},
                content_type='application/json'
            )

            assert response.status_code == 200
            assert 'text/event-stream' in response.content_type

            # Read SSE events
            data = response.data.decode('utf-8')
            assert 'Connection to AI service timed out' in data
            assert '"type": "error"' in data

    def test_timeout_error_returns_timeout_message(self, client, logged_in_engineer):
        """Test that TimeoutError in LLM call returns 'Connection to AI service timed out'."""
        # Patch the actual generator function to make it raise TimeoutError
        def mock_generator(*args, **kwargs):
            raise TimeoutError("Request timed out")
            yield  # Never reached but needed for generator syntax

        with patch('routes.chat.stream_chat_response', side_effect=mock_generator), \
             patch('routes.chat.get_fallback_results', return_value=[]):
            response = client.post(
                '/manuals/chat/api/message',
                json={'query': 'test question'},
                content_type='application/json'
            )

            assert response.status_code == 200
            assert 'text/event-stream' in response.content_type

            # Read SSE events
            data = response.data.decode('utf-8')
            assert 'Connection to AI service timed out' in data
            assert '"type": "error"' in data

    def test_connection_error_with_fallback_results(self, client, logged_in_engineer):
        """Test that ConnectionError includes fallback results if available."""
        def mock_generator(*args, **kwargs):
            raise ConnectionError("Connection refused")
            yield  # Never reached but needed for generator syntax

        fallback = [{'filename': 'test.pdf', 'page_num': 1, 'snippet': 'test'}]
        with patch('routes.chat.stream_chat_response', side_effect=mock_generator), \
             patch('routes.chat.get_fallback_results', return_value=fallback):
            response = client.post(
                '/manuals/chat/api/message',
                json={'query': 'test question'},
                content_type='application/json'
            )

            data = response.data.decode('utf-8')
            assert '"type": "error"' in data
            assert '"type": "fallback"' in data
            assert 'test.pdf' in data


# ─────────────────────────────────────────────────────────────────
# Tests: Health Check Exception Handling
# ─────────────────────────────────────────────────────────────────

class TestHealthCheckExceptions:
    """Test specific exception handling in health check endpoint."""

    def test_operational_error_returns_503(self, client):
        """Test that OperationalError in health check returns 503 with proper JSON."""
        from sqlalchemy.exc import OperationalError

        with patch('models.db.session.execute') as mock_execute:
            # Trigger OperationalError (database connection issue)
            mock_execute.side_effect = OperationalError(
                "connection to server failed", None, None
            )

            response = client.get('/health')
            assert response.status_code == 503

            data = response.get_json()
            assert data['status'] == 'unhealthy'
            assert data['database'] == 'disconnected'
            assert 'version' in data

    def test_generic_exception_returns_503(self, client):
        """Test that unexpected exceptions in health check still return JSON."""
        with patch('models.db.session.execute') as mock_execute:
            # Trigger unexpected exception
            mock_execute.side_effect = RuntimeError("unexpected error")

            response = client.get('/health')
            assert response.status_code == 503

            data = response.get_json()
            assert data['status'] == 'unhealthy'
            assert data['database'] == 'disconnected'
            assert 'version' in data

    def test_successful_health_check(self, client):
        """Test that successful health check returns 200."""
        response = client.get('/health')
        assert response.status_code == 200

        data = response.get_json()
        assert data['status'] == 'healthy'
        assert data['database'] == 'connected'
        assert 'version' in data
