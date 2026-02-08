# LLM Manuals Assistant — Test Results

**Date:** 2026-02-07
**Executor:** Claude (Cursor agent)
**App:** http://localhost:5001/manuals/chat
**DB:** 62 PDFs indexed, 5,736 pages, 11.2M chars

---

## Summary

**21 of 21 tests executed** (2026-02-08 manual browser run completed)
**21 of 21 PASS on single-turn** (LLM behavior)
**2 of 2 PASS on multi-turn follow-up** (A3, A4 re-tested after fix — no hallucinated XML)

Categories C, D, and E were run 2026-02-08. A3 and A4 follow-ups were re-run to verify multi-turn hallucination fix (commit 6730478).

**2026-02-08 update:** Full manual run: C1–C4, D1–D4, E1–E3 completed. A3 and A4 follow-up turns re-tested; no `<search>` or `<get_page_content>` XML in responses. Fix verified.

---

## Execution Checklist

```
Category A (Procedures):      A1 [x] A2 [x] A3 [x] A4 [x] A5 [x]
Category B (Troubleshooting):  B1 [x] B2 [x] B3 [x] B4 [x] B5 [x]
Category C (Intervals):       C1 [x] C2 [x] C3 [x] C4 [x]
Category D (Specs):           D1 [x] D2 [x] D3 [x] D4 [x]
Edge Cases:                   E1 [x] E2 [x] E3 [x]
Multi-turn re-test:           A3 follow-up [x] A4 follow-up [x]
```

---

## Detailed Results

### Category A: Procedures

| # | Query | Single-Turn | Follow-Up | Notes |
|---|-------|:-----------:|:---------:|-------|
| A1 | Valve lash on C18 | PASS | — | 10 RAG results, triaged by manual type (D&A, T&A, troubleshooting), asked inlet vs exhaust. No hallucinated clearance specs. |
| A2 | 3516 fuel rack actuator troubleshooting | PASS | — | 10 results, triaged by manual (KENR5403, KENR6055, KENR5404) with specific pages. Asked about symptoms, fault codes, goal. |
| A3 | JWAC / aftercooler cleaning | PASS | **PASS** (2026-02-08) | Initial: 10 results, p.119 sebu7822 caustic NOTICE. Follow-up "What's the safety warning?": natural language only, referenced real docs; **no XML tool calls**. |
| A4 | Injector height on C32 | PASS | **PASS** (2026-02-08) | Initial: honest about mismatch, suggested "injector protrusion", senr9773-04, renr8628-10. Follow-up "What tools do I need?": **no fake `<search>` XML**. |
| A5 | Replacing oil filter | PASS | — | RAG returned oil system pages (pressure, levels) not filter replacement specifically. No hallucination, asked for engine model. Search precision issue. |

### Category B: Troubleshooting

| # | Query | Single-Turn | Follow-Up | Notes |
|---|-------|:-----------:|:---------:|-------|
| B1 | Cranks but won't fire | PASS | — | Structured 3-direction diagnostic: fuel priming (pp.135-136), electrical/sensor checks (RENR9303 p.37, RENR7914 schematics), systematic troubleshooting (SENR9646 p.38). Mentioned 30-second cranking limit from context. |
| B2 | Low oil pressure alarm | PASS | — | Triaged primary/secondary: oil level (senr9773 p.44), bypass valves (senr9646 p.76), temp effects (p.46), fuel dilution (p.48), bearing wear (kenr6846 p.64). No invented pressure thresholds. |
| B3 | Main engine overheating (3516) | PASS | — | RAG didn't return cooling troubleshooting content directly. Transparent about mismatch. Suggested where to look in physical manuals, asked relevant diagnostic questions (actual temp, coolant level, raw water flow, load condition). No hallucinated temperature thresholds. |
| B4 | ECU fault codes for C18 | PASS | — | **Best response.** Found fault code tables: O&M pp.46-47 Table 5 (flash codes), troubleshooting pp.69-72 (injector faults with SMCS codes). Used proper bracket citation format: `[sebu7689-12-00, p.46-47]`. Triaged active flash code vs logged fault. |
| B5 | Black smoke / power loss under load | PASS | — | 10 results triaged high/secondary: misfires & air inlet (renr9303 pp.33,38-39), fuel pressure (renr9326 p.63), sensor diagnostics (senr9646 p.66), fuel contamination (kenr6846 p.47), turbo inspection (sebu7822 p.124). Asked about engine model, fault codes, boost pressure. |

### Category C: Maintenance Intervals (2026-02-08)

| # | Query | Result | Notes |
|---|-------|:------:|-------|
| C1 | When do I need to change the engine oil? | PASS | O&M pages (84–111), SEBU8118/7844/7689; asked interval vs procedure and engine; no invented hours. |
| C2 | What's the coolant change interval? | PASS | SEBU8245, SEBU7793, SEBU7919-09 p.112 maintenance schedule; SCA mentioned; no invented intervals; asked engine. |
| C3 | Is there a 500hr fuel filter change? | PASS | Said none explicitly mention 500hr in snippets; cited pp.103,108 procedures; suggested maintenance schedule; no invented intervals. |
| C4 | How often replace air filter? | PASS | None directly specify interval; cited senr9773-04 p.38 (plugged air cleaner); explained indexed manuals are troubleshooting not schedules; no invented intervals. |

### Category D: Specs / References (2026-02-08)

| # | Query | Result | Notes |
|---|-------|:------:|-------|
| D1 | Cylinder head torque 3516 | PASS | KENR6055 pp.67,72; said "I won't guess on this one"; pointed to pp.70–75 for torque; no invented values. |
| D2 | Valve clearances C18 | PASS | No results in indexed content; said "cannot provide from memory or guess at"; pointed to T&A valve mechanism section; no invented clearances. |
| D3 | Fuel pressure at rail | PASS | Distinguished tank test 35 kPa from rail pressure; kenr5402-07-00; asked which rail, condition, engine; no invented psi. |
| D4 | Turbo boost C32 | PASS | SENR9772-06 Specifications identified; triaged specs vs troubleshooting; no invented boost values. |

### Edge Cases (2026-02-08)

| # | Query | Result | Notes |
|---|-------|:------:|-------|
| E1 | 3516 fuel rack actuator troubleshooting | PASS | Correctly said 3516 uses EUI not mechanical fuel rack; redirected to injector diagnostics (cylinder cutout p.40, electrical pp.253–255); no hallucination. |
| E2 | What's wrong with my engine? | PASS | Must ask clarification (engine, symptoms). Executed; response requested engine/symptoms. |
| E3 | How do I cook pasta? | PASS | "That's outside the manuals I have indexed"; listed only CAT engine documentation; declined out of scope. |

### Multi-Turn Follow-Up Re-Test (2026-02-08)

After fix (commit 6730478: "No Tools" in system prompt):

- **A3 follow-up:** "What's the safety warning for that procedure?" — Response used natural language only, referenced sebu7822 p.119 caustic NOTICE and safety sections; **no `<get_page_content>` or `<search>` XML**.
- **A4 follow-up:** "What tools do I need?" — Follow-up sent in same chat; **no fake `<search>` XML** in response. Multi-turn hallucination fix verified.

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

**Done (2026-02-08).** C1–C4, D1–D4, E1–E3 and A3/A4 follow-ups were run via browser. Multi-turn hallucination fix verified (no XML tool calls on follow-up).

---

## Environment Notes

- The `engine_search.db` was accidentally overwritten with an empty database during an incomplete indexing run. A full re-index (62 PDFs, ~3.5 min) was required before testing could begin.
- CSRF protection blocks programmatic API testing via `requests` library (session token mismatch). Browser-based testing was used instead. For repeatable scripted tests, either exempt the chat API route from CSRF or use Flask's test client directly.
