# Oil Record Book Tool

Live engine room dashboard and fuel management app that auto-generates compliance documentation.

## The Problem

Maritime engineers manually track fuel consumption, tank soundings, and compliance entries. Data gets entered multiple times (daily logs, weekly reports, ORB entries, handover forms). Errors happen. Time gets wasted.

## The Solution

**Enter data once, use it everywhere.**

- Daily fuel tickets → Live dashboard
- Weekly soundings → Auto-generated ORB entries
- End of rotation → Print complete handover package

## Key Features (MVP)

- [ ] End of Hitch Soundings import (baseline)
- [ ] Daily fuel ticket entry with consumption tracking
- [ ] Weekly slop tank soundings → Code C and I ORB entries
- [ ] Live dashboard showing fuel remaining, consumption rate
- [ ] Handover package generation (forms + Excel for other crew)

## Tech Stack

- **Backend:** Python/Flask
- **Database:** SQLite (portable, works offline)
- **Frontend:** Mobile-first responsive HTML/CSS/JS
- **Deployment:** TBD (Railway or similar)

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
oil_record_book_tool/
├── src/
│   ├── app.py              # Flask app
│   ├── models.py           # Data models
│   ├── routes/             # API endpoints
│   ├── services/           # Business logic
│   └── config.py           # Configuration
├── templates/              # HTML templates
├── static/                 # CSS, JS, images
├── migrations/             # Database migration files
│   ├── versions/           # Migration scripts
│   └── env.py              # Migration environment
├── scripts/                # Utility scripts
│   ├── backup_database.py  # Database backup
│   └── restore_database.py # Database restore
├── tests/
├── data/
│   ├── orb.db              # SQLite database
│   ├── backups/            # Database backups
│   └── sounding_tables.json # Tank conversion tables
├── docs/
│   ├── DATABASE_MIGRATIONS.md
│   └── ORB_App_Planning_Document.md
├── simple_migration.py     # Migration management
├── requirements.txt
└── README.md
```

## Documentation

See `docs/ORB_App_Planning_Document.md` for full planning document including:
- Feature specifications
- ORB entry formats (Code A, B, C, I)
- Sounding table conversion requirements
- Two-crew handover workflow

---

*Built by DP - Chief Engineer building AI tools for blue collar workers*
