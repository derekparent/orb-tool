# Handoff: Manuals & Search Feature — UI Review + Improvement Plan

**For:** Next Claude session
**Goal:** Review the manuals search and LLM chat features, help plan a unified UI, and recommend improvements
**Project:** orb-tool (Flask maritime fuel tracking + CAT engine manuals search)
**Repo:** `git@github.com:derekparent/orb-tool.git` (main branch)

---

## What This App Does

Oil Record Book tool for a marine vessel with 4 CAT engines: 3516 (Main), C18 (GenSet), C32 (Thruster), C4.4 (Emergency). The manuals feature lets engineers search 62 indexed PDFs (5,736 pages) and ask an LLM questions about engine procedures, troubleshooting, specs, and intervals.

**Key constraint:** Mobile-first (used on phones aboard ship). Two-crew rotation — Blue crew uses the app, Gold crew uses Excel.

---

## Current Manuals Feature Architecture

### Two Separate Interfaces (The Problem)

The manuals feature currently has **two separate UIs** that overlap:

1. **Search Page** (`/manuals/`) — Traditional FTS5 keyword search with filters
2. **Chat Page** (`/manuals/chat/`) — LLM-powered conversational assistant

These share the same search backend (`search_manuals()`) but have separate UIs, separate navigation, and no deep linking between them. An engineer searching for "valve lash" on the search page can't seamlessly ask the LLM to explain the results, and an LLM response can't link back to the search page to show the original documents.

### Routes (10 total)

| Route | Method | What It Does |
|-------|--------|-------------|
| `/manuals/` | GET | Search page — FTS5 search with equipment/doc_type/system filters |
| `/manuals/card/<id>` | GET | Troubleshooting card detail |
| `/manuals/cards` | GET | List all troubleshooting cards |
| `/manuals/stats` | GET | Index statistics (page/file/card counts) |
| `/manuals/open` | GET | Open PDF at specific page (macOS only, not useful aboard) |
| `/manuals/chat/` | GET | LLM chat interface |
| `/manuals/chat/api/message` | POST | SSE streaming chat endpoint |
| `/manuals/chat/api/sessions` | GET | List user's chat sessions |
| `/manuals/chat/api/sessions/<id>` | GET | Get specific chat session |
| `/manuals/chat/api/sessions/<id>` | DELETE | Delete chat session |

### Templates (5 in `templates/manuals/`)

| Template | Description |
|----------|-------------|
| `search.html` | Search form + results list. Filters: equipment, doc_type, system tags, authority boost. Results show filename, page number, snippet with highlights. |
| `chat.html` | Chat interface with equipment dropdown, message history, SSE streaming, markdown rendering. Example query buttons. Session management (new chat, load previous). |
| `stats.html` | Dashboard showing total PDFs, indexed pages, card count. |
| `cards.html` | Card list with equipment/subsystem filter dropdowns. |
| `card.html` | Individual troubleshooting card with steps and linked source pages. |

### Navigation Flow

```
Base Nav: Dashboard | Fuel | Soundings | History | [Manuals] | New Hitch

/manuals/ (Search) ←→ /manuals/chat/ (Chat)
     ↓                        ↓
/manuals/card/<id>      Chat sessions
     ↓
/manuals/cards
/manuals/stats
```

The "Manuals" nav link goes to `/manuals/` (search). Chat is a separate sub-page. There's a "Search" link in the chat header and vice versa, but they're separate experiences.

### JavaScript

All manuals JS is **inline in templates** (no separate JS files):
- `search.html`: `openPdf()` function
- `chat.html`: SSE streaming, markdown rendering, session management, auto-resize textarea
- `card.html`: `openPdf()` function

---

## Service Layer Architecture

### Search Pipeline (`manuals_service.py`)

```
User Query
    ↓
prepare_search_query()  ← Expands acronyms, synonyms, spelling variants
    ↓
FTS5 Search (pages_fts) ← Porter stemmer, unicode61 tokenizer
    ↓
Ranking Boosts:
  • Phrase match boost (1.5x for exact phrase in content)
  • Doc-type boost (testing=1.4, disassembly=1.3 for procedural queries)
  • Tag-aware boost (20% per matching subsystem tag, max 60%)
  • Authority boost (primary=1.5x, secondary=1.0, mention=0.7)
    ↓
Results: filename, page_num, equipment, doc_type, snippet, score
```

**Key functions:**
- `search_manuals(query, equipment, doc_type, systems, limit, boost_primary)` — main search
- `get_context_for_llm(query, equipment, limit=10)` — search wrapper for chat
- `get_pages_content(filename, page_nums)` — fetch full page text (used for deep-dive)
- `search_cards(query, equipment, limit)` — troubleshooting card search
- `get_index_stats()` — DB health/stats

### Chat/RAG Pipeline (`chat_service.py`)

```
Conversational Query ("How do I adjust valve lash on the C18?")
    ↓
_extract_search_query()  ← Strips stop words, adds synonyms
    → "adjust OR valve OR lash OR C18 OR clearance"
    ↓
detect_equipment()  ← Auto-detects "C18" from query
    ↓
get_context_for_llm()  ← Returns top 10 search results as snippets
    ↓
format_search_results()  ← Wraps in <search_results> XML for LLM
    ↓
build_messages()  ← System prompt + context + history + query
    ↓
llm_service.stream()  ← Claude Sonnet 4.5, SSE streaming
    ↓
Response with citations to [Document, p.XX]
```

**Token budgets:** Context=4000, History=3000, Max turns=10

### LLM Service (`llm_service.py`)

- Model: `claude-sonnet-4-5-20250929`
- Timeout: 30s, Max retries: 3 (exponential backoff on rate limits)
- Graceful degradation: returns `None` if no API key → chat page shows FTS5 fallback

### System Prompt (`prompts/manuals_assistant.py`)

- Role: collaborative marine engineering assistant (not an oracle)
- Two-phase: triage search results → deep-dive on selected pages
- Citation rules: `[Document Name, p.XX]` format, never hallucinate specs
- Scope rules: decline out-of-scope questions, ask clarifying questions
- Recent fix: explicit "you do NOT have tools" instruction (commit 6730478)

### Tagging System

- `auto_tagger.py` — scans documents for keywords, suggests/applies subsystem tags
- `tagging_schema.py` — creates `documents`, `tags`, `document_tags` junction tables
- Tags: Fuel System, Air Intake, Cooling, Lubrication, Exhaust, Starting, Electrical/Controls, Cylinder Block, Cylinder Head/Valvetrain, Safety/Alarms, General/Maintenance
- Used for tag-aware search boosting (20% per matching tag)

---

## Database Schema (`data/engine_search.db`)

| Table | Purpose | Row Count |
|-------|---------|-----------|
| `pages` | PDF page content | 5,736 |
| `pages_fts` | FTS5 index on content | 5,736 |
| `documents` | Distinct documents | ~62 |
| `tags` | Subsystem tag definitions | ~11 |
| `document_tags` | Document↔tag junction | varies |
| `cards` | Troubleshooting cards | varies |
| `cards_fts` | FTS5 on card title/steps | varies |
| `doc_authority` | Primary/secondary authority levels | varies |
| `search_log` | Query analytics | grows |

---

## Test Results (21/21 PASS)

Full results: `docs/LLM-Test-Results-2026-02-07.md`

### What's Working Well
- **Zero hallucinated specs** across all 21 tests — never invented torque, clearance, pressure, or intervals
- **Excellent troubleshooting triage** — structured primary/secondary diagnostic flows
- **Transparent about misses** — says "I didn't find..." instead of making things up
- **Good equipment awareness** — references correct manual numbers (KENR, SENR, RENR, SEBU)
- **Scope enforcement** — declined "How do I cook pasta?" correctly
- **Clarification behavior** — asked for engine model and symptoms when ambiguous

### Known Issues (Prioritized)

| Priority | Issue | Details |
|----------|-------|---------|
| FIXED | Multi-turn tool hallucination | LLM generated fake `<search>` XML on follow-ups. Fixed in commit 6730478. |
| MEDIUM | Search precision | OR queries too broad for compound terms. "oil filter replacement" matches any page with "oil". |
| LOW | Citation inconsistency | Sometimes `[Doc, p.XX]` brackets, sometimes inline "Page 44 (senr9773)". |
| LOW | No deep linking | Chat can't link to search results; search can't hand off to chat. |

### Search Improvement Recommendations

| Improvement | Impact | Effort |
|-------------|--------|--------|
| FTS5 phrase matching (`"oil filter"`) | High | Low |
| Synonym expansion (lash↔clearance, height↔protrusion) | High | Medium |
| Two-pass search (AND first, OR fallback) | Medium | Low |
| Section-level indexing (by headings, not just page text) | High | High |
| Subsystem tag boost from query intent | Medium | Medium |
| Vector re-ranking after FTS5 | High | High |

---

## What To Review & Plan

### 1. Unified UI Design
The search page and chat page are currently disconnected. Consider:
- Should they be one page with a toggle/tabs?
- Should search results have a "Ask about this" button that opens chat with context?
- Should chat responses have "View in search" links?
- How does this work on a phone screen?

### 2. Search Improvements
Review `_extract_search_query()` in `chat_service.py` and `prepare_search_query()` in `manuals_service.py`:
- Where to add phrase matching?
- What synonym pairs matter most for marine engineers?
- Should the two query prep functions be unified?

### 3. Cards Integration
Troubleshooting cards (`/manuals/cards`) are a separate feature with their own search. Should they:
- Appear in main search results alongside PDF pages?
- Be surfaced by the LLM when relevant?
- Have their own section in a unified UI?

### 4. Mobile UX
This is used on phones aboard ship. Review:
- Are filter controls usable on small screens?
- Is the chat input comfortable to type on mobile?
- Should results be more compact?

---

## Key Files to Read

| File | What It Contains |
|------|-----------------|
| `src/routes/manuals.py` | Search routes, card routes, stats |
| `src/routes/chat.py` | Chat routes, SSE streaming |
| `src/services/manuals_service.py` | Core search logic, ranking, cards |
| `src/services/chat_service.py` | RAG pipeline, query extraction |
| `src/prompts/manuals_assistant.py` | System prompt, citation rules |
| `templates/manuals/search.html` | Search UI |
| `templates/manuals/chat.html` | Chat UI |
| `templates/base.html` | Navigation, mobile layout |
| `docs/LLM-Test-Results-2026-02-07.md` | Full test results with per-query notes |
| `docs/LLM-Manuals-Assistant-Test-Plan.md` | Test plan (21 queries, pass criteria) |
| `docs/subsystem-tagging-guide.md` | Equipment, systems, acronyms reference |
| `data/keywords.json` | Keyword dictionary for auto-tagging |

## Decisions Already Made (Don't Re-Debate)

| Question | Decision | Rationale |
|----------|----------|-----------|
| Separate apps vs one? | One app (orb-tool) | Single deployment, shared auth/nav |
| Database coupling? | Separate DBs (orb.db + engine_search.db) | Different lifecycle |
| LLM model | Claude Sonnet 4.5 | Quality over cost at low volume |
| Chat query→FTS5 | Strip stops, OR for >3 terms | FTS5 AND too restrictive |
| Search fixes location | chat_service.py only | Don't change manuals_service.py |
| Equipment filter priority | Dropdown wins, auto-detect fallback | Respect explicit UI choice |
| Follow-up approach | Re-search on follow-up (v1) | Simpler than page loading |

## Environment Setup

```bash
# App is already running on port 5001 (check first)
cd /Users/dp/Projects/orb-tool/src && FLASK_APP=app:create_app ../venv/bin/flask run --port 5001

# Login: admin / admin123
# Navigate to: http://localhost:5001/manuals/ (search) or /manuals/chat/ (chat)

# DB is populated — DO NOT re-index unless PDFs change
# data/engine_search.db: 5,736 pages from 62 PDFs

# PDFs live in sibling directory: /Users/dp/Projects/engine_tool/
# Equipment folders: Main_Engine_3516/, GenSet_C18/, Thruster_C32/, Emergency_C4.4/
```
