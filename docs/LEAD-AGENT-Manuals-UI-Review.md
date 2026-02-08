# Lead Agent Brief: Manuals UI Review & Unified Design

**For:** Lead Claude orchestrating subagents
**Source:** Full code review of all 8 key files completed (routes, services, templates, CSS, prompts)
**Goal:** Produce a unified UI plan and search improvement recommendations

---

## What Was Already Done (This Session)

Read and analyzed all key files listed in the handoff:
- `src/routes/manuals.py` (199 lines) — 5 routes: search, card_detail, cards_list, stats, open_pdf
- `src/routes/chat.py` (186 lines) — 5 routes: chat_page, send_message (SSE), list/get/delete sessions
- `src/services/manuals_service.py` (1070 lines) — FTS5 search, ranking boosts, cards, authority, stats
- `src/services/chat_service.py` (345 lines) — RAG pipeline, query extraction, equipment detection
- `src/prompts/manuals_assistant.py` (185 lines) — System prompt, context formatters, message builder
- `templates/manuals/search.html` (670 lines) — Search UI with filters, results, cards
- `templates/manuals/chat.html` (743 lines) — Chat UI with SSE streaming, safe DOM rendering
- `templates/manuals/cards.html` (188 lines), `card.html` (228 lines), `stats.html` (100 lines)
- `templates/base.html` (62 lines) — Nav, mobile meta tags, CSRF
- `static/css/style.css` (2109 lines) — Full design system

---

## Architecture Summary (For Subagent Context)

### Two Disconnected UIs — This Is The Core Problem
1. **Search** (`/manuals/`) — Form-based FTS5 search with equipment/doc_type/system filters. Returns PDF page results + troubleshooting cards. Server-rendered via Jinja.
2. **Chat** (`/manuals/chat/`) — LLM conversational assistant. SSE streaming. Client-side JS with safe DOM rendering. Equipment dropdown. Session persistence.

They share `search_manuals()` as their search backend but have **no cross-linking**. You can't go from a search result to "ask the LLM about this" or from a chat citation back to the search result.

### Search Pipeline (Single Path — Already Unified Backend)
```
User query → prepare_search_query() [acronyms, synonyms, phrase expansion]
           → FTS5 MATCH with equipment/doc_type/system filters
           → BM25 ranking + boosts (phrase 1.5x, doc_type, tag-aware 20%/tag, authority)
           → Results: filename, page_num, equipment, doc_type, snippet, score
```

Chat uses same path via `get_context_for_llm()` → `search_manuals(boost_primary=True, limit=10)`.

### Chat RAG Pipeline
```
Conversational query → _extract_search_query() [strip stops, OR for >3 terms, synonyms]
                     → get_context_for_llm() → format_search_results() [XML context]
                     → build_messages() [system prompt + context + history + query]
                     → Claude Sonnet 4.5 SSE stream → safe DOM render
```

### Key Design Decisions (DON'T RE-DEBATE)
| Decision | Rationale |
|----------|-----------|
| Separate DBs (orb.db + engine_search.db) | Different lifecycle |
| Claude Sonnet 4.5 | Quality over cost at low volume |
| OR for >3 terms in chat queries | FTS5 AND too restrictive for OCR text |
| Search fixes go in chat_service.py only | Don't change manuals_service.py search behavior |
| Equipment dropdown wins, auto-detect fallback | Respect explicit UI choice |
| Re-search on follow-up (not page loading) | Simpler for v1 |

### CSS Design System
- Dark theme: `--bg-dark: #0d1117`, `--bg-card: #161b22`
- Accent: `--accent-primary: #f59e0b` (amber/maritime warning)
- Fonts: Work Sans (display), JetBrains Mono (mono)
- Spacing: `--space-xs` through `--space-xl` (0.25rem–2rem)
- Mobile breakpoint: `@media (max-width: 600px)`
- All inline CSS in templates (no separate manuals CSS file)
- Nav: sticky, blurred backdrop, horizontal links

---

## Four Review Areas (From Handoff)

### 1. Unified UI Design (HIGH PRIORITY)
**Current state:** Two pages, loosely linked via header buttons ("Search" ↔ "New Chat").

**Key observations from code review:**
- Search page is server-rendered (full page reload per search). Chat is SPA-like (JS handles everything client-side).
- Search has rich filters (equipment, doc_type, system checkboxes, authority boost). Chat only has equipment dropdown.
- Both pages use `max-width: 900px` container.
- Chat takes full viewport height (`height: calc(100vh - 60px)`). Search scrolls naturally.
- Nav highlights "Manuals" for both (`request.path.startswith('/manuals')`).

**Design options to evaluate:**
- **Option A: Tabs on single page** — `/manuals/` with Search|Chat tabs. Shared equipment filter. Chat panel slides in. Risk: complex JS state management.
- **Option B: "Ask about this" bridge** — Keep separate pages, add "Ask the assistant about these results" button on search that pre-populates chat with context. Add "View in search" links on chat citations. Lowest effort.
- **Option C: Split pane** — Search results on left, chat on right (desktop). Stack vertically on mobile. Most ambitious.

**Recommendation for subagent:** Option B first (bridge buttons), then evaluate if tabs are worth the complexity. Mobile phone screens can't do split pane.

### 2. Search Improvements (MEDIUM PRIORITY)
**Current state:** `_extract_search_query()` in chat_service.py strips stops and uses OR for >3 terms. `prepare_search_query()` in manuals_service.py expands acronyms/synonyms/phrases.

**Known issue:** "oil filter replacement" becomes `oil OR filter OR replacement` — matches any page with "oil" anywhere.

**Improvements to evaluate:**
- **Two-pass search:** AND first, fall back to OR if <3 results. Low effort, high impact.
- **Phrase quoting:** Detect multi-word noun phrases and quote them (`"oil filter"`). `prepare_search_query()` already adds phrase as OR expansion (line 197-199) but chat's `_extract_search_query()` doesn't.
- **Synonym pairs for chat:** `_QUERY_SYNONYMS` dict (line 65-72) only has 6 entries. Compare with `SYNONYM_EXPANSIONS` and `PHRASE_SYNONYMS` in manuals_service.py (lines 101-119) — much richer. Should chat inherit those?
- **Unify query prep?** The handoff says "search fixes go in chat_service.py only" but both functions do similar work. Consider having chat's `_extract_search_query()` produce clean keywords, then let `prepare_search_query()` handle all expansion.

### 3. Cards Integration (LOW PRIORITY)
**Current state:** Cards are searched alongside PDF pages on the search page (line 84 in manuals.py). Chat does NOT surface cards at all — `get_context_for_llm()` only calls `search_manuals()`, not `search_cards()`.

**Quick win:** Add card results to `get_context_for_llm()` so the LLM can reference troubleshooting cards when relevant.

### 4. Mobile UX (LOW PRIORITY)
**Current state from code review:**
- Mobile meta tags present (viewport, apple-mobile-web-app-capable)
- Search: 600px breakpoint stacks search box and filters vertically. Works.
- Chat: 600px breakpoint widens message bubbles to 95%. Input area comfortable (min-height 44px, auto-resize to 120px max).
- System filters: `<details>` collapsible — good for mobile.
- Nav: horizontal scroll with small gap. On a phone with 7 nav items (Dashboard, Fuel, Soundings, History, Manuals, New Hitch, user) this likely overflows. **No hamburger menu.** This is the main mobile issue.

---

## Subagent Task Breakdown

### Task 1: UI Bridge Design (frontend-design skill)
**Scope:** Design the "Ask about this" and "View in search" bridge between search and chat pages.
**Files to modify:** `templates/manuals/search.html`, `templates/manuals/chat.html`
**Constraint:** Mobile-first, dark theme, use existing CSS custom properties. No innerHTML.

### Task 2: Search Precision (chat_service.py only)
**Scope:** Implement two-pass search (AND first, OR fallback) and phrase detection in `_extract_search_query()`.
**Files to modify:** `src/services/chat_service.py`
**Constraint:** Don't change `manuals_service.py`. 21 existing tests must still pass. Add new tests.
**Test command:** `cd /Users/dp/Projects/orb-tool && venv/bin/python -m pytest tests/ -x -q`

### Task 3: Cards in Chat Context
**Scope:** Add card results to `get_context_for_llm()` output so LLM can reference them.
**Files to modify:** `src/services/manuals_service.py` (get_context_for_llm), `src/prompts/manuals_assistant.py` (format for LLM)
**Constraint:** Cards should appear as a separate section in the XML context, not mixed with PDF results.

### Task 4: Citation Consistency
**Scope:** Review system prompt citation rules and tighten format enforcement.
**Files to modify:** `src/prompts/manuals_assistant.py`
**Constraint:** Must always be `[Document Name, p.XX]` format. Add few-shot examples to prompt.

---

## Test & Verification

- **21 existing tests** must pass: `venv/bin/python -m pytest tests/ -x -q`
- Python venv at `venv/bin/python` (NOT system python)
- Flask app: `cd src && FLASK_APP=app:create_app ../venv/bin/flask run --port 5001`
- Login: admin / admin123
- DB is pre-built (5,736 pages, 62 PDFs) — DO NOT re-index
- Security hook blocks `innerHTML` — use safe DOM APIs only

---

## Files Quick Reference

| File | Lines | What |
|------|-------|------|
| `src/routes/manuals.py` | 199 | Search + card + stats routes |
| `src/routes/chat.py` | 186 | Chat page + SSE + session CRUD |
| `src/services/manuals_service.py` | 1070 | FTS5 search, ranking, cards, authority |
| `src/services/chat_service.py` | 345 | RAG pipeline, query extraction |
| `src/prompts/manuals_assistant.py` | 185 | System prompt, context formatters |
| `templates/manuals/search.html` | 670 | Search UI (inline CSS+JS) |
| `templates/manuals/chat.html` | 743 | Chat UI (inline CSS+JS, SSE, safe DOM) |
| `templates/manuals/cards.html` | 188 | Card list with filters |
| `templates/manuals/card.html` | 228 | Card detail with sources |
| `templates/base.html` | 62 | Nav, CSRF meta, scripts |
| `static/css/style.css` | 2109 | Global design system |
