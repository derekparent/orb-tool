# Prompt: Execute LLM Manuals Assistant Test Plan

**For:** Another agent (Claude) implementing the test plan  
**Context:** orb-tool project, LLM-powered manuals chat assistant at `/manuals/chat`

---

## Your Task

Execute the LLM Manuals Assistant test plan and record results. The plan is in [docs/LLM-Manuals-Assistant-Test-Plan.md](LLM-Manuals-Assistant-Test-Plan.md).

## Steps

1. **Start the app** (if not already running):
   ```bash
   cd /Users/dp/Projects/orb-tool/src && FLASK_APP=app:create_app ../venv/bin/flask run --port 5001
   ```
   App serves at http://localhost:5001.

2. **Verify prerequisites:**
   - `.env` has `ANTHROPIC_API_KEY` set
   - `data/engine_search.db` exists and is indexed (run `python -m src.cli.index_manuals` if needed)

3. **Run the test scenarios** from the plan:
   - Open http://localhost:5001/manuals/chat (log in if required)
   - Execute each query in Categories A, B, C, D and Edge Cases E1–E3
   - Use the exact query text from the plan tables

4. **Record results:**
   - For each test: pass / fail
   - Note any failures: missing citations, hallucinated specs, wrong behavior
   - Use the checklist template at the end of the test plan

5. **Report back:**
   - Summary: X of Y tests passed
   - List failed tests with brief reason
   - Suggest fixes if patterns emerge (e.g., prompt tweaks, RAG limit changes)

## What to Check

- **Citations:** Every factual answer should cite `[Document Name, p.XX]`
- **No hallucination:** No invented torque, clearance, pressure, or interval values
- **Scope:** Out-of-scope and no-context queries should be declined or redirected
- **Clarification:** Ambiguous queries should trigger follow-up questions

## Reference

- Test plan: [docs/LLM-Manuals-Assistant-Test-Plan.md](LLM-Manuals-Assistant-Test-Plan.md)
- Subsystem/equipment context: [docs/subsystem-tagging-guide.md](subsystem-tagging-guide.md)
