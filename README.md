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
- **Deployment:** TBD (needs to work in low-bandwidth environments)

## Design Constraints

### Two-Crew Rotation
Blue crew uses the app. Gold crew prefers Excel. Solution: App generates pixel-perfect Excel/PDF handover so Gold crew never needs to know the app exists.

### Offshore Environment
- Must work with spotty internet
- Mobile-first (phones, not laptops)
- No margin for data loss

## Development

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run
flask run
```

## Project Structure

```
oil_record_book_tool/
├── src/
│   ├── app.py              # Flask app
│   ├── models/             # Data models
│   ├── routes/             # API endpoints
│   ├── services/           # Business logic
│   └── templates/          # HTML templates
├── static/                 # CSS, JS, images
├── tests/
├── data/
│   └── sounding_tables/    # Tank conversion tables
├── docs/
│   └── ORB_App_Planning_Document.md
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
