# Phase 3: Parallel Internet Search — Claude Code Multi-Agent Prompt

## Mission

Implement Phase 3 of the orb-tool chat assistant: **parallel internet search**. This adds a "Check online for known issues?" opt-in feature to the existing LLM chat assistant. When the engineer clicks it, the app searches the web via Tavily (with Brave fallback), feeds results into Claude for synthesis alongside the manual-based answer, and streams the combined response.

**Read the full plan before starting:** `docs/phase-3-web-search-plan.md`
**Read the API research:** `docs/search-api-compare.md`

## Existing Architecture (DO NOT break)

- Flask app with app factory pattern in `src/app.py`
- Chat routes in `src/routes/chat.py` (SSE streaming via `text/event-stream`)
- Chat service in `src/services/chat_service.py` (`stream_chat_response()` is the main function)
- LLM service in `src/services/llm_service.py` (Anthropic Claude, factory pattern with `create_llm_service(app)` / `get_llm_service()`)
- Prompts in `src/prompts/manuals_assistant.py`
- Frontend in `templates/manuals/chat.html` (single-file with inline JS, SSE via ReadableStream)
- Config in `src/config.py` (env vars via `os.environ.get()`)
- Security in `src/security.py` (SecurityConfig class with rate limits)
- Offline support in `static/js/offline.js` and `static/js/storage.js`
- All routes require `@login_required` and `@limiter.limit()`

## Agent Tasks

### Agent 1: Backend Service + Config (branch: `agent/1-web-search-service`)

**Create `src/services/web_search_service.py`:**
- `WebSearchService` class with Tavily primary, Brave fallback
- `search_online(query: str, equipment: str | None, domains: list[str] | None) -> list[dict] | None`
  - Each result: `{"title": str, "url": str, "content": str, "score": float}`
  - Prepend equipment to query: `f"Caterpillar {equipment} {query}"` if equipment provided
  - Tavily: `search_depth="basic"`, `max_results` from config, `include_domains` from defaults or param, `timeout` from config
  - On Tavily failure/timeout: fall back to Brave REST API
  - On both fail: return None (graceful degradation)
- `_cache_get(query_hash: str) -> list[dict] | None` / `_cache_set(query_hash: str, results: list[dict])` — SQLite cache
  - Table: `web_search_cache(query_hash TEXT PRIMARY KEY, results_json TEXT, created_at REAL)`
  - TTL from config (default 86400 seconds / 24 hours)
  - Cache DB: `data/web_search_cache.db` (separate from main app DB)
- `create_web_search_service(app) -> WebSearchService | None` — factory, returns None if no TAVILY_API_KEY
- `get_web_search_service() -> WebSearchService | None` — module singleton

**Modify `src/config.py`:**
```python
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
BRAVE_SEARCH_API_KEY = os.environ.get("BRAVE_SEARCH_API_KEY", "")
WEB_SEARCH_TIMEOUT = int(os.environ.get("WEB_SEARCH_TIMEOUT", "10"))
WEB_SEARCH_CACHE_TTL = int(os.environ.get("WEB_SEARCH_CACHE_TTL", "86400"))
WEB_SEARCH_MAX_RESULTS = int(os.environ.get("WEB_SEARCH_MAX_RESULTS", "5"))
```

**Modify `src/app.py`:**
- After `create_llm_service(app)`, add:
```python
from services.web_search_service import create_web_search_service
create_web_search_service(app)
```

**Modify `.env.example`:**
- Add `TAVILY_API_KEY=`, `BRAVE_SEARCH_API_KEY=`, `WEB_SEARCH_TIMEOUT=10`, `WEB_SEARCH_CACHE_TTL=86400`, `WEB_SEARCH_MAX_RESULTS=5`

**Add `tavily-python` to `requirements.txt`.**

**Create `tests/test_web_search_service.py`:**
- Mock Tavily client and Brave HTTP responses
- Test: successful Tavily search returns formatted results
- Test: Tavily timeout triggers Brave fallback
- Test: Tavily exception triggers Brave fallback
- Test: both fail returns None
- Test: cache hit returns cached results without API call
- Test: cache miss calls API and stores result
- Test: expired cache entry triggers fresh API call
- Test: no API key → create_web_search_service returns None
- Test: equipment prefix is prepended to query
- Test: custom domains override defaults

Run `python -m pytest tests/test_web_search_service.py -v` and ensure all pass.

---

### Agent 2: Chat Route + Synthesis Service (branch: `agent/2-web-search-route`)

**Modify `src/routes/chat.py`:**
Add endpoint `POST /manuals/chat/api/web-search`:
```python
@chat_bp.route("/api/web-search", methods=["POST"])
@limiter.limit(SecurityConfig.RATE_LIMIT_AUTH_PER_MINUTE)
@login_required
def web_search():
    """Search the web and synthesize results with manual context."""
```
- Accept JSON: `{query: str, session_id: int, equipment: str | None}`
- Validate: query required, session must belong to current_user
- Get web search service — if None, return 503 with `{"error": "Web search not configured"}`
- Call `search_online(query, equipment)`
- If no results, return JSON `{"type": "error", "message": "No web results found"}`
- Load session history (same as `send_message`)
- Call `stream_web_synthesis(query, web_results, history, equipment)` from chat_service
- Stream SSE response (same pattern as `send_message`):
  - `{"type": "token", "content": "..."}` for each chunk
  - `{"type": "web_sources", "sources": [...]}` before streaming (so frontend can show sources)
  - `{"type": "done", "session_id": N}` when complete
- Save assistant response to session history
- CSRF exempt this endpoint (same as send_message if applicable)

**Modify `src/services/chat_service.py`:**
Add function:
```python
def stream_web_synthesis(
    query: str,
    web_results: list[dict],
    history: list[dict],
    equipment: str | None = None,
) -> Iterator[str]:
```
- Format web results into context string: `"Source: {title} ({url})\n{content}\n---\n"` for each result
- Build messages using a NEW web synthesis prompt (see below)
- Call `llm.stream()` with the web synthesis system prompt + context + history
- Wrap with `_normalize_citation_stream()` (reuse existing)
- Yield text deltas

**Modify `src/prompts/manuals_assistant.py`:**
Add web synthesis prompt:
```python
WEB_SYNTHESIS_SYSTEM_PROMPT = """You are a marine diesel engine troubleshooting assistant aboard a vessel.
The engineer asked a question and already received an answer from the indexed CAT engine manuals.
Now they've requested a web search for additional context from online sources.

Your job:
1. Summarize the most relevant findings from the web search results
2. Compare web findings with what the manual procedures say (if the conversation history includes manual-based answers)
3. Flag any discrepancies between manual procedures and field experience
4. Highlight practical tips, known issues, or gotchas from the field
5. Cite sources with [Source Title](URL) format for each claim

Keep it concise and actionable. The engineer is working on equipment right now.
If the web results don't add anything beyond what the manuals already cover, say so briefly.

## Web Search Results
{web_context}
"""
```

**Create `tests/test_web_search_route.py`:**
- Test: POST without auth returns 401/redirect
- Test: POST with auth, valid query returns SSE stream
- Test: POST with missing query returns 400
- Test: POST with invalid session_id returns 403/404
- Test: web search service unavailable returns 503
- Test: rate limiting applies to endpoint

Run `python -m pytest tests/test_web_search_route.py -v` and ensure all pass.

---

### Agent 3: Frontend UX (branch: `agent/3-web-search-frontend`)

**Modify `templates/manuals/chat.html`:**

1. **"Check online" chip injection:**
   - After every assistant response bubble finishes streaming (in the `done` event handler), inject a "Check online for known issues?" chip
   - Only show if: `navigator.onLine === true` AND the page has `data-web-search-enabled="true"` (set by backend Jinja if web search service is configured)
   - Style: distinct from suggestion chips — use a globe/search icon, different color (e.g., subtle blue outline instead of the default chip style)
   - The chip text should include the original query context, e.g., "Search online for known issues?"

2. **Click handler for "Check online" chip:**
   - POST to `/manuals/chat/api/web-search` with `{query: lastUserQuery, session_id: currentSessionId, equipment: selectedEquipment}`
   - Include CSRF token (same pattern as send_message)
   - Remove the chip after clicking (prevent double-click)
   - Show loading state: new bubble with "Searching the web..." and a spinner animation

3. **Web results bubble:**
   - Parse SSE stream (same ReadableStream pattern as regular messages)
   - On `web_sources` event: show a collapsible "Sources" section at the top of the bubble with linked source titles
   - On `token` events: append to bubble content (same markdown rendering as regular messages)
   - On `done` event: finalize bubble
   - **Distinct styling:** Different background color or left-border accent (e.g., blue-tinted) to visually distinguish from manual-based answers. Add a small "Web" badge/label in the bubble header.

4. **Error handling:**
   - Network error or 503: show inline message "Web search unavailable — showing manual results only" (no modal, no disruption)
   - Timeout: same message
   - Don't break the existing chat flow — errors in web search should never prevent normal chat usage

5. **Offline awareness:**
   - Listen to `offline` event — if user goes offline after chip is shown, hide/disable the chip
   - Listen to `online` event — if user comes back online, re-show the chip if it was hidden

**Backend template change in `src/routes/chat.py`:**
- In `chat_page()`, pass `web_search_enabled` to the template:
```python
from services.web_search_service import get_web_search_service
web_search_enabled = get_web_search_service() is not None
return render_template("manuals/chat.html", web_search_enabled=web_search_enabled)
```

**No new test files for this agent** (frontend JS tests are out of scope for Phase 3), but manually verify:
- Chip appears after assistant response when online
- Chip doesn't appear when offline
- Clicking chip triggers web search and shows results in distinct bubble
- Error states display correctly
- Regular chat flow is unaffected when web search is not configured

---

## Critical Constraints

1. **DO NOT break existing chat functionality.** The regular `send_message` flow must work exactly as before. Web search is purely additive.
2. **All new routes need `@login_required` and `@limiter.limit()`.**
3. **Follow existing patterns.** Look at `llm_service.py` for the factory/singleton pattern. Look at `send_message` in `chat.py` for the SSE streaming pattern. Look at `chat_service.py` for how prompts are built.
4. **Type hints on all Python functions.**
5. **Graceful degradation everywhere.** No API key? Service returns None. Tavily down? Brave fallback. Both down? Return None. Offline? Don't show the chip.
6. **Run the full test suite** (`python -m pytest`) before marking done. Don't break existing tests.
7. **Commit convention:** `feat:`, `fix:`, `refactor:`, `test:`, `chore:` prefixes. No AI mentions in commit messages.

## Merge Order

1. Agent 1 first (service + config — no dependencies)
2. Agent 2 second (route + synthesis — depends on Agent 1's service)
3. Agent 3 last (frontend — depends on Agent 2's route)

## Dependencies to Install

```bash
pip install tavily-python
```
Add `tavily-python` to `requirements.txt`.
