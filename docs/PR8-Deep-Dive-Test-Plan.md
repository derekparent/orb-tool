# PR #8 — Deep-Dive + PDF Citations Test Plan

**Branch:** `feature/deep-dive-pdf-citations`
**PR:** [#8](https://github.com/derekparent/orb-tool/pull/8)
**Purpose:** Validate that Phase 2 deep-dive and clickable PDF citations work correctly in a live browser session.

---

## Prerequisites

- [ ] ANTHROPIC_API_KEY set in `.env`
- [ ] `data/engine_search.db` populated with indexed PDFs
- [ ] App running at http://localhost:5001
- [ ] Logged in (admin/admin123)
- [ ] On macOS (PDF open requires Preview)
- [ ] At least one PDF file physically present at the path stored in DB

Start the app:
```bash
cd /Users/dp/Projects/orb-tool/src && FLASK_APP=app:create_app ../venv/bin/flask run --port 5001
```

---

## Part 1: Unit Tests (Automated)

Run before any manual testing to confirm code correctness.

```bash
cd /Users/dp/Projects/orb-tool && ./venv/bin/python -m pytest tests/test_chat.py -v
```

| Check | Expected |
|-------|----------|
| All tests pass | 78/78 (0 failures) |
| New test classes present | `TestExtractCitations`, `TestShouldDeepDive`, `TestDeepDiveIntegration` |
| No regressions in existing tests | All pre-existing classes still pass |

---

## Part 2: Deep-Dive Detection (Phase 2)

These tests verify that follow-up questions load full page content instead of re-searching.

### T1: Basic deep-dive trigger — "tell me more"

| Step | Action |
|------|--------|
| 1 | Navigate to `/manuals/chat` |
| 2 | Type: `3516 valve lash adjustment` → Send |
| 3 | Wait for triage response with citations like `[kenr5403..., p.48]` |
| 4 | Type: `tell me more` → Send |

**Pass criteria:**
- [ ] Second response is noticeably different from the first (not a re-triage)
- [ ] Second response walks through procedure steps, not just page references
- [ ] Second response still has `[filename, p.XX]` citations
- [ ] Response mentions specific steps/content from the page (evidence of full text)

**Fail indicators:**
- Response looks like another triage ("I found 10 results...")
- Response says "I don't have full page content" or similar

### T2: Specific page reference — "page XX"

| Step | Action |
|------|--------|
| 1 | Start a new chat (click "New Chat") |
| 2 | Type: `C18 valve lash procedure` → Send |
| 3 | Note a specific page number from the citations |
| 4 | Type: `walk me through page [XX]` (use actual page from step 3) → Send |

**Pass criteria:**
- [ ] Response walks through content from that specific page
- [ ] Response has procedural detail (numbered steps, specs, warnings)
- [ ] Only content from the requested page appears (not all cited pages)

### T3: Vague deep-dive — "walk me through the procedure"

| Step | Action |
|------|--------|
| 1 | Start a new chat |
| 2 | Type: `3516 fuel rack actuator troubleshooting` → Send |
| 3 | Wait for triage with multiple citations |
| 4 | Type: `walk me through the procedure` → Send |

**Pass criteria:**
- [ ] Response covers content from cited pages (up to 3 pages)
- [ ] Response is a walkthrough, not a re-triage
- [ ] Citations in the walkthrough match the original cited pages

### T4: New topic breaks deep-dive — falls through to search

| Step | Action |
|------|--------|
| 1 | Continue from any chat with citations |
| 2 | Type: `what about oil filters?` → Send |

**Pass criteria:**
- [ ] Response is a fresh triage (new search results)
- [ ] Response does NOT reference pages from the previous topic
- [ ] Response cites different documents relevant to oil filters

### T5: Uncited page reference — falls through to search

| Step | Action |
|------|--------|
| 1 | Start a new chat |
| 2 | Type: `3516 valve lash` → Send |
| 3 | Note the cited page numbers |
| 4 | Type: `tell me about page 999` → Send |

**Pass criteria:**
- [ ] Response is a new search (page 999 not in citations, so no deep-dive)
- [ ] Does NOT error out or hang

### T6: First message — no deep-dive possible

| Step | Action |
|------|--------|
| 1 | Start a new chat |
| 2 | Type: `tell me more about the procedure` → Send |

**Pass criteria:**
- [ ] Response is a search-based triage (no history to dive into)
- [ ] May ask for clarification or show results

### T7: Deep-dive after chat with no citations

| Step | Action |
|------|--------|
| 1 | Start a new chat |
| 2 | Type: `hello` → Send |
| 3 | Type: `tell me more` → Send |

**Pass criteria:**
- [ ] No crash/error
- [ ] Response is a search or polite redirect

### T8: Deep-dive patterns — all trigger phrases

After getting a triage response with citations, test each trigger phrase (use "New Chat" + initial query before each):

| # | Follow-up phrase | Should trigger deep-dive? |
|---|-----------------|--------------------------|
| 8a | `tell me more` | Yes |
| 8b | `walk me through those pages` | Yes |
| 8c | `the procedure` | Yes |
| 8d | `go into more detail` | Yes |
| 8e | `explain those steps` | Yes |
| 8f | `break that down` | Yes |
| 8g | `page [XX]` (cited page) | Yes |
| 8h | `what about something else entirely` | No — new search |
| 8i | `how often should I change oil?` | No — new topic |

---

## Part 3: Clickable PDF Citations

These tests verify that citation links open the actual PDF at the correct page.

### T9: Citation click opens PDF

| Step | Action |
|------|--------|
| 1 | Get any response with citations (e.g. ask `3516 valve lash`) |
| 2 | Click a citation link like `[kenr5403..., p.48]` |

**Pass criteria:**
- [ ] PDF opens in macOS Preview
- [ ] PDF opens at (or near) the correct page number
- [ ] Status bar at bottom of chat shows "Opened [filename] at page [XX]"
- [ ] Status message auto-clears after ~4 seconds

### T10: Citation click — file not found

| Step | Action |
|------|--------|
| 1 | Requires a citation referencing a filename that's in the DB but whose PDF file has been moved/deleted |
| 2 | Click the citation |

**Pass criteria:**
- [ ] Status bar shows error message (not a crash)
- [ ] "Failed to open PDF" or similar

**Note:** This is hard to trigger naturally. Can be tested by temporarily renaming a PDF file.

### T11: Multiple citations — each opens correct page

| Step | Action |
|------|--------|
| 1 | Get a response with multiple citations to different pages |
| 2 | Click the first citation — note which PDF/page opens |
| 3 | Click a different citation — note which PDF/page opens |

**Pass criteria:**
- [ ] Each click opens the correct PDF at the correct page
- [ ] Second click doesn't re-open the first PDF's page

### T12: Citation links are not regular hyperlinks

| Step | Action |
|------|--------|
| 1 | Get a response with citations |
| 2 | Right-click a citation link |
| 3 | Check that it's `href="#"` (not a URL to the search page) |

**Pass criteria:**
- [ ] Citation `href` is `#` (not `/manuals/?q=...`)
- [ ] No page navigation occurs on click

---

## Part 4: `/manuals/open-by-name` Endpoint

Direct API testing of the new endpoint.

### T13: Valid filename + page

```bash
curl -b cookies.txt "http://localhost:5001/manuals/open-by-name?filename=kenr5403-00_3516-testing-%26-adjusting&page=48"
```

**Pass criteria:**
- [ ] Returns `{"status": "ok", "message": "Opened kenr5403... at page 48"}`
- [ ] PDF opens in Preview

### T14: Missing filename

```bash
curl -b cookies.txt "http://localhost:5001/manuals/open-by-name"
```

**Pass criteria:**
- [ ] Returns 400 with `"No filename specified"`

### T15: Unknown filename

```bash
curl -b cookies.txt "http://localhost:5001/manuals/open-by-name?filename=nonexistent-doc&page=1"
```

**Pass criteria:**
- [ ] Returns 404 with `"Document 'nonexistent-doc' not found in database"`

### T16: Invalid page number

```bash
curl -b cookies.txt "http://localhost:5001/manuals/open-by-name?filename=kenr5403-00_3516-testing-%26-adjusting&page=abc"
```

**Pass criteria:**
- [ ] Defaults to page 1 (no error)

### T17: Auth required

```bash
curl "http://localhost:5001/manuals/open-by-name?filename=test&page=1"
```

**Pass criteria:**
- [ ] Returns 302 redirect to login (not 200)

---

## Part 5: System Prompt Verification

### T18: Deep-dive mode prompt

| Step | Action |
|------|--------|
| 1 | Ask `3516 valve lash` → get triage |
| 2 | Follow up with `walk me through the procedure` |

**Pass criteria:**
- [ ] Response is a walkthrough, NOT "I can only provide snippets"
- [ ] Response does NOT say "I don't have tools" or "I can't load pages"
- [ ] Response does NOT say "open the manual to pages XX-YY for the full procedure"

### T19: Triage mode still works

| Step | Action |
|------|--------|
| 1 | Start new chat |
| 2 | Type: `C32 oil pressure low` → Send |

**Pass criteria:**
- [ ] Response triages results (groups by topic, suggests directions)
- [ ] Citations present in `[filename, p.XX]` format
- [ ] Response says something like "I found X results" with page groupings

---

## Part 6: Edge Cases

### T20: Equipment filter + deep-dive

| Step | Action |
|------|--------|
| 1 | Set Engine dropdown to "3516" |
| 2 | Type: `valve lash` → Send |
| 3 | Follow up: `tell me more` → Send |

**Pass criteria:**
- [ ] Deep-dive still works with equipment filter active
- [ ] Results are scoped to 3516

### T21: Rapid follow-ups

| Step | Action |
|------|--------|
| 1 | Get triage response |
| 2 | Quickly send `tell me more` |
| 3 | Wait for response |
| 4 | Send `tell me more` again |

**Pass criteria:**
- [ ] No crash or duplicate responses
- [ ] Second deep-dive may re-fetch same content or do a new search (both acceptable)

### T22: Long conversation (5+ turns)

| Step | Action |
|------|--------|
| 1 | Have a multi-turn conversation mixing triage and deep-dive |
| 2 | At turn 5+, check that responses are still coherent |

**Pass criteria:**
- [ ] No degradation in response quality
- [ ] Deep-dive still triggers when appropriate
- [ ] History trimming doesn't break citation detection

---

## Results Template

Copy this template and fill in results:

```
## Test Results — [DATE]

### Automated Tests
- pytest: XX/78 passed

### Manual Tests

| Test | Result | Notes |
|------|--------|-------|
| T1: Basic deep-dive | | |
| T2: Specific page ref | | |
| T3: Vague deep-dive | | |
| T4: New topic breaks | | |
| T5: Uncited page | | |
| T6: First message | | |
| T7: No citations in history | | |
| T8a-i: Trigger phrases | | |
| T9: Citation opens PDF | | |
| T10: File not found | | |
| T11: Multiple citations | | |
| T12: Not regular links | | |
| T13: API valid request | | |
| T14: API missing filename | | |
| T15: API unknown filename | | |
| T16: API invalid page | | |
| T17: API auth required | | |
| T18: Deep-dive prompt | | |
| T19: Triage still works | | |
| T20: Equipment filter | | |
| T21: Rapid follow-ups | | |
| T22: Long conversation | | |

### Summary
- Passed: XX / 22
- Failed: XX
- Skipped: XX

### Issues Found
1. ...

### Recommendations
1. ...
```
