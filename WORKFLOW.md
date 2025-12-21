# Multi-Agent Workflow Guide

This project uses the multi-agent workflow system.

## Quick Commands

```bash
# Check current status
python workflow/core/workflow_state.py . 

# Get next recommended action
python workflow/core/workflow_state.py . next-step

# Update to specific phase
python workflow/core/workflow_state.py . phase 3

# Mark phase complete
python workflow/core/workflow_state.py . complete 3
```

## Workflow Phases

1. **Phase 1: Planning** - Requirements analysis and architecture
2. **Phase 2: Framework** - Build skeleton code and structure
3. **Phase 3: Codex Review** - Deep code analysis, generate agent prompts
4. **Phase 4: Agent Work** - Parallel agents implement improvements
5. **Phase 5: Integration** - Review and merge agent PRs
6. **Phase 5.5: Quality Audit** - Post-integration review
7. **Phase 6: Iteration** - Decide: deploy, iterate, or add features

## Directory Structure

```
workflow/
├── core/           # Workflow engine (workflow_state.py)
├── phases/         # Phase instructions (phase1-6 guides)
├── templates/      # PR templates, prompts, stubs
├── scripts/        # Automation scripts
└── learnings/      # Reference patterns and best practices
```

## Phase Guides

For detailed instructions on each phase:
- `workflow/phases/README.md` - Overview of all phases
- `workflow/phases/phase3-codex-review.md` - Start here for existing projects

## After Each Iteration

Update `PROJECT_LEARNINGS.md` with:
- What worked well
- What didn't work
- Patterns worth promoting to central learnings

## Reference

- `workflow/learnings/MASTER_LEARNINGS.md` - Accumulated best practices
- `workflow/templates/` - Templates for PRs, proposals, etc.
