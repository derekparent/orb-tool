# CAT Parts Integration Research Report
## Programmatic Parts Lookup for Marine Diesel Engine Troubleshooting App
### Caterpillar 3516, C18, C32 Engines

**Date:** February 8, 2026  
**Author:** Research Compilation  
**Scope:** API access, parts lookup integration, and alternative approaches for a Flask-based LLM troubleshooting assistant

---

## Executive Summary

Caterpillar does **not** offer a public REST API for parts search, pricing, or availability lookup through SIS2 or parts.cat.com. However, several viable integration paths exist, ranging from official B2B channels (Cat Integrated Procurement) to practical hybrid approaches that combine local part-number extraction from your indexed manuals with deep-linking into Cat's web platforms. This report evaluates each option on feasibility, legal risk, cost, complexity, and data quality.

**Recommended Path:** Build a local CAT part number database extracted from your indexed PDF manuals using regex, enrich it with metadata, and implement one-click deep-links to `parts.cat.com` for real-time pricing and availability — supplemented by the SIS2 CSV/XML export workflow for bulk operations.

---

## 1. CAT SIS2 (sis2.cat.com)

### 1.1 API Availability

**No public or partner API exists for SIS2.** SIS 2.0 is a cloud-based web application (launched May 2021, replacing SIS Web) that requires a paid subscription and browser-based authentication. It is built as a single-page application with internal API calls, but these are:

- Not documented publicly
- Protected behind authentication (CWS ID)
- Subject to the SIS End User License Agreement (EULA) which prohibits reverse engineering, automated access, and data extraction

### 1.2 Data Available in SIS2

SIS2 is the most comprehensive Cat parts and service data source, containing:

| Data Type | Available | Notes |
|---|---|---|
| Part numbers | ✅ | 1.5 million+ part numbers |
| Parts diagrams/graphics | ✅ | 2 million+ service graphics |
| Service documents | ✅ | 44,000+ documents |
| Serial number lookup | ✅ | Products from 1977 to present |
| Part pricing | ✅ | Dealer-specific, shown in cart |
| Part availability | ✅ | Dealer-specific, shown in cart |
| Supersession info | ✅ | Shown when searching old part numbers |
| Service bulletins | ✅ | Included in service documents |
| SMCS codes | ✅ | Filterable in search results |
| Planned maintenance kits | ✅ | One-click access for PM info |

### 1.3 Data Export Capabilities

SIS2 provides **limited manual export** functionality:

- **Shopping Cart → CSV export**: You can export your parts list as CSV (part numbers, quantities, pricing)
- **Shopping Cart → XML export**: Alternative structured format for parts lists
- **Shopping Cart → Print/PDF**: Physical or PDF copy of cart contents
- **Import from Excel**: Upload CSV files with part numbers into the shopping cart
- **No bulk data download**: You cannot export the entire parts database or diagrams

### 1.4 URL Structure

SIS2 uses a single-page application architecture at `sis2.cat.com`. After authentication, navigation happens via internal routing. Observed patterns:

```
sis2.cat.com/                          # Home/login
sis2.cat.com/#/                        # Main interface after auth
```

The application uses prefix/serial number-based navigation internally. **Deep-linking to specific parts or diagrams from outside SIS2 is not reliably supported** due to the SPA architecture and session-based authentication.

### 1.5 Third-Party Tools and Scrapers

- **SIS2GO App**: Official mobile companion app (iOS, Android, Windows) — free with SIS subscription
- **SIS USB offline option**: Available for $1,500 + subscription cost, allows offline access
- No known legitimate Chrome extensions or third-party tools that interact with SIS2
- No known open-source projects that integrate with SIS2

### 1.6 Terms of Service — Automated Access

The SIS EULA (November 4, 2024) and Acceptable Use Policy **explicitly prohibit**:

> *"Use any robot, spider, site search/retrieval application or other manual or automatic device, or other method or technology to extract or otherwise collect any information from the Digital Offering... for the purposes of creating, training, or improving any computer, machine learning, deep learning, AI system, AI models, software, database, or other algorithmic models without Caterpillar's express prior written consent."*

Additional prohibitions include:
- Systematic downloading of Digital Offering Information
- Reverse engineering, decompiling, or disassembling
- Framing or mirroring any portion of the Digital Offering
- Reproducing, modifying, or creating derivative works without written consent
- Using data for benefit of third parties

**Violations result in:** Immediate suspension/termination of subscription, mandatory binding arbitration (AAA, New York law), indemnification obligations.

---

## 2. CATPARTS.com / parts.cat.com

### 2.1 API Availability

**No public API for parts.cat.com.** The eCommerce platform is a dealer-connected web store with session-based authentication. It does not expose REST, SOAP, or GraphQL endpoints for external consumption.

### 2.2 URL Structure and Deep-Linking

parts.cat.com uses dealer-specific routing:

```
parts.cat.com/en/catcorp                        # Main store (generic corporate)
parts.cat.com/en/catcorp/parts-diagram          # Parts diagram lookup by serial number
parts.cat.com/en/catcorp/shop-all-categories    # Browse by category
parts.cat.com/en/catcorp/myequipment            # Saved equipment/serial numbers
```

**Deep-linking to a specific part number search is partially possible.** While the site doesn't have a clean `?q=PARTNUMBER` parameter in the URL, you can construct links like:

```
https://parts.cat.com/en/catcorp/search?searchTerm=XXX-XXXX
```

However, this requires the user to be authenticated to see pricing and availability. **The most practical approach is to link users to parts.cat.com and have them search from there**, since authentication state cannot be programmatically controlled.

### 2.3 CSV Import for Bulk Orders

parts.cat.com supports a **Quick Order** feature that accepts CSV uploads:

- First column: `Quantity`
- Second column: `Part Number`
- Up to 180 part numbers per upload

This means your app could **generate a CSV file** of identified part numbers that the engineer can download and upload to parts.cat.com for instant cart population.

---

## 3. CAT Dealer/Partner APIs

### 3.1 Cat Integrated Procurement (Cat IP) — B2B/EDI

This is the **closest thing to an official parts ordering API** that Caterpillar offers.

| Feature | Details |
|---|---|
| Protocol | XML over HTTPS |
| Integration Type | Punchout/OCI RoundTrip, EDI |
| Supported Transactions | Price requests, PO generation, order acknowledgments, invoices, shipping notices |
| Data Access | Real-time pricing, availability, 1M+ Cat parts |
| SIS Integration | Includes PM checklists and SIS information |
| Target Users | High-volume parts buyers with procurement systems |
| Requirements | Business procurement system that sends/receives XML via HTTPS |

**Key Considerations:**
- Designed for enterprise procurement systems (SAP, Oracle, etc.), not lightweight web apps
- Requires dealer relationship setup and onboarding
- Transaction costs reportedly reduced by 50%+ for large customers
- Your Flask app would need to implement XML document exchange

**Feasibility for your use case:** Medium. You would need to work with your Cat dealer to explore whether a smaller-scale integration is possible. Cat IP is designed for high-volume buyers, so a single-vessel or small-fleet operation may not qualify. However, contacting your dealer about Cat IP access is the first step.

### 3.2 CPC (Caterpillar Product Content) API — cpc.cat.com

A **legitimate REST API exists** at `cpc.cat.com` for Caterpillar Product Content:

| Feature | Details |
|---|---|
| API Versions | V2 (XML), V3 (OpenAPI/Swagger) |
| Response Formats | JSON (default), XML |
| Authentication | Token-based (migrating to Microsoft Entra ID) |
| Data Domains | Trees, Sales Channels, Groups & Products |
| Pagination | V3 supports offset/limit parameters |
| Date Filtering | V3 supports ISO date parameter for modified-after queries |

**However:** The CPC API provides **product catalog/marketing content** — not parts pricing, availability, or ordering data. It covers product classifications, sales channel information, and product groupings. It would be useful for building a product taxonomy but not for parts lookup.

### 3.3 AEMP 2.0 / ISO 15143-3 API

Caterpillar offers a **telematics data API** following the ISO 15143-3 standard:

- One-time fee for API access (up to 10,000 calls/day)
- Data types: location, operating hours, fuel consumption, fault codes, diagnostic trouble codes (DTCs)
- Requires active Product Link subscription (ConnectPro, TrackPro, or equivalent)
- Supported by Geotab, Samsara, and other fleet management platforms

**Not useful for parts lookup.** This API provides operational/telematics data, not parts information. However, the fault code data (DTCs) could be interesting for your troubleshooting app — correlating engine fault codes with repair procedures.

### 3.4 Cat Digital Marketplace (digital.cat.com)

Caterpillar's digital ecosystem hub that provides:
- Visibility to Cat and dealer applications
- API subscriptions for business system integration
- Reusable components with pre-built functionality
- Developer collaboration forum

As of 2025, Caterpillar has adopted an "AI First" approach through its Helios platform, with generative AI-powered service recommendations and a library of AI agents. While this suggests Caterpillar is building more digital/API capabilities, **public parts-data APIs are not currently available** through the marketplace.

**Recommendation:** Register on digital.cat.com and explore what's available. The ecosystem is evolving, and parts-related APIs may appear as Caterpillar continues its digital transformation.

### 3.5 VisionLink API

Telematics/fleet management API — similar to AEMP 2.0 but Caterpillar-specific. Provides equipment monitoring data, not parts data.

---

## 4. Alternative Approaches

### 4.1 Local Part Number Database from Indexed Manuals

**This is the highest-value, lowest-risk approach for your specific use case.**

Since you've already indexed CAT engine manuals for the 3516, C18, and C32 engines, you can extract all part numbers using regex and build a local lookup database.

#### CAT Part Number Formats

| Format | Pattern | Regex | Example | Era |
|---|---|---|---|---|
| New (current) | NNN-NNNN | `\b\d{3}-\d{4}\b` | 230-5743, 420-0751 | ~1990s–present |
| Old (legacy) | XANNNN | `\b\d[A-Z]\d{4}\b` | 1B2345, 9Y9999 | Pre-1990s |
| Old with leading zeros | 0X0NNN | `\b0[A-Z]0\d{3}\b` | 0V0272, 0T0772 | Converted legacy |

**Combined regex for extraction:**
```python
import re

# Match both old and new CAT part number formats
CAT_PART_REGEX = re.compile(
    r'\b(\d{3}-\d{4})\b'          # New format: 230-5743
    r'|\b(\d[A-Z]\d{4})\b'        # Old format: 1B2345
    r'|\b(0[A-Z]0\d{3})\b'        # Converted legacy: 0V0272
)
```

For modern 3516, C18, and C32 engines, **virtually all part numbers will be in the NNN-NNNN format**.

#### Building the Database

```python
# Pseudo-code for extracting parts from indexed manuals
import re
import json

CAT_PART_PATTERN = re.compile(r'\b(\d{3}-\d{4})\b')

def extract_parts_from_manual(text_chunks):
    """Extract part numbers with context from indexed manual chunks."""
    parts_db = {}
    for chunk in text_chunks:
        matches = CAT_PART_PATTERN.findall(chunk['text'])
        for part_num in matches:
            if part_num not in parts_db:
                parts_db[part_num] = {
                    'part_number': part_num,
                    'contexts': [],
                    'engines': set(),
                    'categories': set()
                }
            parts_db[part_num]['contexts'].append({
                'source': chunk['source_file'],
                'page': chunk.get('page'),
                'surrounding_text': chunk['text'][:200]
            })
    return parts_db
```

#### Data Enrichment

Once you have part numbers extracted, enrich with:
1. **Context classification**: Use the LLM to categorize each part (filter, gasket, bearing, sensor, etc.) based on surrounding text
2. **Engine applicability**: Track which engine model(s) each part appears in
3. **Procedure association**: Link parts to specific repair/maintenance procedures
4. **Supersession notes**: Flag parts that may need verification (older manuals)

### 4.2 Deep-Link Strategy for One-Click Availability Check

The most practical "one-click" approach:

```python
def generate_parts_cat_link(part_number):
    """Generate a deep link to parts.cat.com for a specific part."""
    # Clean the part number
    clean_pn = part_number.strip().replace(' ', '')
    # Construct the search URL
    return f"https://parts.cat.com/en/catcorp/search?searchTerm={clean_pn}"

def generate_sis2_link():
    """Link to SIS2 homepage (user must be authenticated)."""
    return "https://sis2.cat.com"

def generate_availability_response(part_number, context=""):
    """Generate LLM response with part lookup links."""
    pcc_link = generate_parts_cat_link(part_number)
    return {
        'part_number': part_number,
        'context': context,
        'actions': [
            {
                'label': f'Check Availability: {part_number}',
                'url': pcc_link,
                'type': 'parts_cat_com'
            },
            {
                'label': 'Open SIS2 for Full Diagram',
                'url': 'https://sis2.cat.com',
                'type': 'sis2'
            },
            {
                'label': 'Cat Filter Cross-Reference',
                'url': 'https://www.catfiltercrossreference.com/',
                'type': 'filter_xref'
            }
        ]
    }
```

### 4.3 CSV Export Workflow

For bulk parts ordering from repair procedures:

```python
import csv
import io

def generate_parts_csv(parts_list):
    """Generate a CSV file compatible with parts.cat.com Quick Order."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Quantity', 'Part Number'])
    for part in parts_list:
        writer.writerow([part.get('quantity', 1), part['part_number']])
    return output.getvalue()
```

The engineer can download this CSV and upload it directly to parts.cat.com's Quick Order feature (supports up to 180 part numbers per upload).

### 4.4 Aftermarket Supplier Cross-Reference

No robust third-party API for CAT heavy equipment parts was identified. However:

| Supplier | API? | Notes |
|---|---|---|
| AGA Parts (aga-parts.com) | ❌ | Online catalog, no API |
| IPD Parts (ipdparts.com) | ❌ | Aftermarket Cat engine parts, no API |
| AMS Parts (amsparts.com) | ❌ | New, used, rebuilt — phone-based |
| Highway & Heavy Parts | ❌ | Aftermarket Cat specialist, no API |
| tractorparts.com | ❌ | Has cross-reference database (web-based lookup) |
| EquipmentWatch | Paid API | Equipment specs/values, not parts |
| HeavyEquipmentData.com | Paid API | Equipment specifications, not parts numbers |
| TecDoc | Paid API | Automotive aftermarket — not heavy equipment |

**For marine-specific CAT parts**, consider contacting:
- Your local Cat marine dealer directly about Cat IP eligibility
- Marine-specific aftermarket suppliers who may offer EDI/API integration

### 4.5 Scraping Approaches — Legal and Technical Assessment

#### Technical Feasibility

Using Playwright/Puppeteer against an authenticated SIS2 session is technically possible:
- SIS2 runs in Chromium-based browsers (Chrome, Edge, Safari)
- Session cookies could be maintained by a headless browser
- Parts data, pricing, and availability could be scraped from the DOM

#### Legal Risk: **EXTREMELY HIGH**

The SIS EULA and Caterpillar Acceptable Use Policy explicitly prohibit:

1. **Automated access**: "Use any robot, spider... or other manual or automatic device... to extract or otherwise collect any information"
2. **Data extraction for AI/databases**: "...for the purposes of creating, training, or improving any computer, machine learning, deep learning, AI system, AI models, software, database, or other algorithmic models"
3. **Systematic downloading**: "Except as expressly authorized herein, systematically download and store Digital Offering Information"
4. **Reverse engineering**: "Reverse engineer, decompile, or disassemble"

**Consequences:**
- Immediate termination of SIS subscription
- Loss of access to ALL Caterpillar digital offerings
- Potential legal action (binding arbitration, attorney fees)
- Damage to dealer relationship
- **As a marine chief engineer, losing SIS access would be operationally devastating**

**Recommendation: Do NOT scrape SIS2 or parts.cat.com.** The risk far outweighs any benefit, especially when legitimate alternatives exist.

---

## 5. Part Number Extraction from Manuals

### 5.1 Standard CAT Part Number Format

For the 3516, C18, and C32 marine engines, part numbers follow the **NNN-NNNN** format (3 digits, hyphen, 4 digits). Examples from these engine families:

- Fuel filters: 1R-xxxx series (e.g., 1R-0751, 1R-0749)
- Oil filters: 1R-xxxx series
- Air filters: Various series
- Gaskets, seals, bearings: Various NNN-NNNN patterns

### 5.2 Part Number Currency and Supersession

| Concern | Reality | Mitigation |
|---|---|---|
| Manual age | Part numbers from manuals 5+ years old may be superseded | Flag and note manual publication date |
| Supersession rate | Common for filters, gaskets, seals; less for major components | parts.cat.com will show current part number when old one is searched |
| Cross-reference | Old part numbers generally forward-resolve on Cat systems | Include note: "Verify current part number on parts.cat.com" |
| Price changes | Manual prices are always stale | Never cache prices; always link to live system |

**Key insight:** When you enter a superseded part number on parts.cat.com, the system typically shows the supersession and redirects to the current part number. This means your local database doesn't need to track supersessions — parts.cat.com handles it.

### 5.3 Supersession Checking

There is no standalone API or tool to check supersessions programmatically. Options:
1. **parts.cat.com manual check**: Enter old part number, system shows if superseded
2. **SIS2 manual check**: Search by part number shows current status
3. **Dealer inquiry**: Call or email your Cat dealer's parts department
4. **Cat filter cross-reference tool**: For filters specifically, catfiltercrossreference.com provides cross-reference data

---

## 6. What Others Have Built

### 6.1 Open-Source Projects

No open-source projects were found that directly integrate with CAT SIS2 or parts.cat.com. The closest related projects:

- **PartPilot** (GitHub): Open-source electronics parts management tool with LCSC integration — not CAT-specific but architecturally relevant
- **CaterpillarInc** (GitHub): Caterpillar's official GitHub has some public repos, but none related to SIS or parts APIs

### 6.2 How Independent Dealers Handle Parts Lookup

Based on community discussions and dealer documentation:

1. **Cat IP (B2B/EDI)**: Large dealers and fleet operators use Cat Integrated Procurement for XML-based ordering
2. **SIS2 + parts.cat.com manual workflow**: Most users follow the SIS2 → shopping cart → parts.cat.com flow
3. **Phone/email**: Many independent operators still call their dealer's parts counter
4. **Custom spreadsheets**: Some shops maintain Excel sheets of frequently ordered parts with part numbers

### 6.3 Community Resources

- **Heavy Equipment Forums** (heavyequipmentforums.com): Active discussion of CAT part numbering, supersession tracking
- **ACMOC Forum** (acmoc.org): Antique Caterpillar Machinery Owners Club — historical part number discussions
- **Cat Forum** (catmbr.org): General Caterpillar community discussions
- No dedicated CAT parts API developer community exists

---

## 7. Approach Comparison Matrix

| Approach | Feasibility (1-10) | Legal/TOS Risk | Cost | Implementation Complexity | Data Quality/Freshness |
|---|---|---|---|---|---|
| **Local part DB + deep links** | **9** | **None** | **$0** | **Low-Medium** | **Good (manual-sourced, verify on PCC)** |
| CSV export to parts.cat.com | 8 | None | $0 | Low | Excellent (live data on PCC) |
| Cat IP (B2B/EDI) | 5 | None (official) | $$-$$$ | High | Excellent (real-time) |
| CPC API for product catalog | 6 | Low (official) | $-$$ | Medium | Good (catalog data) |
| Cat Digital Marketplace | 4 | None | Unknown | Unknown | Unknown (evolving) |
| Aftermarket supplier APIs | 3 | None | Varies | Medium | Variable |
| SIS2 scraping (Playwright) | 7 (technically) | **EXTREME** | $0 | Medium | Excellent |
| Reverse-engineer SIS2 API | 6 (technically) | **EXTREME** | $0 | High | Excellent |
| Manual SIS2 export workflow | 8 | None | $0 (with SIS sub) | Low | Excellent |

---

## 8. Recommended Implementation Plan

### Phase 1: Part Number Extraction & Local Database (Week 1-2)

1. **Extract all part numbers** from your indexed 3516, C18, and C32 manuals using the NNN-NNNN regex
2. **Build a SQLite/PostgreSQL table** with: part_number, engine_model, category, source_document, page_reference, surrounding_context
3. **Use your LLM** to classify parts (filter, gasket, seal, sensor, etc.) from context
4. **Create a parts lookup function** that the LLM agent can call during troubleshooting conversations

### Phase 2: One-Click Availability Links (Week 2-3)

1. **Implement deep-link generation** to parts.cat.com search: `https://parts.cat.com/en/catcorp/search?searchTerm={part_number}`
2. **Add action buttons** in your chat interface: "Check Availability on parts.cat.com", "Open in SIS2", "View Filter Cross-Reference"
3. **Generate downloadable CSV** when multiple parts are identified (compatible with parts.cat.com Quick Order)
4. **Include disclaimer**: "Prices and availability shown on parts.cat.com. Part numbers sourced from [manual name/date]. Verify current part number with your dealer."

### Phase 3: Enhanced LLM Integration (Week 3-4)

1. **Tool/function calling**: Add a `lookup_part` tool to your LLM agent that:
   - Searches the local parts database
   - Returns part number, description, category, applicable engines
   - Generates parts.cat.com deep link
   - Notes if the source manual is older (supersession risk)
2. **Contextual part identification**: When the LLM walks through a repair procedure, it should automatically identify referenced part numbers and offer lookup
3. **Shopping list builder**: Accumulate parts across a troubleshooting session and generate a consolidated CSV for ordering

### Phase 4: Explore Official Channels (Ongoing)

1. **Contact your Cat dealer** about Cat IP eligibility for your operation
2. **Register on digital.cat.com** and explore available APIs
3. **Contact Cat Digital Support** (catdigitalsupport@cat.com) to inquire about parts data API access for marine customers
4. **Monitor the Cat Digital Marketplace** for new parts-related APIs as Caterpillar continues its "AI First" digital transformation

---

## 9. Architecture Recommendation

```
┌─────────────────────────────────────────────────┐
│                Flask Web App                     │
│                                                  │
│  ┌──────────────┐    ┌──────────────────────┐   │
│  │  LLM Chat    │───▶│  Tool/Function Layer  │   │
│  │  Assistant   │    │                       │   │
│  │  (RAG on     │    │  • search_manuals()   │   │
│  │   CAT PDFs)  │    │  • lookup_part()      │   │
│  │              │◀───│  • search_web()        │   │
│  └──────────────┘    │  • generate_csv()      │   │
│                      └──────────┬───────────┘   │
│                                 │                │
│                      ┌──────────▼───────────┐   │
│                      │  Local Parts DB       │   │
│                      │  (SQLite/PostgreSQL)  │   │
│                      │                       │   │
│                      │  • part_number        │   │
│                      │  • description        │   │
│                      │  • engine_model       │   │
│                      │  • category           │   │
│                      │  • source_doc         │   │
│                      │  • page_ref           │   │
│                      └──────────────────────┘   │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │           Action Buttons in Chat UI       │   │
│  │                                           │   │
│  │  [🔗 Check on parts.cat.com]              │   │
│  │  [📋 Open SIS2]                           │   │
│  │  [📥 Download Parts CSV]                  │   │
│  │  [🔍 Filter Cross-Reference]              │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
                        │
           External (user clicks link)
                        ▼
          ┌──────────────────────────┐
          │  parts.cat.com           │
          │  (user authenticated)    │
          │  • Real-time pricing     │
          │  • Availability          │
          │  • Supersession handled  │
          │  • Order placement       │
          └──────────────────────────┘
```

---

## 10. Sample LLM Agent Tool Implementation

```python
# tools/parts_lookup.py

import re
import sqlite3
from typing import Optional

CAT_PART_PATTERN = re.compile(r'\b(\d{3}-\d{4})\b')
PARTS_CAT_BASE = "https://parts.cat.com/en/catcorp/search?searchTerm="
SIS2_URL = "https://sis2.cat.com"
FILTER_XREF_URL = "https://www.catfiltercrossreference.com/"

def lookup_part(part_number: str, db_path: str = "cat_parts.db") -> dict:
    """
    Look up a CAT part number in the local database and 
    generate action links.
    
    Called by the LLM agent when a part number is mentioned 
    or when troubleshooting identifies needed parts.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT part_number, description, engine_model, 
               category, source_doc, page_ref
        FROM parts 
        WHERE part_number = ?
    """, (part_number,))
    
    result = cursor.fetchone()
    conn.close()
    
    response = {
        "part_number": part_number,
        "found_in_local_db": result is not None,
        "links": {
            "parts_cat_com": f"{PARTS_CAT_BASE}{part_number}",
            "sis2": SIS2_URL,
        }
    }
    
    if result:
        response.update({
            "description": result[1],
            "engine_model": result[2],
            "category": result[3],
            "source_document": result[4],
            "page_reference": result[5],
        })
        
        # Add filter cross-reference link if it's a filter
        if result[3] and 'filter' in result[3].lower():
            response["links"]["filter_xref"] = FILTER_XREF_URL
    
    response["note"] = (
        "Verify current pricing, availability, and part number "
        "on parts.cat.com. Part numbers from service manuals may "
        "have been superseded."
    )
    
    return response


def extract_parts_from_text(text: str) -> list:
    """Extract all CAT part numbers from a text string."""
    return list(set(CAT_PART_PATTERN.findall(text)))


def generate_order_csv(parts: list) -> str:
    """
    Generate a CSV string compatible with parts.cat.com 
    Quick Order upload.
    
    parts: list of dicts with 'part_number' and optional 'quantity'
    """
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Quantity', 'Part Number'])
    for part in parts:
        qty = part.get('quantity', 1)
        writer.writerow([qty, part['part_number']])
    return output.getvalue()
```

---

## 11. Key Contacts and Resources

| Resource | URL/Contact | Purpose |
|---|---|---|
| SIS 2.0 | sis2.cat.com | Parts diagrams, service info |
| parts.cat.com | parts.cat.com/en/catcorp | Parts ordering, pricing, availability |
| Cat Digital Support | catdigitalsupport@cat.com | API inquiries, technical support |
| Cat Digital Marketplace | digital.cat.com | Developer tools, API catalog |
| CPC API Portal | cpc.cat.com | Product content API (catalog data) |
| Cat Filter Cross-Reference | catfiltercrossreference.com | Filter parts cross-reference |
| Cat IP Information | cat.com/en_US/support/maintenance/parts/ip.html | B2B procurement integration |
| Cat SIS2GO App | App stores (iOS/Android/Windows) | Mobile SIS access |
| Your Cat Dealer | Contact locally | Cat IP setup, parts support, API credentials |

---

## 12. Conclusion

The most practical path to **"the LLM identifies a part number from the manual, and the engineer can check availability with one click"** is:

1. **Extract part numbers** from your already-indexed CAT engine manuals using regex (`\d{3}-\d{4}`)
2. **Build a local parts database** enriched with LLM-classified categories and engine applicability
3. **Generate deep-links** to `parts.cat.com/en/catcorp/search?searchTerm={part_number}` that the engineer clicks
4. **Offer CSV download** for multi-part repair procedures (compatible with parts.cat.com Quick Order)
5. **Add SIS2 and filter cross-reference links** as secondary actions

This approach is **free, legal, low-complexity, and immediately implementable** with your existing infrastructure. The engineer stays in your app for troubleshooting guidance and clicks through to Caterpillar's official platforms for pricing and ordering — leveraging their existing SIS2 subscription and parts.cat.com authentication.

For a longer-term path toward real-time API integration, explore **Cat Integrated Procurement (Cat IP)** with your dealer and monitor the **Cat Digital Marketplace** for emerging parts-data APIs.
