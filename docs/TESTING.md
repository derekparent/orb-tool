# Testing Guide

## Quick Start

```bash
# Activate virtualenv
source venv/bin/activate

# Run full suite
pytest

# Run with verbose output
pytest -v

# Run a single test file
pytest tests/test_chat.py

# Run a single test class or method
pytest tests/test_auth.py::TestAuthRoutes::test_login_page
```

## Test Files

| File | Tests | Focus | ~Runtime |
|---|---|---|---|
| `test_api.py` | 83 | API endpoint CRUD, validation, error handling | 10s |
| `test_auth.py` | 26 | Login, RBAC, session persistence | 6s |
| `test_chat.py` | 109 | LLM chat, citations, suggestion chips, prompts | 5s |
| `test_integration.py` | 26 | End-to-end workflows (hitch lifecycle, fuel, ORB) | 8s |
| `test_security.py` | 22 | Input validation, XSS, CSRF, headers, upload | 1s |
| **Total** | **~366** | | **~34s** |

## Running Subsets

```bash
# Only integration tests
pytest -m integration

# Exclude slow performance tests
pytest -m "not slow"

# Only chat/LLM tests
pytest tests/test_chat.py

# Stop on first failure
pytest -x

# Show local variables in tracebacks
pytest --tb=long -l
```

## Known Environment Notes

- **Python 3.14**: `datetime` builtins are immutable — tests avoid `monkeypatch.setattr(datetime, ...)`.
- **Flask test client**: Does not enforce `MAX_CONTENT_LENGTH` like a real HTTP server. File size limits are verified via config assertion rather than actual upload rejection.
- **Flask-CORS + test client**: CORS headers may not appear in test client responses. CORS configuration is verified via app config instead.
- **`json=None` in test client**: Sends `Content-Type: application/json` with no body, which Flask may return as `415` instead of `400`. Tests accept both.

## Fixtures (conftest.py)

- `app` / `client` — standard Flask test app with temp SQLite file DB
- `admin_user` / `engineer_user` / `viewer_user` — pre-created users (no nested app context)
- `logged_in_admin` / `logged_in_engineer` / `logged_in_viewer` — session-authenticated clients
- `integration_app` / `integration_client` / `all_users` — full-app fixtures for integration tests

### DetachedInstanceError Prevention

User fixtures create objects directly in the `app` fixture's existing app context — **never** with a nested `with app.app_context():` block. A nested context causes the SQLAlchemy session to detach objects when the inner block exits on `return`.
