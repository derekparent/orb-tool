# LLM Manuals Assistant — Test Results

**Date:** 2026-02-07
**Executor:** Claude (Cursor agent)
**App:** http://localhost:5001/manuals/chat
**DB:** 62 PDFs indexed, 5,736 pages, 11.2M chars

---

## Summary

**11 of 21 tests executed** (session context limit reached before completion)
**11 of 11 PASS on single-turn** (LLM behavior)
**2 of 2 FAIL on multi-turn follow-up** (hallucinated tool calls)

Categories C (Intervals), D (Specs), and E (Edge Cases) were **not tested** — should be run in a follow-up session.

**2026-02-08 update:** Code fixes applied (multi-turn hallucination, synonym expansion, citation example). C1-E3 still require manual browser execution.

---

## Execution Checklist

```
Category A (Procedures):      A1 [x] A2 [x] A3 [x] A4 [x] A5 [x]
Category B (Troubleshooting):  B1 [x] B2 [x] B3 [x] B4 [x] B5 [x]
Category C (Intervals):       C1 [ ] C2 [ ] C3 [ ] C4 [ ]
Category D (Specs):           D1 [ ] D2 [ ] D3 [ ] D4 [ ]
Edge Cases:                   E1 [ ] E2 [ ] E3 [ ]
```

---

## Detailed Results

### Category A: Procedures

| # | Query | Single-Turn | Follow-Up | Notes |
|---|-------|:-----------:|:---------:|-------|
| A1 | Valve lash on C18 | PASS | — | 10 RAG results, triaged by manual type (D&A, T&A, troubleshooting), asked inlet vs exhaust. No hallucinated clearance specs. |
| A2 | 3516 fuel rack actuator troubleshooting | PASS | — | 10 results, triaged by manual (KENR5403, KENR6055, KENR5404) with specific pages. Asked about symptoms, fault codes, goal. |
| A3 | JWAC / aftercooler cleaning | PASS | **FAIL** | Initial: 10 results, identified safety-critical caustic warning on p.119 of sebu7822. Follow-up: **hallucinated `<get_page_content>` and `<search>` XML tool calls** that don't exist. Raw XML rendered in chat. |
| A4 | Injector height on C32 | PASS | **FAIL** | Initial: found injector-related content but not adjustment procedure. Honestly said mismatch, suggested "injector protrusion" as correct term. Follow-up: same **fake `<search>` tool call hallucination**. |
| A5 | Replacing oil filter | PASS | — | RAG returned oil system pages (pressure, levels) not filter replacement specifically. No hallucination, asked for engine model. Search precision issue. |

### Category B: Troubleshooting

| # | Query | Single-Turn | Follow-Up | Notes |
|---|-------|:-----------:|:---------:|-------|
| B1 | Cranks but won't fire | PASS | — | Structured 3-direction diagnostic: fuel priming (pp.135-136), electrical/sensor checks (RENR9303 p.37, RENR7914 schematics), systematic troubleshooting (SENR9646 p.38). Mentioned 30-second cranking limit from context. |
| B2 | Low oil pressure alarm | PASS | — | Triaged primary/secondary: oil level (senr9773 p.44), bypass valves (senr9646 p.76), temp effects (p.46), fuel dilution (p.48), bearing wear (kenr6846 p.64). No invented pressure thresholds. |
| B3 | Main engine overheating (3516) | PASS | — | RAG didn't return cooling troubleshooting content directly. Transparent about mismatch. Suggested where to look in physical manuals, asked relevant diagnostic questions (actual temp, coolant level, raw water flow, load condition). No hallucinated temperature thresholds. |
| B4 | ECU fault codes for C18 | PASS | — | **Best response.** Found fault code tables: O&M pp.46-47 Table 5 (flash codes), troubleshooting pp.69-72 (injector faults with SMCS codes). Used proper bracket citation format: `[sebu7689-12-00, p.46-47]`. Triaged active flash code vs logged fault. |
| B5 | Black smoke / power loss under load | PASS | — | 10 results triaged high/secondary: misfires & air inlet (renr9303 pp.33,38-39), fuel pressure (renr9326 p.63), sensor diagnostics (senr9646 p.66), fuel contamination (kenr6846 p.47), turbo inspection (sebu7822 p.124). Asked about engine model, fault codes, boost pressure. |

### Categories C, D, E: NOT TESTED

Session context limit reached. These should be tested in a follow-up session.

---

## Critical Findings

### 1. Multi-Turn Tool Hallucination (HIGH PRIORITY)

On follow-up turns, the LLM generates fake XML tool calls:
```xml
<search>
<query>injector protrusion measurement specification procedure C32</query>
<equipment>C32</equipment>
</search>
```

```xml
<get_page_content>
<source>sebu7822-10-00_manuals-operation-&-maintenance.pdf</source>
<page>119</page>
</get_page_content>
```

**Problem:** These tools don't exist. The raw XML is rendered directly in the chat UI.

**Root cause:** The system prompt describes a triage workflow ("I can pull the full page content...") but the assistant has no mechanism to actually retrieve additional content or re-search. It invents tool syntax.

**Fix options:**
1. Add explicit instruction to the system prompt: "You do NOT have tools. You cannot perform additional searches or retrieve page content. Work only with the context provided."
2. Implement actual tool calling (Anthropic function calling) so the assistant CAN re-search and retrieve pages
3. Strip XML-like tags from the response in the SSE stream before sending to client

### 2. RAG Search Precision (MEDIUM)

The FTS5 + stop-word stripping + OR expansion pipeline works for broad recall but struggles with precision:

- **Problem:** "Walk me through replacing the oil filter" → strips to `replacing OR oil OR filter` → matches oil pressure pages, oil level pages, etc. instead of the specific filter replacement procedure.
- **Problem:** "How do I clean the JWAC or aftercooler core?" → broad OR matches cooling-related pages but not the specific cleaning procedure.
- **What works well:** Short, specific queries with equipment filter (e.g., "ECU fault codes" + C18 filter → nailed it).

**Improvement recommendations:**

| Improvement | Impact | Effort |
|-------------|--------|--------|
| **Phrase matching:** Use FTS5 `"quoted phrases"` for multi-word terms ("oil filter", "valve lash", "injector height") | High | Low |
| **Synonym expansion:** Map "lash" ↔ "clearance", "height" ↔ "protrusion", "JWAC" ↔ "jacket water aftercooler" in query prep | High | Medium |
| **Two-pass search:** First try strict AND for short queries, fall back to OR if zero results | Medium | Low |
| **Section-level indexing:** Index by section headings (not just page text) so "oil filter replacement" matches the section title even if the page text says "remove element" | High | High |
| **Subsystem tagging boost:** Use the existing subsystem tags to boost results matching the query's implied system (fuel, lube, cooling) | Medium | Medium |
| **Re-ranking with embeddings:** Add a vector similarity re-ranking step after FTS5 retrieval for better semantic matching | High | High |

### 3. Citation Format Inconsistency (LOW)

- B4 used proper bracket format: `[sebu7689-12-00, p.46-47]`
- Most other responses used inline references: "Page 44 (senr9773 Testing & Adjusting)"
- The system prompt specifies `[Document Name, p.XX]` format but compliance is inconsistent

**Fix:** Add a few-shot example in the system prompt showing the exact citation format expected.

### 4. What's Working Well

- **No hallucinated specs:** Across all 11 tests, the LLM never invented torque, clearance, pressure, or interval values. This is the most important safety property and it's solid.
- **Transparent about search misses:** When RAG returns irrelevant content, the assistant says so explicitly rather than pretending the results are useful.
- **Good diagnostic structure:** Troubleshooting responses consistently use prioritized triage (primary → secondary), suggest starting points, and ask relevant clarifying questions.
- **Equipment awareness:** Correctly references manual numbers (KENR, SENR, RENR, SEBU prefixes), understands engine model differences, asks which engine when not specified.

---

## Remaining Tests for Next Session

Run C1-C4, D1-D4, E1-E3 using the same browser approach. After 2026-02-08 fixes, also re-test A3 and A4 follow-up turns to verify multi-turn hallucination is resolved. Key things to verify:
- **C (Intervals):** Does the LLM quote specific hour intervals from context? Does it invent intervals when not in context?
- **D (Specs):** Does it quote exact torque/clearance/pressure values verbatim? Does it add "verify against physical manual" reminder?
- **E (Edge cases):** Does E2 ("What's wrong with my engine?") trigger clarification? Does E3 (pasta) get declined as out of scope?

---

## Environment Notes

- The `engine_search.db` was accidentally overwritten with an empty database during an incomplete indexing run. A full re-index (62 PDFs, ~3.5 min) was required before testing could begin.
- CSRF protection blocks programmatic API testing via `requests` library (session token mismatch). Browser-based testing was used instead. For repeatable scripted tests, either exempt the chat API route from CSRF or use Flask's test client directly.
