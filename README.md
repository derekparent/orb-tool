# Oil Record Book Tool

Live engine room dashboard and fuel management app that auto-generates compliance documentation. Includes CAT engine manuals search and LLM-powered chat assistant (consolidated from engine_tool).

## The Problem

Maritime engineers manually track fuel consumption, tank soundings, and compliance entries. Data gets entered multiple times (daily logs, weekly reports, ORB entries, handover forms). Errors happen. Time gets wasted.

## The Solution

**Enter data once, use it everywhere.**

- Daily fuel tickets → Live dashboard
- Weekly soundings → Auto-generated ORB entries
- End of rotation → Print complete handover package

## Key Features

- [x] End of Hitch Soundings import (baseline)
- [x] Daily fuel ticket entry with consumption tracking
- [x] Weekly slop tank soundings → Code C and I ORB entries
- [x] Live dashboard showing fuel remaining, consumption rate
- [x] Handover package generation (forms + Excel for other crew)
- [x] Authentication and RBAC (Chief Engineer, Engineer, Read-only)
- [x] Manuals search: FTS5 search across CAT engine PDFs
- [x] LLM chat assistant for manuals (Anthropic, RAG-backed)
- [x] Offline support (localStorage, retry queue)
- [x] Structured logging and audit trail

## Tech Stack

- **Backend:** Python/Flask
- **Database:** SQLite (orb.db, engine_search.db for manuals)
- **Frontend:** Mobile-first responsive HTML/CSS/JS
- **Deployment:** Docker, gunicorn, health check endpoint

## Design Constraints

### Two-Crew Rotation
Blue crew uses the app. Gold crew prefers Excel. Solution: App generates pixel-perfect Excel/PDF handover so Gold crew never needs to know the app exists.

### Offshore Environment
- Handle temporary connectivity drops gracefully (don't lose user input)
- Mobile-first (phones, not laptops)
- No margin for data loss

## Development

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Database Migration (First time setup)
python simple_migration.py upgrade

# Run
flask run
```

### Manuals Indexing (optional)

To enable manuals search and chat, index PDFs:

```bash
python -m src.cli.index_manuals --pdf-dir /path/to/equipment-folders
```

Set `MANUALS_PDF_DIR` and `ANTHROPIC_API_KEY` in `.env` for manuals features.

## Database Migrations

This project uses Flask-Migrate (Alembic) for database schema evolution.

### Migration Commands

```bash
# Apply all migrations to database
python simple_migration.py upgrade

# Rollback one migration
python simple_migration.py downgrade

# Create new migration (after model changes)
python simple_migration.py create "Description of changes"
```

### Production Migration Workflow

1. **Backup database**: `cp data/orb.db data/orb.db.backup-$(date +%Y%m%d)`
2. **Review migration**: Check `migrations/versions/*.py` for SQL changes
3. **Test migration**: Run on copy of production data first
4. **Apply migration**: `python simple_migration.py upgrade`
5. **Verify**: Confirm app starts and data is intact

**Never skip migrations or run them out of order.**

## Project Structure

```
orb-tool/
├── src/
│   ├── app.py              # Flask app
│   ├── models.py           # Data models
│   ├── routes/             # API endpoints (api, auth, chat, manuals)
│   ├── services/           # Business logic
│   ├── cli/                # index_manuals for PDF indexing
│   └── config.py           # Configuration
├── templates/              # HTML templates
├── static/                 # CSS, JS, images
├── migrations/             # Database migration files
├── scripts/                # backup_database, restore_database, healthcheck
├── tests/
├── data/
│   ├── orb.db              # Main SQLite database
│   ├── engine_search.db    # Manuals FTS5 index (from indexer)
│   └── sounding_tables.json
├── docs/
│   ├── DATABASE_MIGRATIONS.md
│   ├── DEPLOYMENT.md
│   └── Engine_Room_Status_Board_Planning.md
├── simple_migration.py     # Migration management
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Documentation

- `docs/DATABASE_MIGRATIONS.md` — Migration workflow
- `docs/DEPLOYMENT.md` — Docker, systemd, backup strategy
- `docs/Engine_Room_Status_Board_Planning.md` — Feature specs and ORB formats

---

*Built by DP - Chief Engineer building AI tools for blue collar workers*
