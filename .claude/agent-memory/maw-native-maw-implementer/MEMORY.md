# MAW Implementer Memory — orb-tool

## Flask-Limiter Pattern
- Move `Limiter` to module-level in `app.py` with `limiter = Limiter(key_func=get_remote_address)`
- Call `limiter.init_app(app)` inside `create_app()` factory
- Blueprints import directly: `from app import limiter`
- Flask-Limiter auto-disables when `TESTING=True`, so tests aren't affected by rate limits
- Config keys: `RATELIMIT_STORAGE_URI` and `RATELIMIT_DEFAULT` (set via `app.config.setdefault`)

## Exception Handling Pattern (established 2026-02-08)
- API routes: `IntegrityError` (409) → `OperationalError` (503) → `SQLAlchemyError` (500)
- manuals.py uses raw `sqlite3`, NOT SQLAlchemy — catch `sqlite3.Error`
- chat.py SSE generator: can't return HTTP status, yield error events instead
- Health check: keep generic `except Exception` — must always return JSON
- Never leak `str(e)` to client; log server-side with `logger.exception()`

## Project Test Notes
- 577 tests as of 2026-02-08
- Use venv from main repo: `source /Users/dp/Projects/orb-tool/venv/bin/activate`
- Run with: `python -m pytest tests/ -q`
- Python 3.14 in venv — `datetime` is immutable
- Tests that monkeypatch `raise Exception(...)` must match narrowed exception types
