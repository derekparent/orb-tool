# Project Goals

MAW reads this file to prioritize what to work on.
Update this as your priorities change!

## Active Focus
<!-- What you're working on NOW - MAW prioritizes these -->
- Specific exception handling — 15 bare `except Exception as e:` across route handlers. Replace with specific exception types (IntegrityError, OperationalError, etc.).
- Re-add rate-limiting — dropped during API consolidation. Flask-Limiter infrastructure exists in app.py/security.py but decorators not applied to api.py endpoints.

## Completed
<!-- Done — moved here for reference -->
- ~~Consolidate duplicate API routes~~ — merged secure_api.py into api.py. 13 duplicate endpoints eliminated, validation/auth unified.
- ~~Test coverage for critical untested modules~~ — manuals_service (99 tests), llm_service (26 tests), manuals_indexer (33 tests), manuals_assistant (52 tests) = 210 total.
- ~~Clickable suggestion chips~~ — PR #9, #11 (deterministic detection, 80 char max)
- ~~Citation format enforcement~~ — PR #10 (backend normalization to bracket format)
- ~~Full pytest suite passing~~ — PR #12 (367/367 pass)

## Backlog
<!-- Coming up next - MAW considers these secondary -->
- Page number display — citations show DB page index (p.82) vs printed page (48-49). Cosmetic but confusing. Could map DB→printed page numbers.
- Frontend tests (JS tests for form validation, API handling, offline behavior)
- API documentation (OpenAPI/Swagger spec)

## Not Now
<!-- Explicitly deprioritized - MAW skips unless critical -->
- OCR accuracy improvements (confidence scoring, manual correction UI)
- Performance monitoring (query profiling, caching, pagination)
- Staging/production deployment — local dev only for now

## Long-term Vision
<!-- Where is this project going? Helps MAW understand context -->
Production Oil Record Book + Engine Room Status Board used aboard ship. Mobile-first, handles connectivity drops. Two-crew rotation (Blue crew app, Gold crew Excel handover). LLM chat assistant for CAT engine manuals. Phase 2 deep-dive and PDF citations are merged — chat is functionally complete for triage + walkthrough workflow.

### LLM Assistant Evolution — "Troubleshooting Partner"

The current chat does triage + walkthrough from indexed manuals. The vision is a full **engineering troubleshooting partner** that goes beyond local OCR:

#### Phase 3: Parallel Internet Search
- After LLM has context from user query + manuals, spin up a **parallel web search** for supplementary info (forums, bulletins, TSBs)
- LLM suggests: "I found the manual procedure. Want me to also check online for known issues with 3516 injector lash on high-hour engines?"
- Could use a second, smarter model (e.g. GPT-5 / o3) for the web research leg while primary model handles manual walkthrough
- Present combined results: manual procedure + real-world gotchas from the field

#### Phase 4: CAT Parts & SIS Integration
- **CATPARTS.com integration** — LLM identifies part numbers from manual procedures, offers to check availability: "Do you want me to check CATPARTS.com for availability in your area?"
- **CAT SIS2 integration** — DP has SIS login. Explore what data files we can extract from CATSIS2, or if there's an API for parts lookup, service bulletins, or diagram retrieval
- **Parts search from context** — when walking through a procedure, auto-extract part numbers and cross-reference availability
- Start by auditing what's accessible from SIS2 (API? exportable files? scraping?)

#### Phase 5: Diagrams & Visual Context
- Surface relevant diagrams/illustrations alongside procedures (many CAT manuals have exploded views, torque diagrams, flow charts)
- Could be page-level (show the PDF page with the diagram) or extracted images
- LLM references: "See Figure 12 on page 54 for the valve bridge assembly"

#### Phase 6: Troubleshooting Council
- Multi-model approach: primary LLM does manual lookup, secondary does web research, third cross-checks against known failure modes
- "Council" synthesizes: manual says X, field reports say watch out for Y, parts availability is Z
- Structured output: procedure + warnings + parts + availability

#### Phase 7: Expand Beyond Manuals Chat
- LLM assists with other app pages: fuel tracking anomaly detection, sounding trend analysis, ORB entry suggestions
- "Your slop tank readings are trending up faster than normal — want me to check the manual for separator throughput specs?"
- Cross-reference fuel data with engine hours and maintenance intervals

### Key Constraints for All Phases
- **DP has CAT PARTS and SIS logins** — leverage these for authenticated access
- **Ship connectivity** — parallel searches must handle offline gracefully (manual-only fallback)
- **Engineer drives** — LLM suggests, never acts autonomously on parts ordering or external queries without user opt-in
- **Cost awareness** — secondary model calls (GPT-5, web search APIs) should be budgeted per-query

### Reference
- Original architecture plan: `.cursor/plans/search-integrated_chat_assistant_e7bdb770.plan.md`
- Current implementation: Phase 1 (triage) + Phase 2 (deep-dive) complete and merged
- PR #7 test notes: `docs/PR7-Test-Session-Notes-2026-02-07.md`

---
*Tip: Be specific. "Fix UI" is vague. "Mobile touch targets too small on inventory page" is actionable.*
