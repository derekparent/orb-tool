# Prompt: Execute PR #8 Deep-Dive + PDF Citations Test Plan

**For:** Testing agent in Cursor
**Context:** orb-tool project, Flask app, LLM-powered manuals chat at `/manuals/chat`
**Branch:** `feature/deep-dive-pdf-citations`
**PR:** https://github.com/derekparent/orb-tool/pull/8

---

## Background

PR #8 adds two features to the manuals chat assistant:

1. **Phase 2 deep-dive:** When a user follows up on cited pages (e.g. "tell me more", "walk me through the procedure", "page 48"), the system now fetches full OCR page content instead of re-running search. This gives the LLM full procedure text to walk through collaboratively.

2. **Clickable PDF citations:** Citation links in chat responses (`[filename, p.48]`) now open the actual PDF in macOS Preview at the cited page, instead of linking to the search page.

### What changed (5 files)

| File | What |
|------|------|
| `src/services/chat_service.py` | `_extract_citations()`, `_should_deep_dive()` — detects when to load full pages; both `get_chat_response()` and `stream_chat_response()` now route through deep-dive before falling back to search |
| `src/prompts/manuals_assistant.py` | System prompt updated for dual-mode context (triage vs deep-dive) |
| `src/routes/manuals.py` | New `/manuals/open-by-name` endpoint — resolves filename → filepath from DB, opens PDF |
| `templates/manuals/chat.html` | `formatInline()` changed: citations click → `openPdfByName(filename, page)` fetch call instead of search href |
| `tests/test_chat.py` | 15 new tests in `TestExtractCitations`, `TestShouldDeepDive`, `TestDeepDiveIntegration` |

### How deep-dive detection works

Both conditions must be true:
1. The **last assistant message** in history contains `[filename, p.XX]` citations
2. The **user's query** matches a deep-dive pattern: "tell me more", "the procedure", "walk me through", "page 48", "go into detail", "explain those steps", "break that down", etc.

If the user says "page 48" specifically, only that page is fetched (if it's in the citations). Vague phrases like "tell me more" fetch all cited pages, capped at 3.

If detection fails (no citations, no pattern match, uncited page number), the system falls through to normal search — no errors, just a fresh triage.

---

## Your Task

Execute the test plan at `docs/PR8-Deep-Dive-Test-Plan.md` and record results.

### Step 1: Setup

```bash
cd /Users/dp/Projects/orb-tool
git checkout feature/deep-dive-pdf-citations
```

Verify the app starts:
```bash
cd src && FLASK_APP=app:create_app ../venv/bin/flask run --port 5001
```

The app serves at http://localhost:5001. Login: `admin` / `admin123`.

### Step 2: Run automated tests

```bash
cd /Users/dp/Projects/orb-tool && ./venv/bin/python -m pytest tests/test_chat.py -v
```

Expected: 78/78 passing, 0 failures.

### Step 3: Run manual tests

Open http://localhost:5001/manuals/chat in a browser. Execute tests T1 through T22 from the test plan.

**Key tests to focus on:**

**Deep-dive (most important):**
- **T1:** Ask `3516 valve lash adjustment`, then follow up `tell me more` — should get a walkthrough, NOT another triage
- **T2:** After getting citations, ask `walk me through page [XX]` using an actual cited page — should get specific page content
- **T4:** After triage, ask a completely new topic like `what about oil filters?` — should re-search, NOT deep-dive

**PDF citations:**
- **T9:** Click any `[filename, p.XX]` citation link in a response — PDF should open in Preview at that page
- **T12:** Verify citations are `href="#"` (click handlers), not links to search page

**Endpoint:**
- **T14/T15:** `curl` the `/manuals/open-by-name` endpoint with missing/unknown filenames — should return proper error codes

### Step 4: Record results

Create `docs/PR8-Test-Results-[DATE].md` using the results template at the bottom of the test plan. Include:

1. Automated test count (XX/78)
2. Each manual test: pass/fail + brief notes
3. Summary: total passed/failed/skipped
4. Issues found (if any) with specifics:
   - What was the query?
   - What was the expected behavior?
   - What actually happened?
   - Screenshot or response text if possible
5. Recommendations for fixes if issues found

### Step 5: If issues are found

For each failing test, check:

1. **Is `_should_deep_dive()` returning correctly?** Add a temporary log:
   ```python
   # In chat_service.py, inside get_chat_response() after the deep_dive_pages line:
   logger.info(f"Deep-dive result: {bool(deep_dive_pages)}, query: {query!r}")
   ```
   Then check the Flask console output.

2. **Is the system prompt correct?** The LLM should NOT say things like:
   - "I can only provide snippets"
   - "I don't have full page content"
   - "Open the manual to pages XX-YY"
   If it does, the deep-dive didn't trigger — check detection logic.

3. **Is the citation format matching?** The regex expects `[filename, p.XX]`. If the LLM outputs `(filename, p.XX)` or `filename, p.XX` (no brackets), the detection won't work. Check the system prompt's citation format instructions.

4. **PDF not opening?** Check:
   - Is the file physically present at the path in the DB?
   - Is the filename in the DB matching what the LLM cited?
   - Check Flask console for the `/manuals/open-by-name` request and response

---

## What to verify at each step

### For deep-dive responses, look for:
- Procedural detail (numbered steps, tools needed, safety warnings)
- Specific values (torque specs, clearances, pressures) quoted from page content
- The response feeling like it's "reading" the page, not just triaging snippets
- Citations still present (deep-dive responses should still cite sources)

### For triage responses (when deep-dive should NOT trigger), look for:
- Result count ("I found X results across Y documents")
- Topic grouping ("Pages 48-49 cover the adjustment, pages 52-54 cover specs")
- Suggestions for next steps ("Which area would you like to explore?")

### For citation clicks, look for:
- PDF opens in Preview (not a browser tab)
- Correct page (or close — Preview sometimes offsets by 1-2 for front matter)
- Status toast appears in the chat status bar at the bottom
- Toast auto-clears after ~4 seconds

---

## Reference files

| File | Description |
|------|-------------|
| `docs/PR8-Deep-Dive-Test-Plan.md` | Full test plan with all 22 tests |
| `src/services/chat_service.py` | Deep-dive detection logic (lines 125-240) |
| `src/prompts/manuals_assistant.py` | System prompt with dual-mode context format |
| `src/routes/manuals.py` | `/manuals/open-by-name` endpoint |
| `templates/manuals/chat.html` | Citation click handler (`openPdfByName`) |
| `tests/test_chat.py` | Automated tests (78 total, 15 new) |
| `docs/subsystem-tagging-guide.md` | Equipment/subsystem reference for queries |
