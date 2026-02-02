# Codex Agent Prompt: Marine Diesel Engine Technical Manual Search Tool Testing & Improvement

## Your Mission

You are an expert marine engineer and software tester tasked with comprehensively testing and improving a local search application for Caterpillar marine diesel engine technical manuals. The application indexes 62 PDF documents covering C4.4, C18, 3516, and C32 engines with full-text search functionality.

Your goal is to **execute systematic testing, identify gaps, and recommend specific improvements** to make this tool production-ready for vessel operators and marine engineers.

---

## Application Context

### Current Implementation
- **Technology Stack**: Python/SQLite/Flask
- **Document Count**: 62 PDFs
- **Engine Models**: C4.4 (Emergency), C18 (GenSet), 3516 (Main Engine), C32 (Thruster)
- **Document Types**:
  - Operation & Maintenance (O&M) Manuals
  - Service Manuals
  - Troubleshooting Guides
  - Testing & Adjusting Modules
  - Disassembly & Assembly Modules
  - Specifications Modules
  - Schematics/Electrical Diagrams
- **Features Already Implemented**:
  - Full-text search across all PDFs
  - Equipment type filtering (by engine model)
  - Document type filtering
- **Features Planned (Not Yet Implemented)**:
  - Subsystem tagging (fuel, cooling, lubrication, air intake, exhaust, electrical, etc.)
  - Hierarchical filtering (system → subsystem → component)
  - Multi-label document tagging

### Document Library (from contents.md)

**Emergency_C4.4** (11 documents):
- Specifications, Testing & Adjusting, Schematics, Disassembly & Assembly, Systems Operations, O&M, Special Instructions, Service modules

**GenSet_C18** (24 documents):
- Troubleshooting (multiple), Schematics (multiple), Service, Specifications, Testing & Adjusting, Disassembly & Assembly, O&M (multiple), Special Instructions

**Main_Engine_3516** (12 documents):
- Service, Specifications, Testing & Adjusting, Troubleshooting (multiple), Schematics (multiple), Disassembly & Assembly, O&M (multiple), Special Instructions

**Thruster_C32** (15 documents):
- Schematics (multiple), Troubleshooting (multiple), Disassembly & Assembly, O&M (multiple), Special Instructions, Service, Specifications, Testing & Adjusting

---

## Your Testing Protocol

### Phase 1: Baseline Functionality Testing (50 queries)

**Objective**: Verify search returns relevant results for common maintenance tasks.

**Test Set 1.1 - Simple Keyword Searches (10 queries)**
Execute these queries and record:
- Number of results returned
- Are the top 3 results relevant?
- Which document types appear in results?
- Are results from correct engine model (if specified)?

Sample queries:
1. "valve lash"
2. "oil change"
3. "fuel filter"
4. "turbocharger"
5. "coolant"
6. "injector"
7. "thermostat"
8. "oil pressure"
9. "starting"
10. "wiring diagram"

**Test Set 1.2 - Component-Specific Searches (10 queries)**
1. "HEUI injector"
2. "seawater pump impeller"
3. "heat exchanger"
4. "JWAC" (Jacket Water Aftercooler)
5. "SCAC" (Seawater Charge Air Cooler)
6. "ECM" (Engine Control Module)
7. "valve bridge"
8. "rocker arm"
9. "crankshaft bearing"
10. "turbo boost pressure"

**Test Set 1.3 - Model-Specific Queries (10 queries)**
Test if engine model filtering works correctly:
1. "C18 valve adjustment"
2. "3516 oil capacity"
3. "C32 specifications"
4. "C4.4 troubleshooting"
5. "3516 torque specifications"
6. "C18 fuel system"
7. "C32 cooling system"
8. "3516 starting problems"
9. "C18 wiring diagram"
10. "C4.4 service intervals"

**Test Set 1.4 - Natural Language Questions (10 queries)**
Test if search handles conversational queries:
1. "How do I adjust valves on a 3516?"
2. "What is the oil change interval?"
3. "How to find top dead center?"
4. "How to bleed fuel system?"
5. "What causes low oil pressure?"
6. "How to test turbocharger?"
7. "How to replace fuel filter?"
8. "What is valve lash specification?"
9. "How to remove cylinder head?"
10. "How to check compression?"

**Test Set 1.5 - Troubleshooting Scenarios (10 queries)**
1. "engine won't start"
2. "overheating"
3. "black smoke"
4. "low power"
5. "rough idle"
6. "high coolant temperature"
7. "fuel leak"
8. "oil leak"
9. "turbo failure"
10. "alarm troubleshooting"

**For each query, document:**
- ✓/✗ Did it return relevant results?
- Number of results
- Top 3 document filenames
- Missing information you'd expect to find
- False positives (irrelevant results)

---

### Phase 2: Advanced Search Testing (100+ queries from test file)

**Objective**: Execute comprehensive test queries from `engine-search-test-queries.md` to identify gaps.

**Test Categories to Execute**:
1. **Maintenance Procedures** (50 queries)
   - Oil & Lubrication (10)
   - Cooling System (10)
   - Fuel System (10)
   - Air Intake & Exhaust (10)
   - Valve Train & Cylinder Head (10)

2. **Troubleshooting** (70 queries)
   - Starting Issues (10)
   - Performance Problems (10)
   - Overheating (10)
   - Oil Pressure (10)
   - Electrical & Controls (10)
   - Fuel System Faults (10)
   - Turbocharger Problems (10)

3. **Procedural Questions** (75 queries)
   - Finding TDC (5)
   - Valve Adjustment (10)
   - Fuel System Bleeding (10)
   - Turbocharger Inspection (10)
   - Cooling System Service (10)
   - Injector Service (10)
   - Oil Change (10)
   - Starting System (10)

4. **Specifications & Torque Values** (40 queries)
5. **Disassembly & Assembly** (40 queries)
6. **Schematics & Diagrams** (40 queries)
7. **Model-Specific** (30 queries)

**For Phase 2, focus on:**
- Which query categories perform well?
- Which categories return poor/no results?
- Are multi-word technical terms handled correctly? ("valve lash", "top dead center", "fuel injection timing")
- Do acronyms work? (TDC, HEUI, MEUI, JWAC, SCAC, ECM, ECU)
- Are there patterns in failed searches?

---

### Phase 3: Filtering & Navigation Testing

**Test Current Filters:**
1. Equipment Type Filter:
   - Does filtering by "C18" only show C18 docs?
   - Does filtering by "3516" only show 3516 docs?
   - Test each engine model (C4.4, C18, 3516, C32)

2. Document Type Filter:
   - Does "O&M" filter work correctly?
   - Does "Troubleshooting" filter work?
   - Does "Specifications" filter work?
   - Does "Schematics" filter work?
   - Test combined filters (e.g., C18 + Troubleshooting)

**Test Planned Subsystem Filters (if not yet implemented, recommend priority):**
- Can you filter for "Fuel System" topics?
- Can you filter for "Cooling System" topics?
- Can you filter for "Electrical" topics?
- Do multi-system documents appear in multiple filters?

---

### Phase 4: Edge Case & Stress Testing

**Test These Scenarios:**
1. **Spelling Variations**:
   - "labour" vs "labor"
   - "centre" vs "center"
   - "coolant" vs "cooland" (typo)
   - "analyze" vs "analyse"

2. **Synonym Handling**:
   - "turbocharger" vs "turbo"
   - "injector" vs "fuel injector"
   - "cylinder head" vs "head"
   - "crankshaft" vs "crank"

3. **Acronym Recognition**:
   - Does "TDC" return same results as "top dead center"?
   - Does "ECM" work as well as "engine control module"?
   - Does "O&M" work as well as "operation and maintenance"?

4. **Complex Multi-Word Queries**:
   - "valve lash adjustment procedure"
   - "fuel system bleeding after filter change"
   - "turbocharger bearing failure diagnosis"
   - "cylinder head bolt torque sequence"

5. **Partial Matches**:
   - "valve" (should return valve lash, valve timing, valve adjustment, etc.)
   - "fuel" (should return fuel filter, fuel system, fuel pressure, etc.)
   - "oil" (should return oil change, oil pressure, oil leak, etc.)

6. **Empty/No Results**:
   - Identify queries that return zero results but should have results
   - Document which information is missing from the manual collection

---

### Phase 5: User Experience Evaluation

**Evaluate These Aspects:**

1. **Search Speed**:
   - Time typical queries
   - Is full-text search fast enough? (<500ms acceptable, <100ms ideal)

2. **Result Ranking**:
   - Are most relevant docs at the top?
   - Do specific procedures outrank general overviews?
   - Are troubleshooting docs prioritized for problem queries?

3. **Result Presentation**:
   - Can you identify which section of the PDF contains the result?
   - Are page numbers shown?
   - Is context snippet helpful?
   - Can you preview result before opening PDF?

4. **Navigation Flow**:
   - How many clicks to find information?
   - Can you refine search easily?
   - Can you go back to results after opening a PDF?

5. **Mobile/Responsive**:
   - Does it work on tablet (common in engine rooms)?
   - Are filters accessible on small screens?

---

## Deliverable: Comprehensive Testing Report

### Required Report Structure

#### 1. Executive Summary
- Overall search effectiveness rating (1-10)
- Top 3 strengths
- Top 3 critical issues
- Recommended priority improvements (ranked)

#### 2. Baseline Functionality Results
- Success rate by test category (percentage)
- Table of failed queries with reasons
- Examples of excellent search results
- Examples of poor search results

#### 3. Advanced Search Results Analysis
- Which query categories perform best? (list top 3)
- Which query categories fail most often? (list bottom 3)
- Acronym/abbreviation handling: works / needs improvement
- Natural language question handling: works / needs improvement
- Model-specific filtering: works / needs improvement

#### 4. Gap Analysis
**Missing Functionality:**
- List features that should exist but don't
- Prioritize by impact (High/Medium/Low)

**Missing Information:**
- Topics frequently searched but not found in manuals
- Suggest additional documentation needed

#### 5. Specific Improvement Recommendations

**Category A: Critical (Implement Immediately)**
Format:
```
1. [Issue]: [Description]
   **Impact**: [User impact]
   **Solution**: [Specific technical recommendation]
   **Implementation Effort**: [Low/Medium/High]
   **Example**: [Before/After scenario]
```

**Category B: High Priority (Implement Soon)**
[Same format as above]

**Category C: Enhancement (Nice to Have)**
[Same format as above]

#### 6. Subsystem Tagging Validation
- Review proposed taxonomy from `diesel-tagging-guide.md`
- Are the 11 primary systems appropriate?
- Are secondary subsystems granular enough?
- Recommend any additions/changes
- Validate keyword dictionary completeness
- Suggest high-value tags to add first

#### 7. Search Query Optimization
- Recommend query preprocessing steps (stemming, lemmatization, synonym expansion)
- Suggest search scoring/ranking improvements
- Identify need for phrase matching vs. word matching
- Evaluate need for fuzzy matching (typo tolerance)

#### 8. Technical Implementation Recommendations

**Database Schema:**
- Validate SQLite schema from `diesel-tagging-guide.md`
- Suggest index optimizations
- Recommend query performance improvements

**Search Algorithm:**
- Evaluate SQLite FTS5 configuration
- Recommend ranking/scoring adjustments
- Suggest handling of common words (stop words)

**UI/UX Enhancements:**
- Filtering interface improvements
- Result presentation improvements
- Navigation flow improvements
- Mobile optimization needs

#### 9. Testing Artifacts
- Spreadsheet/table of all test queries with results
- List of queries that returned 0 results
- List of queries that returned excellent results
- Screenshots or examples of good/bad result sets

#### 10. Prioritized Action Plan
Create a numbered checklist:
```
Priority 1 (Week 1):
[ ] Fix [specific issue]
[ ] Implement [specific feature]
[ ] Optimize [specific component]

Priority 2 (Week 2-3):
[ ] Add [feature]
[ ] Improve [aspect]

Priority 3 (Month 2):
[ ] Enhance [feature]
[ ] Consider [improvement]
```

---

## Specific Areas to Investigate

### 1. Valve Lash Adjustment Accuracy
This is a **critical maintenance procedure**. Test these queries:
- "valve lash"
- "valve adjustment"
- "valve clearance"
- "valve lash specification"
- "How do I adjust valves on a C18?"
- "valve lash C32"
- "injector height" (related procedure)

**Expected Results**: Should return testing-&-adjusting manuals with specific procedures for each engine model.

**Validate**:
- Are specifications clearly shown? (intake: 0.38mm ± 0.08mm, exhaust: 0.76mm ± 0.08mm for C18)
- Is adjustment procedure step-by-step?
- Are torque specs included? (30 ± 7 N·m for locknut)
- Are related topics cross-referenced? (finding TDC, injector height)

### 2. Top Dead Center (TDC) Location
Another **critical procedure**. Test:
- "TDC"
- "top dead center"
- "finding top dead center"
- "timing pin"
- "How do I find TDC on a 3516?"
- "#1 piston top center"

**Expected Results**: Should return service manuals and testing-&-adjusting manuals with TDC location procedures.

**Validate**:
- Is timing pin tool mentioned?
- Is flywheel housing access described?
- Is compression stroke identification explained?
- Are valve position checks described?

### 3. Fuel System Bleeding
**Critical for startup after maintenance**. Test:
- "fuel system bleeding"
- "bleed fuel system"
- "air in fuel system"
- "prime fuel system"
- "How to bleed fuel system after filter change?"

**Expected Results**: Should return O&M manuals and troubleshooting guides.

**Validate**:
- Is step-by-step bleeding procedure present?
- Are bleed screw locations shown?
- Is manual priming pump procedure described?
- Is sequence of bleeding (filter → pump → injectors) clear?

### 4. Troubleshooting Overheating
**Common critical fault**. Test:
- "overheating"
- "high coolant temperature"
- "engine temperature high"
- "cooling system troubleshooting"

**Expected Results**: Should return troubleshooting manuals and O&M manuals.

**Validate**:
- Is diagnostic flow chart present?
- Are common causes listed (thermostat, heat exchanger, seawater pump)?
- Are test procedures described?
- Are specifications provided (normal operating temperature)?

### 5. Wiring Diagrams / Schematics
**Essential for electrical troubleshooting**. Test:
- "wiring diagram C18"
- "electrical schematic 3516"
- "sensor wiring"
- "ECM pinout"
- "starting system wiring"

**Expected Results**: Should return schematic/pub documents.

**Validate**:
- Are diagrams readable/clear?
- Are wire colors shown?
- Are connector pinouts detailed?
- Are ground locations shown?

### 6. Specifications & Torque Values
**Required for proper reassembly**. Test:
- "torque specifications"
- "cylinder head bolt torque"
- "valve lash specification"
- "oil capacity"
- "coolant capacity"

**Expected Results**: Should return specifications manuals.

**Validate**:
- Are torque values complete?
- Are tightening sequences shown?
- Are fluid capacities listed by engine model?
- Are clearances specified?

### 7. Model-Specific Differentiation
Test if search distinguishes between engine models:
- "C18 oil capacity" (should only return C18 docs)
- "3516 valve adjustment" (should only return 3516 docs)
- Generic "oil capacity" (should return all models or allow filtering)

**Validate**:
- Does equipment filter work correctly?
- Are results properly labeled with model?
- Can you easily switch between models?

### 8. Cross-System Topics
Some topics span multiple systems. Test if search captures all relevant docs:
- "aftercooler" (cooling system + air intake system)
- "turbocharger oil supply" (air intake + lubrication)
- "fuel pressure sensor" (fuel system + electrical)
- "high temperature alarm" (cooling + safety/alarms + electrical)

**Validate**:
- Are all related documents returned?
- Is multi-label tagging needed (future feature)?

---

## Success Criteria

### Minimum Acceptable Performance
- ≥80% of common maintenance queries return relevant results
- ≥70% of troubleshooting queries return relevant results
- ≥90% of model-specific queries filter correctly
- Top 3 results should include correct answer ≥75% of the time
- Search speed <500ms for typical queries

### Excellent Performance Goals
- ≥95% of common maintenance queries return relevant results
- ≥85% of troubleshooting queries return relevant results
- ≥98% of model-specific queries filter correctly
- Top 3 results should include correct answer ≥90% of the time
- Search speed <200ms for typical queries
- Natural language questions handled as well as keyword searches

---

## Additional Context & Resources

### Reference Documents Provided
1. **diesel-tagging-guide.md** - Comprehensive guide for implementing subsystem tagging with taxonomy, keyword dictionary, SQLite schema, and implementation plan
2. **engine-search-test-queries.md** - 470 test queries organized by category for comprehensive testing

### Industry Knowledge
- Marine engineers often search while troubleshooting under time pressure
- Access to manuals often happens in engine rooms with limited connectivity
- Common workflow: symptom → troubleshooting guide → procedure → specifications
- Critical procedures must be findable in <30 seconds
- Schematic diagrams must be easily accessible for electrical issues

### Known Caterpillar Manual Structure
- **O&M Manuals** (sebu prefix): Operator information, maintenance schedules, basic troubleshooting
- **Service Manuals** (renr/senr/kenr prefix): Detailed procedures, disassembly/assembly, testing/adjusting
- **Troubleshooting Guides** (kenr prefix, _troubleshooting suffix): Diagnostic procedures, fault codes, test procedures
- **Specifications** (senr prefix, _specifications suffix): Torque values, clearances, capacities, dimensions
- **Schematics** (renr/kenr prefix, -pub suffix): Wiring diagrams, hydraulic schematics, fuel system diagrams

### Common Acronyms You'll Encounter
- **TDC**: Top Dead Center
- **HEUI**: Hydraulically Actuated, Electronically Controlled Unit Injector
- **MEUI**: Mechanically Actuated, Electronically Controlled Unit Injector
- **JWAC**: Jacket Water Aftercooler
- **SCAC**: Seawater Charge Air Cooler
- **ECM/ECU**: Engine Control Module/Unit
- **O&M**: Operation & Maintenance
- **SCA**: Supplemental Coolant Additive
- **EGR**: Exhaust Gas Recirculation
- **DPF**: Diesel Particulate Filter
- **SCR**: Selective Catalytic Reduction

---

## Output Format

Generate your comprehensive testing report in Markdown format with:
- Clear section headings
- Tables for test results
- Code blocks for technical recommendations
- Numbered lists for action items
- Examples with before/after scenarios
- Screenshots/examples where helpful

**Prioritize actionable recommendations.** Every issue should have a specific, implementable solution.

---

## Final Instructions

1. **Be thorough but focused**: Test comprehensively, but prioritize issues by user impact
2. **Provide specific solutions**: Don't just identify problems—recommend exact fixes
3. **Think like a marine engineer**: Consider real-world usage scenarios and time pressure
4. **Validate against manual collection**: Some "failures" may be due to information not existing in the 62 PDFs
5. **Consider implementation effort**: Recommend quick wins alongside long-term improvements
6. **Use the test query file**: Execute queries from `engine-search-test-queries.md` systematically
7. **Validate tagging guide**: Review and improve the proposed subsystem taxonomy from `diesel-tagging-guide.md`

Your testing and recommendations will directly impact the usability and effectiveness of this critical maintenance tool for vessel operations.

---

**Begin comprehensive testing and deliver your detailed report with prioritized, actionable recommendations.**
