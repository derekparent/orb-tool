# Engine Room Status Board - Project Planning Document

**Version:** 2.0  
**Date:** December 18, 2025  
**Status:** Active Development  
**Vessel:** USNS Arrowhead

---

## Executive Summary

Building an **Engine Room Status Board** - a comprehensive operational dashboard that provides at-a-glance vessel status while offering a suite of engineering tools including ORB compliance documentation, fuel tracking, and equipment status monitoring.

**Core Principle:** Status board first, detailed logging stays in Excel. Enter data once, generate compliance docs automatically.

**What This App IS:**
- At-a-glance engine room status dashboard
- Quick status updates (sewage pumped, potable loaded, equipment notes)
- ORB compliance tool (slop tank soundings → Code C/I entries)
- Fuel/oil consumption tracking
- Handover package generator for crew rotation

**What This App IS NOT:**
- Replacement for 4-hour operating logs (temps, pressures)
- Replacement for daily end-of-day Excel entries
- Filter change tracking system
- Parts ordering system

---

## Dashboard Layout

```
┌─────────────────────────────────────────────────────────────┐
│  ENGINE ROOM STATUS                        USNS Arrowhead   │
│  Live operational overview                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ CURRENT FUEL│  │  LUBE OIL   │  │  GEAR OIL   │          │
│  │ 125,134 gal │  │   606 gal   │  │   279 gal   │          │
│  │ #13 P/S     │  │    15P      │  │    15S      │          │
│  │ ▓▓▓▓▓▓▓░░░  │  │  ▓▓▓░░░░░   │  │  ▓▓░░░░░░   │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ HYDRAULIC   │  │   SEWAGE    │  │  POTABLE    │          │
│  │   305 gal   │  │ Pumped:     │  │ Loaded:     │          │
│  │    16S      │  │ Dec 15      │  │ Dec 12      │          │
│  │  ▓▓▓░░░░░   │  │ (3 days)    │  │ (6 days)    │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  SLOP TANKS (ORB)                                           │
│  ┌────────────────────┐  ┌────────────────────┐             │
│  │ 17P Oily Water     │  │ 17S Dirty Oil      │             │
│  │ 17 gal · 0.06 m³   │  │ 34 gal · 0.13 m³   │             │
│  │ Code I             │  │ Code C             │             │
│  └────────────────────┘  └────────────────────┘             │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  EQUIPMENT STATUS                                           │
│  PME ✓   PRG ✓   SME ✓   SRG ✓   SSDG1 ✓   SSDG2 ✓        │
│  SSDG3 ✓   T1 ✓   T2 ✓   T3 ✓                              │
│  All systems: Online (NTR)                                  │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [+ Update Status]  [Weekly Sounding]  [Tools ▼]            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Module Specifications

### 1. Dashboard (Home)

**Purpose:** At-a-glance operational status - what you check when you walk into the engine room

**Cards:**

| Card | Data Displayed | Click Action |
|------|----------------|--------------|
| Current Fuel | Total ROB (gal), active service tank pair | → Fuel Module |
| Lube Oil | 15P level (gal) | → Quick update |
| Gear Oil | 15S level (gal) | → Quick update |
| Hydraulic Oil | 16S level (gal) | → Quick update |
| Sewage | Date last pumped, days ago | → Date picker |
| Potable | Date last loaded, days ago | → Date picker |
| Slop Tanks | 17P/17S levels with ORB codes | → Weekly Sounding form |
| Equipment | 10 items with status indicators | → Equipment Status editor |

---

### 2. Fuel Module (Expanded)

**Purpose:** Track fuel consumption and oil levels from daily tickets

**Features:**
- Service tank selector (#7, #9, #11, #13, #14, #18 P/S)
- Meter readings entry (start/end)
- Auto-calculate consumption
- Photo upload for fuel ticket (with ticket #)
- Track on same ticket:
  - Fuel consumption
  - 15P Lube Oil
  - 15S Gear Oil
  - 16P Lube Oil
  - 16S Hydraulic Oil

**Data Model:**
```
FuelTicket:
  - ticket_date
  - ticket_number (optional, from photo)
  - service_tank_pair
  - meter_start
  - meter_end
  - consumption_gallons
  - lube_15p_gallons (optional)
  - gear_15s_gallons (optional)
  - lube_16p_gallons (optional)
  - hyd_16s_gallons (optional)
  - engineer_name
  - photo_path (optional)
  - notes
```

---

### 3. Quick Status Updates

**Sewage Tank:**
- Simple date picker: "When did you pump sewage?"
- Stores date, calculates "X days ago" for display
- No volume tracking needed (just operational awareness)

**Potable Water:**
- Simple date picker: "When did you load potable?"
- Stores date, calculates "X days ago" for display
- No volume tracking needed

**Data Model:**
```
StatusEvent:
  - event_type (sewage_pump, potable_load, etc.)
  - event_date
  - notes (optional)
  - engineer_name
```

---

### 4. Equipment Status Module

**Purpose:** Track operational status of critical machinery

**Equipment List (10 items):**
```
ID        Name                  Default Status
───────────────────────────────────────────────
PME       Port Main Engine      Online
PRG       Port Reduction Gear   Online
SME       STBD Main Engine      Online
SRG       STBD Reduction Gear   Online
SSDG1     Generator #1          Online
SSDG2     Generator #2          Online
SSDG3     Generator #3          Online
T1        FWD Bow Thruster      Online
T2        AFT Bow Thruster      Online
T3        Stern Thruster        Online
```

**Status Options:**
- ✓ Online (green) - "NTR" or "No issues"
- ⚠ Issue (yellow) - With note field
- ✗ Offline (red) - With note field

**Data Model:**
```
EquipmentStatus:
  - equipment_id (PME, PRG, etc.)
  - status (online, issue, offline)
  - note (required if issue/offline)
  - updated_at
  - updated_by
```

---

### 5. Weekly Soundings / ORB Module (Already Built)

**Status:** ✅ Complete

**Tanks:**
- 17P - Oily Water Tank (Code I)
- 17S - Dirty Oil Tank (Code C)

**Features:**
- Feet/inches input → auto-lookup gallons → convert to m³
- Generate MARPOL-compliant ORB entries
- Copy button for paste into official ORB
- Historical tracking with deltas

---

### 6. Hitch Start Import

**Purpose:** Capture baseline when Blue Crew arrives

**Workflow:**
1. App detects new hitch (or user triggers "Start New Hitch")
2. User uploads photo of Gold Crew's End of Hitch Soundings form
3. OCR extracts tank levels (or manual entry fallback)
4. Data becomes Day 0 baseline
5. All tracking resets/continues from this point

**Data Captured:**
- All fuel tank levels (#7, #9, #11, #13, #14, #18 P/S)
- Service tank levels (15P, 15S, 16P, 16S)
- Slop tank levels (17P, 17S)
- Date/time of turnover
- Incoming engineer name

**Priority:** HIGH - enables proper delta tracking

---

### 7. Handover Package Generator

**Purpose:** Generate all forms Gold Crew expects at end of Blue Crew's hitch

**Outputs:**
- End of Hitch Soundings form (PDF, matching existing format)
- Vessel Status summary (matching Generic_VESSEL_STATUS.docx format)
- Excel logs if needed (matching Gold Crew's format)

**Priority:** HIGH - critical for crew rotation workflow

---

## Tool Suite (Future)

| Tool | Description | Priority |
|------|-------------|----------|
| **ORB Entry Tool** | Generate any ORB entry type | In Progress |
| **Status Report Tool** | Generate vessel status doc | Medium |
| **Standard Text Tool** | Pre-written text for filter changes, PMs | Medium |
| **Oil Order Tool** | Generate oil requisition | Low |
| **Chemical Order Tool** | Generate chemical requisition | Low |
| **Hazmat Tool** | Track hazmat inventory/disposal | Low |
| **Bunkering Tool** | Full bunkering workflow (pre/post/BDN) | Complex - Last |

---

## Data Architecture

### Service Oil Tanks

| Tank | Contents | Capacity | Tracking |
|------|----------|----------|----------|
| 15P | Lube Oil | TBD gal | Level in gallons |
| 15S | Gear Oil | TBD gal | Level in gallons |
| 16P | Lube Oil | TBD gal | Level in gallons |
| 16S | Hydraulic Oil | TBD gal | Level in gallons |

### Slop Tanks (ORB Compliance)

| Tank | Contents | Capacity | ORB Code |
|------|----------|----------|----------|
| 17P | Oily Water | 1607 gal (6.08 m³) | Code I |
| 17S | Dirty Oil | 1607 gal (6.08 m³) | Code C |

### Fuel Storage Tanks

| Tank | Capacity | Notes |
|------|----------|-------|
| #7 P/S | TBD | Storage |
| #9 P/S | TBD | Storage |
| #11 P/S | TBD | Storage |
| #13 P/S | TBD | Service |
| #14 P/S | TBD | Service |
| #18 P/S | TBD | Day Tanks |

---

## Database Schema Updates Required

### New Tables

```sql
-- Quick status events (sewage, potable, etc.)
CREATE TABLE status_events (
    id INTEGER PRIMARY KEY,
    event_type TEXT NOT NULL,  -- 'sewage_pump', 'potable_load'
    event_date DATETIME NOT NULL,
    notes TEXT,
    engineer_name TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Equipment status tracking
CREATE TABLE equipment_status (
    id INTEGER PRIMARY KEY,
    equipment_id TEXT NOT NULL,  -- 'PME', 'SSDG1', etc.
    status TEXT NOT NULL,  -- 'online', 'issue', 'offline'
    note TEXT,
    updated_at DATETIME NOT NULL,
    updated_by TEXT NOT NULL
);

-- Service oil tank levels
CREATE TABLE oil_levels (
    id INTEGER PRIMARY KEY,
    recorded_at DATETIME NOT NULL,
    tank_15p_lube REAL,
    tank_15s_gear REAL,
    tank_16p_lube REAL,
    tank_16s_hyd REAL,
    source TEXT,  -- 'fuel_ticket', 'manual', 'hitch_start'
    engineer_name TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Hitch tracking
CREATE TABLE hitch_records (
    id INTEGER PRIMARY KEY,
    start_date DATETIME NOT NULL,
    end_date DATETIME,
    crew TEXT,  -- 'blue', 'gold'
    starting_fuel_rob REAL,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Updates to Existing Tables

```sql
-- Add to daily_fuel_tickets
ALTER TABLE daily_fuel_tickets ADD COLUMN ticket_number TEXT;
ALTER TABLE daily_fuel_tickets ADD COLUMN photo_path TEXT;
ALTER TABLE daily_fuel_tickets ADD COLUMN lube_15p_gallons REAL;
ALTER TABLE daily_fuel_tickets ADD COLUMN gear_15s_gallons REAL;
ALTER TABLE daily_fuel_tickets ADD COLUMN lube_16p_gallons REAL;
ALTER TABLE daily_fuel_tickets ADD COLUMN hyd_16s_gallons REAL;
```

---

## Implementation Phases

### Phase 1: Dashboard Expansion (Current)
- [ ] Rename app: "ORB Tool" → "Engine Room Status Board"
- [ ] Add sewage/potable date cards
- [ ] Add oil level cards (lube, gear, hydraulic)
- [ ] Add equipment status section
- [ ] Create status_events table
- [ ] Create equipment_status table

### Phase 2: Equipment Status Module
- [ ] Equipment list page
- [ ] Status update form (online/issue/offline + note)
- [ ] Dashboard integration
- [ ] Historical status log

### Phase 3: Enhanced Fuel Tracking
- [ ] Expand fuel ticket form (add oil fields)
- [ ] Photo upload for tickets
- [ ] oil_levels table and tracking

### Phase 4: Hitch Management
- [ ] Hitch start workflow
- [ ] Photo upload → OCR for soundings
- [ ] Baseline capture
- [ ] Handover package generation

### Phase 5: Tool Suite
- [ ] Status report generator
- [ ] Standard text library
- [ ] Additional tools as needed

### Phase 6: Bunkering (Complex)
- [ ] Pre-bunker planning
- [ ] Load plan generation
- [ ] Post-bunker reconciliation
- [ ] BDN integration
- [ ] ORB entry generation

---

## Two-Crew Rotation (Unchanged)

**Blue Crew (21 days):** Uses app exclusively  
**Gold Crew (21 days):** Uses Excel/paper as always

**Key:** App generates handover package that looks exactly like Gold Crew's expected forms. Zero adoption friction.

---

## Technical Stack

- **Backend:** Python/Flask
- **Database:** SQLite (portable, offline-capable)
- **Frontend:** Mobile-first responsive HTML/CSS/JS
- **Deployment:** TBD (needs to work on ship network)

---

## File Structure (Updated)

```
engine_room_status_board/
├── src/
│   ├── app.py
│   ├── config.py
│   ├── models.py              # Add new tables
│   ├── routes/
│   │   ├── api.py             # Expand API
│   │   └── __init__.py
│   └── services/
│       ├── sounding_service.py
│       ├── orb_service.py
│       ├── fuel_service.py
│       ├── equipment_service.py   # NEW
│       └── status_service.py      # NEW
├── templates/
│   ├── base.html
│   ├── dashboard.html         # Expand
│   ├── soundings.html
│   ├── fuel.html              # Expand
│   ├── equipment.html         # NEW
│   └── history.html
├── static/
│   ├── css/style.css
│   └── js/app.js
├── data/
│   ├── sounding_tables.json
│   └── orb.db
├── tests/
└── docs/
    └── Engine_Room_Status_Board_Planning.md  # This file
```

---

## Success Metrics

1. **Adoption:** Blue Crew uses app daily without complaint
2. **Time Saved:** Reduces handover prep time
3. **Accuracy:** ORB entries are audit-ready
4. **Zero Friction:** Gold Crew receives familiar forms, never touches app

---

**Document Status:** ✅ Planning Complete  
**Next Action:** Begin Phase 1 - Dashboard Expansion  
**Owner:** DP
