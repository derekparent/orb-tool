# Marine Diesel Engine Technical Manual: Subsystem Tagging Guide

**For:** Caterpillar engine search tool (3516, C18, C32, C4.4)
**Scope:** 62 PDFs | Python/SQLite/Flask stack
**Goal:** Add subsystem filtering to full-text search

**Source:** Perplexity Deep Research (2026-02-01)

---

## 1. SUBSYSTEM TAXONOMY

### Primary Systems (10-12 categories)

| System | Purpose | Key Components |
|--------|---------|-----------------|
| **Fuel System** | Deliver pressurized fuel to injectors | Fuel tank, transfer pump, filters, fuel rack, injectors, fuel cooler |
| **Air Intake System** | Supply clean, compressed air to cylinders | Air filter, turbocharger, intercooler, intake manifold, boost control |
| **Cooling System** | Remove combustion heat via water/seawater circuits | Water pump, freshwater radiator, seawater heat exchanger, thermostat, JWAC |
| **Lubrication System** | Provide oil film to moving parts | Oil pump, oil filters, oil cooler, galleries, oil sump, breather |
| **Exhaust System** | Remove combustion gases | Exhaust manifold, turbocharger turbine, muffler, aftertreatment |
| **Starting System** | Crank engine to start | Electric starter, air starter, hydraulic starter, solenoid |
| **Electrical/Controls** | Monitor and control engine operation | Alternator, battery, ECU/governor, wiring harnesses, relay panels |
| **Cylinder Block/Internals** | Core engine structure and power generation | Cylinder liners, pistons, crankshaft, connecting rods, bearings, rings |
| **Cylinder Head/Valvetrain** | Manage air/fuel intake and exhaust expulsion | Cylinder head, valves, camshaft, rocker arms, push rods, timing gears |
| **Safety/Alarms** | Protect engine from damage | Overspeed trip, high-temp shutdown, low-oil alarm, pressure relief |
| **General/Maintenance** | Multi-system topics | Maintenance intervals, fluid specs, torque specs, troubleshooting flow charts |

---

### Secondary Subsystems (Examples by System)

#### Fuel System
- Fuel Injection
- Fuel Filtration
- Fuel Transfer/Supply Pump
- Fuel Cooler
- Fuel Return

#### Air Intake System
- Turbocharger
- Intercooler (SCAC/JWAC)
- Air Filter
- Intake Manifold
- Boost Control/Governor

#### Cooling System
- Freshwater Circuit
- Seawater Circuit
- Heat Exchanger
- Thermostat
- Water Pump
- Coolant Management

#### Lubrication System
- Oil Pump
- Oil Filters
- Oil Cooler
- Oil Galleries/Distribution
- Oil Sampling/Analysis

#### Exhaust System
- Exhaust Manifold
- Turbocharger Turbine
- Muffler/Silencer
- Aftertreatment (DPF/SCR)
- Exhaust Temperature Control

#### Starting System
- Electric Starter Motor
- Air Start System
- Hydraulic Starter
- Starter Solenoid/Relay
- Starter Components

#### Electrical/Controls
- ECU/Governor
- Sensors (temperature, pressure, speed)
- Wiring Harnesses
- Relay/Switch Panels
- Electrical Troubleshooting

#### Safety/Alarms
- Overspeed Trip
- Temperature Alarms
- Pressure Alarms
- Oil Level/Condition
- Emergency Shutdown

### Cross-Cutting Tags (Apply in Addition to Primary System)

- **Sensors** - Applies to fuel, cooling, lube, air, exhaust, electrical
- **Wiring/Electrical** - Spans multiple systems
- **Safety Systems** - Alarms, trips, shutdowns
- **Gaskets/Seals** - Generic maintenance across systems
- **Fasteners/Hardware** - Bolts, studs, retainers

---

## 2. INDUSTRY STANDARDS REFERENCE

### SMCS Codes (Service, Maintenance, Component System)

**Format:** 9-digit hierarchical code (System-Assembly-Component)

**Engine-specific codes (1000 series):**
- 1001 = Engine general, start, stop
- 1250 = Fuel system
- 1350 = Cooling system
- 1450 = Lubrication system
- 1550 = Air inlet system
- 1650 = Exhaust system
- 1700 = Starting system
- 1800 = Electrical system

**Action:** If your Caterpillar PDFs include SMCS codes, use them to validate your tagging scheme.

### Cat SIS 2.0 Organization

Caterpillar structures service information by:
1. Product configuration (serial number range)
2. System/Group (hierarchical parts lists)
3. Document type (Operation, Service, Troubleshooting, Parts Book)
4. Maintenance interval (500hr, 1000hr, as-needed)

**Insight for your tool:** Mirror this system→assembly→component hierarchy with your primary→secondary subsystem structure.

---

## 3. TAGGING APPROACH: KEYWORD-ASSISTED MANUAL

### Why Not ML/NLP?

- Only 62 documents - overkill
- Requires 100+ tagged documents per category for training
- Complexity not justified for single-user tool
- Keyword-assisted manual tagging: 70-80% automation, 20-30% human judgment

### Phase 1: Initial Setup (5-6 hours)

#### Step 1a: Define Taxonomy (2 hours)
- Customize secondary subsystems based on your 62 PDFs
- Example: If you have 3 cooling docs and 2 lube docs, tag them "Cooling System" without splitting into freshwater/seawater
- Start with broad categories; split only if you have 5+ docs per subsystem

#### Step 1b: Build Keyword Dictionary (2 hours)

Create mapping of technical terms → systems:

```python
keywords = {
    'Fuel System': [
        'injector', 'fuel pump', 'fuel filter', 'fuel rack', 'fuel pressure',
        'fuel line', 'fuel nozzle', 'fuel cooler', 'meui', 'heui', 'common rail',
        'fuel transfer', 'fuel supply', 'fuel return'
    ],
    'Air Intake System': [
        'turbocharger', 'turbo', 'aftercooler', 'scac', 'jwac', 'intercooler',
        'air filter', 'intake manifold', 'boost pressure', 'boost', 'compressor',
        'charge air'
    ],
    'Cooling System': [
        'coolant', 'radiator', 'heat exchanger', 'thermostat', 'water pump',
        'freshwater', 'seawater', 'coolant temp', 'overheating', 'jacket water'
    ],
    'Lubrication System': [
        'oil pump', 'oil filter', 'oil cooler', 'lube oil', 'lubricating oil',
        'oil pressure', 'oil gallery', 'bearings', 'oil analysis', 'oil sampling'
    ],
    'Exhaust System': [
        'exhaust manifold', 'turbo turbine', 'muffler', 'silencer', 'exhaust gas',
        'scr', 'dpf', 'aftertreatment', 'exhaust temperature'
    ],
    'Starting System': [
        'starter motor', 'starter', 'air start', 'hydraulic start', 'solenoid',
        'cranking', 'starting torque'
    ],
    'Electrical/Controls': [
        'ecu', 'governor', 'sensor', 'wiring', 'alternator', 'battery', 'relay',
        'switch', 'electrical', 'harness', 'connector', 'diagnostic'
    ],
    'Cylinder Block/Internals': [
        'piston', 'crankshaft', 'connecting rod', 'bearing', 'cylinder liner',
        'ring', 'block', 'bore', 'stroke'
    ],
    'Cylinder Head/Valvetrain': [
        'cylinder head', 'valve', 'camshaft', 'rocker arm', 'push rod',
        'timing gear', 'valve train', 'valve timing'
    ],
    'Safety/Alarms': [
        'overspeed', 'trip', 'shutdown', 'alarm', 'high temp', 'low oil',
        'low pressure', 'emergency', 'safety', 'protective'
    ],
    'Sensors': [
        'sensor', 'temperature sensor', 'pressure sensor', 'speed sensor',
        'flow sensor', 'load cell'
    ],
    'Wiring/Electrical': [
        'wire', 'wiring', 'harness', 'connector', 'terminal', 'cable',
        'electrical', 'circuit'
    ]
}
```

**Action:** Expand/refine based on your PDF content. Extract 1-2 sample PDFs and see what terms appear.

#### Step 1c: Create Tagging Interface (4 hours)

Simple Flask form or Python script:

```python
# simple_tagger.py
import os
import json
from pathlib import Path

class DocTagger:
    def __init__(self, docs_dir, keywords_file):
        self.docs = sorted([f for f in os.listdir(docs_dir) if f.endswith('.pdf')])
        with open(keywords_file) as f:
            self.keywords = json.load(f)
        self.tags_file = 'document_tags.json'
        self.load_tags()

    def suggest_tags(self, text):
        """Scan text for keyword matches, return suggested tags"""
        suggestions = {}
        for system, terms in self.keywords.items():
            matches = sum(1 for term in terms if term in text.lower())
            if matches > 0:
                suggestions[system] = matches
        return sorted(suggestions.items(), key=lambda x: x[1], reverse=True)

    def load_tags(self):
        """Load existing tags from JSON"""
        if os.path.exists(self.tags_file):
            with open(self.tags_file) as f:
                self.tags = json.load(f)
        else:
            self.tags = {}

    def save_tags(self):
        """Save tags to JSON"""
        with open(self.tags_file, 'w') as f:
            json.dump(self.tags, f, indent=2)

# CLI interface
def main():
    tagger = DocTagger('pdfs', 'keywords.json')

    for pdf in tagger.docs:
        if pdf in tagger.tags:
            print(f"[DONE] {pdf} - tags: {tagger.tags[pdf]}")
            continue

        print(f"\n{'='*60}")
        print(f"PDF: {pdf}")
        print(f"{'='*60}")

        # Extract text from PDF (use PyPDF2 or pdfplumber)
        # text = extract_text(f'pdfs/{pdf}')
        # suggestions = tagger.suggest_tags(text)

        # Mock for demo
        suggestions = [('Fuel System', 15), ('Electrical/Controls', 3)]
        print(f"Suggested tags: {[s[0] for s in suggestions]}")

        user_input = input("Enter tags (comma-separated) or press Enter to accept: ").strip()

        if user_input:
            tags = [t.strip() for t in user_input.split(',')]
        else:
            tags = [s[0] for s in suggestions]

        tagger.tags[pdf] = tags
        tagger.save_tags()
        print(f"Saved: {tags}")

if __name__ == '__main__':
    main()
```

---

### Phase 2: Manual Tagging (10 hours)

**Timeline:** ~5 min per document average

1. **Run keyword scanner** on all 62 PDFs
2. **Review suggestions** for each PDF
3. **Accept/reject/modify** tags based on context
4. **Handle edge cases:**
   - Multi-system documents → Use multiple tags
   - Ambiguous terms → Add context note
   - Documents you're unsure about → Mark "flag for review"

**Target:** 2-4 tags per document on average

---

## 4. MULTI-LABEL TAGGING APPROACH

### Why Multi-Label?

Technical documents frequently span multiple systems:

| Document Topic | Tags |
|---|---|
| Fuel pressure sensor wiring | Fuel System, Sensors, Electrical/Controls |
| Turbocharger oil supply | Air Intake, Lubrication, Wiring/Electrical |
| High-temperature shutdown alarm | Cooling, Safety/Alarms, Electrical/Controls |
| Coolant flow in aftercooler | Cooling, Air Intake |
| Crankshaft bearing failure analysis | Cylinder Block/Internals, Lubrication, General/Maintenance |

### Hierarchical Structure

```
Level 1 (Primary):    Fuel System
Level 2 (Secondary):  Fuel Injection
Level 3 (Component):  Injector Nozzle
Cross-Reference Tags: Sensors, Electrical/Controls
```

---

## 5. SQLITE SCHEMA

### Core Tables

```sql
-- Main document table (existing)
CREATE TABLE documents (
    doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT UNIQUE NOT NULL,
    equipment_type TEXT NOT NULL,  -- 3516, C18, C32, C4.4
    doc_type TEXT NOT NULL,        -- troubleshooting, O&M, schematic, etc.
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    content_hash TEXT              -- for deduplication
);

-- Tag definitions
CREATE TABLE tags (
    tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_name TEXT UNIQUE NOT NULL,
    tag_category TEXT NOT NULL,    -- 'system', 'subsystem', 'cross_cutting'
    parent_tag_id INTEGER,         -- for hierarchy (subsystem links to system)
    description TEXT,
    FOREIGN KEY (parent_tag_id) REFERENCES tags(tag_id)
);

-- Document-to-tag junction table (multi-label)
CREATE TABLE document_tags (
    doc_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    tag_weight REAL DEFAULT 1.0,   -- importance: 1.0 = primary, 0.5 = mentioned
    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (doc_id, tag_id),
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(tag_id) ON DELETE CASCADE
);

-- Full-text search virtual table
CREATE VIRTUAL TABLE documents_fts USING fts5(
    content,
    content=documents,
    content_rowid=doc_id
);
```

### Indexes for Fast Queries

```sql
CREATE INDEX idx_doc_equipment ON documents(equipment_type);
CREATE INDEX idx_doc_type ON documents(doc_type);
CREATE INDEX idx_tags_category ON tags(tag_category);
CREATE INDEX idx_doc_tags_tag ON document_tags(tag_id);
CREATE INDEX idx_doc_tags_doc ON document_tags(doc_id);
```

### Seed Tag Data

```sql
-- Primary systems
INSERT INTO tags (tag_name, tag_category, description) VALUES
    ('Fuel System', 'system', 'Fuel delivery, injection, filtration'),
    ('Air Intake System', 'system', 'Air filtration, turbocharging, boost control'),
    ('Cooling System', 'system', 'Thermal management via water/seawater circuits'),
    ('Lubrication System', 'system', 'Oil supply, cooling, cleaning'),
    ('Exhaust System', 'system', 'Combustion gas expulsion'),
    ('Starting System', 'system', 'Engine cranking and starting'),
    ('Electrical/Controls', 'system', 'ECU, governor, sensors, alternator'),
    ('Cylinder Block/Internals', 'system', 'Pistons, crankshaft, bearings'),
    ('Cylinder Head/Valvetrain', 'system', 'Valves, camshaft, timing'),
    ('Safety/Alarms', 'system', 'Protective shutdowns and alerts'),
    ('General/Maintenance', 'system', 'Multi-system, specs, intervals');

-- Cross-cutting tags
INSERT INTO tags (tag_name, tag_category, description) VALUES
    ('Sensors', 'cross_cutting', 'Temperature, pressure, speed sensors'),
    ('Wiring/Electrical', 'cross_cutting', 'Harnesses, connectors, wiring'),
    ('Gaskets/Seals', 'cross_cutting', 'Sealing components across systems'),
    ('Fasteners/Hardware', 'cross_cutting', 'Bolts, studs, retainers');
```

---

## 6. QUERY PATTERNS

### Filter by System (Checkbox Search)

```python
# Flask route example
@app.route('/search')
def search():
    query = request.args.get('q', '')
    equipment = request.args.get('equipment', '')
    systems = request.args.getlist('system')  # multiple checkboxes

    sql = """
        SELECT DISTINCT d.*
        FROM documents d
        JOIN documents_fts fts ON d.doc_id = fts.rowid
        LEFT JOIN document_tags dt ON d.doc_id = dt.doc_id
        LEFT JOIN tags t ON dt.tag_id = t.tag_id
        WHERE fts.content MATCH ?
    """
    params = [query]

    if equipment:
        sql += " AND d.equipment_type = ?"
        params.append(equipment)

    if systems:
        placeholders = ','.join('?' * len(systems))
        sql += f" AND t.tag_name IN ({placeholders})"
        params.extend(systems)

    sql += " ORDER BY rank, d.upload_date DESC"

    results = db.execute(sql, params).fetchall()
    return jsonify(results)
```

### Get Tag Counts (Faceted Search)

```python
def get_tag_facets(equipment=None):
    """Return count of documents per tag for current filters"""
    sql = """
        SELECT t.tag_id, t.tag_name, t.tag_category, COUNT(DISTINCT d.doc_id) as count
        FROM tags t
        JOIN document_tags dt ON t.tag_id = dt.tag_id
        JOIN documents d ON dt.doc_id = d.doc_id
        WHERE t.tag_category = 'system'
    """
    params = []

    if equipment:
        sql += " AND d.equipment_type = ?"
        params.append(equipment)

    sql += " GROUP BY t.tag_id ORDER BY count DESC"

    return db.execute(sql, params).fetchall()
```

### Combined Full-Text + Tag Filter

```sql
SELECT d.*,
       COUNT(DISTINCT dt.tag_id) as tag_count,
       GROUP_CONCAT(t.tag_name, ', ') as tags
FROM documents_fts fts
JOIN documents d ON fts.rowid = d.doc_id
LEFT JOIN document_tags dt ON d.doc_id = dt.doc_id
LEFT JOIN tags t ON dt.tag_id = t.tag_id
WHERE fts.content MATCH 'overheating OR high temperature'
  AND d.equipment_type = 'C18'
  AND t.tag_name = 'Cooling System'
GROUP BY d.doc_id
ORDER BY rank DESC;
```

---

## 7. UI PATTERNS FOR FILTERING

### Pattern 1: Checkbox List (Recommended for 10-12 systems)

```html
<form id="search-form">
    <h3>Filter by System</h3>

    <label><input type="checkbox" name="system" value="Fuel System">
        Fuel System (18)</label>

    <label><input type="checkbox" name="system" value="Cooling System" checked>
        Cooling System (12)</label>

    <label><input type="checkbox" name="system" value="Air Intake System">
        Air Intake System (15)</label>

    <label><input type="checkbox" name="system" value="Electrical/Controls">
        Electrical/Controls (8)</label>

    <details>
        <summary>Show more systems...</summary>
        <label><input type="checkbox" name="system" value="Lubrication System">
            Lubrication System (10)</label>
        <!-- etc -->
    </details>

    <button type="submit">Search</button>
    <button type="reset">Clear Filters</button>
</form>
```

### Pattern 2: Tree View (For hierarchical navigation)

```html
<details>
    <summary>Cooling System (12 docs)</summary>
    <ul>
        <li><label><input type="checkbox" name="subsystem" value="Freshwater">
            Freshwater Circuit (5)</label></li>
        <li><label><input type="checkbox" name="subsystem" value="Seawater">
            Seawater Circuit (4)</label></li>
        <li><label><input type="checkbox" name="subsystem" value="Heat Exchanger">
            Heat Exchanger (3)</label></li>
    </ul>
</details>
```

### Pattern 3: Tag Cloud (Visual overview)

```html
<div class="tag-cloud">
    <span class="tag-large">Fuel System (18)</span>
    <span class="tag-large">Cooling System (12)</span>
    <span class="tag-medium">Air Intake (15)</span>
    <span class="tag-medium">Electrical/Controls (8)</span>
    <span class="tag-small">Sensors (4)</span>
</div>
```

---

## 8. IMPLEMENTATION TIMELINE

| Phase | Task | Time | Deliverable |
|-------|------|------|-------------|
| 1a | Define taxonomy | 2 hrs | List of 10-12 systems + 20-30 subsystems |
| 1b | Build keyword dictionary | 2 hrs | `keywords.json` with 200-300 terms |
| 1c | Create tagging interface | 4 hrs | `simple_tagger.py` script + manual tagger |
| 2 | Manual tagging (62 docs) | 10 hrs | `document_tags.json` with all tags |
| 3 | SQLite schema + seed data | 2 hrs | Database with tags table populated |
| 4 | Implement filter queries | 3 hrs | Flask routes for tag-based filtering |
| 5 | UI for checkboxes | 3 hrs | Frontend filter form + results integration |
| **Total** | | **26 hrs** | Production-ready subsystem search |

---

## 9. VALIDATION CHECKLIST

After implementation, verify:

- [ ] "Show me all C18 fuel system documents" returns injector, pump, filter docs
- [ ] "Show me cooling problems" + cooling filter returns overheating, thermostat, heat exchanger docs
- [ ] Search "high temperature" + filter by Cooling narrows results correctly
- [ ] Multi-system documents appear in all relevant filtered searches
- [ ] Tag counts in filter facets match actual document counts
- [ ] No documents tagged "General/Maintenance" unless truly multi-system
- [ ] Equipment type filter AND system filter work together
- [ ] Full-text search still works alongside tag filters

---

## 10. FUTURE ENHANCEMENTS (Out of Scope)

**Don't implement now, but consider for future:**

- Maintenance interval tags (500hr, 1000hr)
- Failure mode tags (leak, blockage, wear)
- Urgency tags (critical, routine)
- Related equipment tags (generator, transmission)
- SMCS code mapping (if CAT PDFs include them)
- Auto-tagging via ML (when you reach 100+ docs)
- Tag synonym expansion ("turbo" = "turbocharger")

---

## 11. REFERENCE: CATERPILLAR TERMINOLOGY

**Common acronyms in your PDFs:**

- **MEUI** = Mechanically Actuated, Electronically Controlled Unit Injector (older)
- **HEUI** = Hydraulically Actuated, Electronically Controlled Unit Injector (modern)
- **JWAC** = Jacket Water Aftercooler (freshwater to charge air)
- **SCAC** = Seawater Charge Air Cooler (seawater to charge air)
- **ECU** = Engine Control Unit (electronic governor)
- **ECM** = Engine Control Module (same as ECU)
- **EFI** = Electronic Fuel Injection
- **SCR** = Selective Catalytic Reduction (emissions)
- **DPF** = Diesel Particulate Filter (emissions)
- **OBD** = Onboard Diagnostics

**Map these to subsystems:**
- MEUI/HEUI → Fuel System → Fuel Injection
- JWAC/SCAC → Cooling System (or Air Intake, depending on emphasis)
- ECU/ECM → Electrical/Controls → Governor/Controls
- SCR/DPF → Exhaust System → Aftertreatment

---

## 12. SAMPLE TAGGED DOCUMENTS

**Example assignments for reference:**

| Filename | Equipment | Doc Type | Primary Tags | Secondary Tags |
|----------|-----------|----------|--------------|-----------------|
| C18_HEUI_Service_Guide.pdf | C18 | Service | Fuel System, Electrical/Controls | Sensors, Wiring/Electrical |
| 3516_Cooling_OandM.pdf | 3516 | O&M | Cooling System | General/Maintenance |
| C32_Turbo_Troubleshooting.pdf | C32 | Troubleshooting | Air Intake System, Cooling System | - |
| Lube_Oil_Analysis_Guide.pdf | All | General | Lubrication System | General/Maintenance |
| Overspeed_Trip_Install.pdf | All | Service | Safety/Alarms, Electrical/Controls | Sensors, Wiring/Electrical |
| Cylinder_Head_Rebuild.pdf | C4.4 | Service | Cylinder Head/Valvetrain | Gaskets/Seals, Fasteners/Hardware |
| Aftercooler_Blockage_Diagnosis.pdf | C18 | Troubleshooting | Air Intake System, Cooling System | Sensors |
| Fuel_Filter_Change_500hr.pdf | All | O&M | Fuel System | General/Maintenance |

---

**Questions? Start with Phase 1a - define your taxonomy based on the 62 PDFs you already have.**
