# Oil Record Book Utility - Project Planning Document

**Version:** Draft 1.0  
**Date:** November 15, 2025  
**Status:** Initial Planning Phase

---

## Executive Summary

Building a **live engine room status dashboard** and fuel management application that serves daily operational needs while automatically generating compliance documentation for Oil Record Book (ORB) entries, LARS exports, and regulatory requirements.

**Core Principle:** Enter data once, use it everywhere. No duplicate entry, always print-ready.

---

## Project Vision

Transform fuel management from manual paperwork into a **single source of truth** that:
- Serves engineers' daily operational needs
- Auto-generates compliance documentation
- Provides at-a-glance engine room status
- Generates pre-filled forms on demand
- Tracks consumption and inventory in real-time

---

## Platform Requirements

- **Mobile-First Design:** Fully functional on smartphones
- **Desktop Optimized:** Clean, professional layout for PC viewing
- **Responsive:** Seamless experience across all devices
- **Print-Ready:** Generate formatted documents from live data

---

## Core Features (Identified So Far)

### 1. Starting Baseline - "End of Hitch Soundings" Import

**Purpose:** Capture initial fuel state when arriving on vessel

**Input Method:**
- Accept screenshot of "End of Hitch Soundings" form
- Manual entry option as backup

**Data Captured:**
- Vessel name, location, date/time, charter
- Draft readings (Forward/Aft)
- Fuel on Log vs actual (with correction factor)
- **Fuel Tanks** (with sounding → volume conversion):
  - #7 Port/Stbd
  - #9 Port/Stbd
  - #11 Port/Stbd
  - #13 Port/Stbd
  - #14 Port/Stbd
  - #18 Port/Stbd Day Tanks
  - Water presence check for each
- **Service/Utility Tanks** (direct volume):
  - #15 Port/Stbd (Lube Oil, Gear Oil)
  - #16 Port/Stbd (Lube Oil, Hyd Oil)
  - #17 Port/Stbd (Oily Bilge, Dirty Oil)

**Output:**
- Stored as Day 0 baseline
- Used for first week's delta calculations
- Foundation for all subsequent tracking

---

### 2. Daily Operations Dashboard

**Purpose:** Real-time engine room status and daily fuel tracking

#### Service Tank Selector
- Choose active fuel tank pair (always matching P/S, e.g., #13P/S, #14P/S)
- Visual indicator of which tanks are currently in service
- Tank capacity and current volume display

#### Daily Fuel Ticket Entry
- Input meter readings from daily fuel ticket
- Deck officers receive this data
- Automatic consumption calculation

#### Live Tracking Display
- **Fuel Remaining:** Auto-calculated from tickets and soundings
- **Lube Oil Used:** Tracked and displayed
- **Current Service Tanks:** Active pair highlighted
- **Consumption Rate:** Daily/weekly trends

#### Quick Actions
- Print current status
- Generate shift handover report
- View consumption trends

---

### 3. Weekly Soundings - Slop Tanks

**Tanks:**
- **#17 Port (17P):** Dirty Oil Tank (6.08 m³ capacity)
- **#17 Stbd (17S):** Oily Water Tank (6.08 m³ capacity)

**Input:**
- Date and time of soundings
- Tank 17P sounding: Feet and Inches (e.g., 2' 4")
- Tank 17S sounding: Feet and Inches (e.g., 1' 10")
- Engineer name and title

**Conversion Process:**
- App contains sounding tables for both tanks
- Automatic lookup: Feet/Inches → Gallons
- Automatic conversion: Gallons → Cubic Meters (m³)

**Display:**
- Tank 17P: X gallons (Y m³) retained
- Tank 17S: X gallons (Y m³) retained
- Delta from previous week
- Alert if unusual changes detected (leak detection)

**Output - Two ORB Entries Generated:**

**Entry 1 - Code C (Dirty Oil Tank):**
```
DATE: [User's Date]
CODE: C
11.1 Dirty Oil Tank (17P)
11.2 6.08 m³ capacity
11.3 [Calculated] m³ retained
11.4 N/A
[Engineer Name], ([Title]) [DATE]
```

**Entry 2 - Code I (Oily Water Tank):**
```
DATE: [User's Date]
CODE: I
34.1 Oily Water Tank (17S)
34.2 6.08 m³ capacity
34.3 [Calculated] m³ retained
[Engineer Name], ([Title]) [DATE]
```

**Features:**
- One-tap generation of both entries
- Copy/paste ready format
- Historical tracking of weekly volumes
- Visual indication of trends (increasing/decreasing)

---

### 4. ORB Entry Generation

**Purpose:** Generate MARPOL-compliant Oil Record Book entries

**Features:**
- Pre-written templates for common operations
- Auto-populated with current data
- Accurate, audit-safe wording
- Never fabricates data - only uses user-provided info

**Entry Types Identified:**

**A-Code: Ballasting or Cleaning of Fuel Tanks**
```
Example Format:
DATE: [Date]
CODE: A
3.1 [Location and time]
3.2 [Tank identifier]
3.3 [Details of operation]
[Engineer Name], ([Title]) [DATE]
```

**B-Code: Discharge of Dirty Ballast or Cleaning Water**
```
Example Format:
DATE: [Date]
CODE: B
5 [Tank identifier]
6 [Start location]
7 [Stop location]
8 [Speed in knots]
9.2 [Discharge method - e.g., Vac Truck]
10 [Volume in m³]
[Engineer Name], ([Title]) [DATE]
```

**C-Code: Weekly Inventory of Oil Residues (Sludge)**
```
Format - See Weekly Soundings section for complete implementation
CODE: C - Dirty Oil Tank tracking
```

**I-Code: Weekly Inventory of Bilge Water**
```
Format - See Weekly Soundings section for complete implementation  
CODE: I - Oily Water Tank tracking
```

**Additional Entry Types (To Be Defined):**
- Daily fuel consumption entries
- Internal fuel transfers
- Bunkering operations
- Settling/service tank changes

**Output Format:**
- Clean, compliant text
- Ready for copy/paste into official ORB
- Stored for historical record
- Can be exported as formatted document

---

### 5. Forms Generation System

**Concept:** Print any needed form with live data pre-filled

**Identified Forms:**
- End of Hitch Soundings
- Daily fuel tickets
- ORB entries
- LARS export format
- (More to be defined from uploaded documents)

---

## Data Flow Architecture

```
Day 0: End of Hitch Soundings (Baseline)
    ↓
Daily: Fuel Tickets → Consumption Tracking → Dashboard Updates
    ↓
Weekly: Slop Tank Soundings → Volume Calculations → ORB Entry
    ↓
On-Demand: Print Forms (pre-filled) | Export to LARS | Historical Reports
```

---

## Technical Approach

### Sounding Table Conversions
- Store conversion tables internally (feet/inches → gallons)
- **Tank 17P (Dirty Oil):** Feet/inches to gallons lookup table
- **Tank 17S (Oily Water):** Feet/inches to gallons lookup table  
- **Fuel Tanks (#7, #9, #11, #13, #14, #18):** Conversion tables from uploaded sounding sheets
- Automatic volume calculation
- Automatic unit conversion (gallons → cubic meters for ORB entries)
- Manual override option if needed

### Unit Conversions
- **Gallons to Cubic Meters (m³):** 1 gallon = 0.00378541 m³
- Display both units where relevant
- ORB entries use m³ (MARPOL standard)
- Internal tracking can use gallons (more familiar to crew)

### Calculations Required
- Total ROB (Remaining On Board)
- Delta calculations (weekly, daily)
- Consumption rates
- Fuel remaining after ticket entry
- Lube oil usage tracking

### Data Validation
- Detect unrealistic changes
- Warn on unusual consumption
- Flag potential leaks or errors
- Require confirmation for outliers

---

## Safety & Compliance Principles

- **No Assumptions:** Never fabricate quantities, timestamps, or personnel data
- **User Data Only:** All entries based on explicitly provided information
- **Conflict Warnings:** Alert if numbers don't reconcile
- **Audit Trail:** Historical record of all entries
- **MARPOL Compliance:** All ORB entries follow regulatory standards

---

## Features to be Defined

**Areas requiring further specification:**

**Bunkering Operations:**
- Pre-bunker planning workflow (referenced in uploaded Fuel Notes doc)
- Fuel sampling procedures
- Bunker Delivery Note (BDN) data capture
- Request to Witness form integration
- Post-bunker reconciliation
- Fuel treatment tracking (Amerstat/Amergy XLS)

**Internal Fuel Transfer Tracking:**
- Tank-to-tank transfers
- Settling tank operations
- Service tank changes
- Transfer procedures and documentation

**Additional ORB Entry Types:**
- A-Code: Ballasting/Cleaning operations (format known, workflow needed)
- B-Code: Discharge operations (format known, workflow needed)
- Daily fuel consumption entries (linked to fuel ticket workflow)
- Sludge disposal operations
- Other operational entries

**Forms to Generate:**
- Pre-Bunker Sounding form
- Post-Bunker Sounding form  
- Load Plan
- Fuel Treatment Log
- Declaration of Inspection (Transfer Checklist)
- LARS export format
- Any other required handover documents

**Calculations Needed:**
- Fuel consumption rate tracking
- Cost per gallon/day calculations
- Efficiency metrics
- Leak detection algorithms
- Fuel treatment dosage calculations

**User Roles & Permissions:**
- Who can enter data vs. view only?
- Chief Engineer admin access
- Regular engineer permissions
- Shore-side viewing rights (if applicable)

**Historical Reporting:**
- Monthly summaries
- Consumption trends
- Cost analysis
- Efficiency comparisons
- Audit trail requirements

---

---

## Critical Design Constraint: Two-Crew Rotation System

### The Challenge:
**Blue Crew (21 days on) → Gold Crew (21 days on)**

**Blue Crew wants:**
- Modern app for data entry
- Live dashboard
- Single entry point for all data
- Real-time calculations

**Gold Crew prefers:**
- Traditional Excel spreadsheets
- Familiar paper forms
- Established workflow

**Problem:**
If Blue Crew uses app AND maintains Excel for Gold Crew = **Double work = App dies**

### The Solution:

**Blue Crew's Experience:**
1. Use app exclusively during 21-day rotation
2. Fast, validated data entry
3. Live dashboard for operational status
4. At end of rotation: Click "Generate Handover Package"
5. App auto-creates:
   - End of Hitch Soundings form (printed/PDF)
   - All Excel logs (auto-filled from app data)
   - Any other forms Gold crew expects
6. Leave forms for Gold crew / save to OneDrive
7. Walk off boat

**Gold Crew's Experience:**
1. Arrive to familiar paper forms
2. Continue using Excel as always
3. Zero knowledge that app exists
4. At end of rotation: Fill out End of Hitch Soundings
5. Blue crew screenshots form on return

**Result:**
- ✅ Blue Crew: Zero double work, modern workflow
- ✅ Gold Crew: Zero change required
- ✅ Company: All Excel logs maintained
- ✅ No adoption battle

### Key Technical Requirements:
1. **Perfect form replication:** Generated forms must be pixel-perfect matches of current Excel/paper forms
2. **Background Excel maintenance:** App maintains Excel logs automatically during Blue crew's 21 days
3. **Fast screenshot import:** Quick OCR/data capture from Gold crew's End of Hitch form
4. **Excel structure matching:** Generated spreadsheets must match Gold crew's exact format (columns, formulas, tabs)

---

## Next Steps

1. **Complete Feature Discovery**
   - Review uploaded documents (Slop Tanks.xlsx, ORB_Cheat_Sheet.docx)
   - Identify remaining workflows and forms
   - Capture all calculations needed
   - Define "must have" vs "nice to have"

2. **Organize & Prioritize**
   - Group features into logical modules
   - Create MVP vs Phase 2 vs Future roadmap
   - Identify dependencies

3. **Design Data Model**
   - Map information flow
   - Define storage requirements
   - Plan for historical data

4. **Technical Stack Selection**
   - Mobile-first responsive framework
   - Database architecture
   - Deployment strategy

5. **Build Development Plan**
   - Sprint structure
   - Testing approach
   - Rollout strategy

---

## Team Review Questions

1. Does this capture the vision accurately?
2. Are there critical workflows missing?
3. What's the priority order for features?
4. Who are the primary users? (Engineers only, or deck officers too?)
5. Any regulatory requirements we haven't addressed?
6. Timeline expectations?
7. Budget considerations?

---

## Document Status

- [ ] Initial team review
- [ ] Feature discovery complete
- [ ] Prioritization agreed
- [ ] Technical approach approved
- [ ] Development roadmap finalized
- [ ] Ready to build

---

**Prepared for:** Engineering Team Review  
**Contact:** DP  
**Next Review Date:** TBD
