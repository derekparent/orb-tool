# CLAUDE.md
*Context for AI agents working on DP's repos*

## Git - CRITICAL

**All repos use SSH authentication, not HTTPS.**

If push fails with "could not read Username":
```bash
git remote set-url origin git@github.com:Dparent97/oil_record_book_tool.git
```

## Commit Convention

```
type: short description (<72 chars)

Types: feat, fix, docs, refactor, test, chore
```

**Never mention AI/Claude in commit messages.**

## Code Style

### Python
- Type hints always
- f-strings for formatting
- Ruff/Black for formatting
- Explicit error handling

### General
- Readability > cleverness
- Explicit > implicit
- Handle errors, never fail silently

## Branch Naming

```
improve/[N]-description   # Multi-agent improvements
feature/description       # New features
fix/description          # Bug fixes
```

## Communication

- Be direct, skip preambles
- Show code, not descriptions
- Point out issues directly
- Commit often, small logical chunks

## When Done

Just say "Done." - no summaries unless asked.

```
✓ Completed task
⚠ Needs review
→ Next step
```

## Project Context

**Oil Record Book Tool** - Flask web app for maritime fuel/compliance tracking.

**Key constraints:**
- Mobile-first (used on phones aboard ship)
- Handle temporary connectivity drops gracefully (don't lose user input on network blip)
- Two-crew rotation: Blue crew uses app, Gold crew uses Excel (app generates Excel handover)
- Real users = real consequences

**Data:**
- Sounding tables in `data/sounding_tables.json`
- Conversion: gallons × 0.00378541 = m³

**Core features (MVP):**
- End of Hitch Soundings import (baseline)
- Daily fuel tickets → live dashboard
- Weekly slop tank soundings → ORB entry generation (Code C and I)
- Print handover package for crew rotation

## Workflow Tracking

After completing significant work, update these files:

1. **WORKFLOW_STATE.json** - Update status, phase, test counts, and add to history
2. **PROJECT_LEARNINGS.md** - Capture patterns, gotchas, and decisions

Do this automatically at the end of:
- Completing a feature or fix
- Finishing a wave/phase
- Integration work
- Any session with notable learnings
