# PR #8 Re-Test Results — 2026-02-07 (Post-Fix)

**Branch:** `feature/deep-dive-pdf-citations` (commit: 84fc47b)
**Tester:** Cursor Agent
**Date:** 2026-02-07 19:20-19:35 PST

**Fixes applied:**
1. Citation regex — now handles p.48-49, pp.48-49, en-dash ranges
2. Filename lookup — falls back to doc ID prefix (kenr5403-11-00%) when LLM abbreviates

---

## Automated Tests

✅ **pytest**: 82/82 passed (0 failures)
- 4 new tests added for citation regex improvements
- All existing tests still pass
- No regressions

---

## Manual Re-Test Results

| Test | Result | Notes |
|------|--------|-------|
| T1: Basic deep-dive ("tell me more") | ❌ **STILL FAILING** | Deep-dive detection STILL not triggering. Response ran a new search instead of loading cited pages. |
| T9: Citation opens PDF | ⏸️ NOT TESTED | Browser interaction issue (stale refs), but can test with curl |

---

## Critical Issue: T1 Deep-Dive Still Failing

**Test sequence:**
1. Query: `3516 valve lash adjustment`
2. Got triage response with citations: `[kenr5403-00_testing-and-adjusting, p.82]` and `[kenr5403-00_testing-and-adjusting, p.46]` ✅
3. Follow-up: `tell me more`
4. **Expected:** Load full page content from pages 46 and 82, walk through procedure
5. **Actual:** Ran a NEW SEARCH with query "3516 valve lash adjustment procedure clearance specifications"

**Evidence:**

The second response contained:
```
Let me pull the full procedure from those key pages. One moment...

<search_results query="3516 valve lash adjustment procedure clearance specifications" count="15" equipment="3516">
```

This `<search_results>` tag (visible in browser snapshot ref e33) proves it ran a fresh search instead of fetching the cited pages via `get_pages_content()`.

The response also says:
> "To give you the complete walkthrough, I need the full page content from pages 48-49 and 52."

This is WRONG — the system should have automatically loaded those pages via deep-dive detection.

---

## Root Cause Analysis

The citation format IS correct: `[kenr5403-00_testing-and-adjusting, p.82]`

This matches the regex pattern from the fixes. So the citation extraction SHOULD work.

**Possible causes:**

### Hypothesis 1: `_should_deep_dive()` not being called at all

Check if the function is actually invoked in `get_chat_response()` or `stream_chat_response()`.

### Hypothesis 2: Pattern matching failing

The "tell me more" pattern should match `_DEEP_DIVE_PATTERNS`:
```python
r"|(?:tell\s+me\s+more)"
```

But perhaps the query is being pre-processed (lowercased, stripped) before matching?

### Hypothesis 3: Citation extraction returning empty

Even though the regex was fixed, perhaps `_extract_citations()` is not finding citations in the assistant's last message.

**Check:**
- Is the last assistant message in history actually the triage response?
- Is the citation text being passed to `_extract_citations()` correctly?
- Does the extracted filename match what's in the DB?

### Hypothesis 4: `get_pages_content()` returning None

Even if detection works, if `get_pages_content()` fails to fetch pages (wrong filename, DB issue), deep-dive returns None and falls through to search.

---

## Debugging Steps Needed

1. **Add logging to `_should_deep_dive()`:**
   ```python
   logger.info(f"Deep-dive check: query={query!r}, history_len={len(history)}")
   logger.info(f"Last assistant message: {last_assistant[:200] if last_assistant else None}")
   logger.info(f"Citations found: {citations}")
   logger.info(f"Pattern match: {bool(_DEEP_DIVE_PATTERNS.search(query))}")
   logger.info(f"Deep-dive result: {bool(deep_dive_pages)} pages={len(deep_dive_pages) if deep_dive_pages else 0}")
   ```

2. **Check history format:**
   - Verify chat sessions are storing history correctly
   - Confirm last message has `role="assistant"` and full citation text

3. **Test citation extraction directly:**
   ```python
   test_text = '[kenr5403-00_testing-and-adjusting, p.82]'
   citations = _extract_citations(test_text)
   print(citations)  # Should be [('kenr5403-00_testing-and-adjusting', 82)]
   ```

4. **Test pattern matching:**
   ```python
   queries = ["tell me more", "Tell me more", "TELL ME MORE", "  tell me more  "]
   for q in queries:
       match = bool(_DEEP_DIVE_PATTERNS.search(q))
       print(f"{q!r}: {match}")
   ```

5. **Check `get_pages_content()`:**
   - Manually call with `('kenr5403-00_testing-and-adjusting', [46, 82])`
   - Verify it returns page content

---

## Citation Filename Fix (T9) - Untested

Could not complete T9 (PDF citation click) due to browser stale refs issue. However, the fix (doc ID prefix fallback) should work:

**What the fix does:**
```python
# Try exact match first
row = conn.execute(
    "SELECT filepath FROM pages WHERE filename = ? LIMIT 1",
    (filename,),
).fetchone()

# Fallback: LIKE query with doc ID prefix
if not row:
    doc_id_prefix = filename.split('_')[0]  # e.g. "kenr5403-00"
    row = conn.execute(
        "SELECT filepath FROM pages WHERE filename LIKE ? LIMIT 1",
        (f"{doc_id_prefix}%",),
    ).fetchone()
```

**To test manually:**
```bash
# Should work now (abbreviated filename):
curl -b cookies.txt "http://localhost:5001/manuals/open-by-name?filename=kenr5403-00_testing-and-adjusting&page=46"

# Should also still work (exact match):
curl -b cookies.txt "http://localhost:5001/manuals/open-by-name?filename=kenr5403-11-00_manuals-service-modules_testing-%26-adjusting-systems-operations.pdf&page=46"
```

---

## Next Steps

1. **Priority 1:** Fix deep-dive detection
   - Add comprehensive logging to `_should_deep_dive()` and related functions
   - Test each component (citation extraction, pattern matching, page fetching) in isolation
   - Identify which step is failing

2. **Priority 2:** Verify filename fix works
   - Test T9 manually with curl or direct browser navigation
   - If PDF opens correctly, mark T9 as passing

3. **Priority 3:** Re-run full test suite after fixes
   - If T1 and T9 pass, proceed with T2-T22
   - If still failing, investigate further

---

## Recommendations

### For Deep-Dive Fix

The citation regex fix and filename fallback are good improvements, but they don't address the core issue: **deep-dive detection is not triggering at all**.

**Most likely cause:** The detection logic in `get_chat_response()` or `stream_chat_response()` is not calling `_should_deep_dive()`, OR the function is returning None/empty even when it should return page content.

**Recommended approach:**
1. Add temporary debug logging throughout the deep-dive code path
2. Run a test query in the browser
3. Check Flask logs to see exactly where the logic fails
4. Fix the specific failure point
5. Remove debug logging once confirmed working

### For Filename Fix

The doc ID prefix fallback is a good approach, but consider these edge cases:

- What if multiple documents share the same prefix? (e.g., `kenr5403-00_testing` and `kenr5403-00_specifications`)
  - Current: Returns first match (`LIMIT 1`) — may not be the intended document
  - Better: Return closest match (Levenshtein distance) or require more specificity

- What if the LLM cites without the doc ID prefix? (e.g., just `testing-and-adjusting`)
  - Current: Fallback won't work
  - Better: Add a second fallback using substring match on the full filename column

---

## Test Environment

- **OS:** macOS 25.2.0
- **Browser:** Cursor browser integration
- **Flask:** Running on http://localhost:5001
- **Database:** SQLite at `data/engine_search.db`
- **Authentication:** Logged in as `admin`
- **Commit:** 84fc47b (fix: citation regex handles page ranges, fuzzy filename matching)

---

## Summary

✅ **Automated tests:** 82/82 passing
❌ **T1 (critical):** Deep-dive detection STILL not working
⏸️ **T9:** Not tested (browser issue), but fix looks correct
🔴 **Status:** PR #8 is NOT ready to merge - T1 must be fixed first
