# LLM Manuals Assistant — Test Plan

**Purpose:** Validate the LLM assistant's response quality and RAG grounding using natural-language queries worded as marine engineers would ask. Use this plan to run the assistant through realistic scenarios and verify citation accuracy, hallucination prevention, and clarification behavior.

**Related docs:** [subsystem-tagging-guide.md](subsystem-tagging-guide.md) (systems, equipment, acronyms), [LLM-Powered-Manuals-Assistant-Plan.md](LLM-Powered-Manuals-Assistant-Plan.md) (architecture).

---

## 1. Prerequisites

- **ANTHROPIC_API_KEY** set in `.env`
- **engine_search.db** populated (run `python -m src.cli.index_manuals` with PDFs)
- App running at http://localhost:5001
- Navigate to `/manuals/chat`

---

## 2. Test Scenarios

### Category A: Procedures

Engineers asking for step-by-step how-to instructions.

| # | Query | Expected Behavior | Pass Criteria | Notes |
|---|-------|-------------------|---------------|-------|
| A1 | How do I adjust valve lash on the C18? | Returns procedure with numbered steps; cites document and page | Response cites [Doc Name, p.XX]; steps are numbered; no made-up torque values | C18 GenSet; valvetrain |
| A2 | What's the procedure for troubleshooting the 3516 fuel rack actuator? | Either triages results (procedure vs troubleshooting) or walks through relevant pages | Citations present; says "verify against your physical manual" for specs | 3516 Main Engine; fuel system |
| A3 | How do I clean the JWAC or aftercooler core? | Describes cleaning procedure; may mention JWAC/SCAC difference | Citations; no hallucinated chemical or pressure values | Cooling / air intake |
| A4 | How do I set injector height on the C32? | Gives procedure with tools and specs if in context | Specs quoted verbatim from manual; cites source | C32 Thruster; fuel injection |
| A5 | Walk me through replacing the oil filter | Step-by-step procedure; mentions capacity, torque if available | Numbered steps; citations; no invented part numbers | Lubrication; applies to multiple engines |

### Category B: Troubleshooting

Engineers describing symptoms or fault conditions.

| # | Query | Expected Behavior | Pass Criteria | Notes |
|---|-------|-------------------|---------------|-------|
| B1 | Engine cranks but won't fire — where do I start? | Suggests diagnostic flow (fuel, air, compression); cites troubleshooting sections | Citations; structured diagnosis; may ask for equipment model if ambiguous | Starting / fuel |
| B2 | We're getting a low oil pressure alarm. What should I check? | Lists causes (level, pump, filter, sensor, bearings); cites diagnostic flow | Citations; does not invent pressure thresholds | Lubrication; safety |
| B3 | Main engine is overheating. Coolant temp keeps climbing. | Covers coolant level, thermostat, heat exchanger, seawater flow, pump | Citations; suggests verification steps | Cooling; 3516 likely |
| B4 | Where do I look up ECU fault codes for the C18? | Points to electrical/controls docs; may list common codes if in context | Citations; does not invent fault codes | Electrical/Controls |
| B5 | Engine's making black smoke and losing power under load | Suggests fuel delivery, air restriction, turbo; diagnostic flow | Citations; asks about engine model if not specified | Fuel / air / exhaust |

### Category C: Maintenance Intervals

Engineers asking when to perform service.

| # | Query | Expected Behavior | Pass Criteria | Notes |
|---|-------|-------------------|---------------|-------|
| C1 | When do I need to change the engine oil? | Returns interval (e.g., 500hr, 1000hr) from manuals | Citations; no invented hours; says verify if not in context | Lubrication |
| C2 | What's the coolant change interval? | Interval from O&M or service manual | Citations; SCA/testing mentioned if in docs | Cooling |
| C3 | Is there a 500hr fuel filter change? | Confirms or denies from context; cites schedule | Citations; says "I don't have that" if not indexed | Fuel; maintenance schedule |
| C4 | How often should we replace the air filter? | Interval from manuals; may vary by environment | Citations; no invented intervals | Air intake |

### Category D: Specs / References

Engineers looking up numbers and tolerances.

| # | Query | Expected Behavior | Pass Criteria | Notes |
|---|-------|-------------------|---------------|-------|
| D1 | What's the cylinder head torque spec for the 3516? | Quotes torque values from manual; includes sequence if present | Values quoted verbatim; "verify against your physical manual"; citations | Cylinder head |
| D2 | What are the valve clearances for the C18? | Intake/exhaust clearances from Testing & Adjusting | Exact values; citations; no guessing | Valvetrain |
| D3 | What fuel pressure should I see at the rail? | Pressure spec from service manual if indexed | Citations; no invented psi/kPa | Fuel system |
| D4 | What's normal turbo boost pressure for the C32? | Boost spec from specs or O&M | Citations; units stated | Air intake; turbocharger |

---

## 3. Edge Cases and Negative Tests

| # | Query | Expected Behavior | Pass Criteria |
|---|-------|-------------------|---------------|
| E1 | 3516 fuel rack actuator troubleshooting | If RAG returns no relevant content: assistant says it does not have indexed content for that topic | Does NOT hallucinate; says something like "I don't have indexed content for that" or suggests searching directly |
| E2 | What's wrong with my engine? | Asks for clarification: which engine, what symptoms, what system | Asks for equipment model and/or symptoms |
| E3 | How do I cook pasta? | Declines; says out of scope; suggests searching manuals for engine topics | Stays in scope; redirects to manuals |

---

## 4. Pass Criteria by Scenario Type

| Type | Must Have | Must Not Have |
|------|-----------|---------------|
| **Procedures** | Numbered steps where appropriate; [Doc, p.XX] citations; "verify against your physical manual" for safety-critical specs | Invented torque, clearance, or pressure values |
| **Troubleshooting** | Diagnostic structure; citations; may ask for equipment/symptoms | Hallucinated fault codes or thresholds |
| **Maintenance intervals** | Citations; intervals only from context | Made-up hours or schedules |
| **Specs** | Values quoted verbatim; citations; verification reminder | Guessed or recalled values |
| **No context** | Explicit "I don't have indexed content" or similar | Fabricated procedures or specs |
| **Ambiguous** | Asks for engine model, symptoms, or system | Assumes and answers incorrectly |
| **Out of scope** | Declines; redirects to search | Attempts to answer off-topic |

---

## 5. Implementation Options for Executor

### Option A: Manual Execution

1. Start app: `cd src && FLASK_APP=app:create_app ../venv/bin/flask run --port 5001`
2. Open http://localhost:5001/manuals/chat
3. Log in if required
4. Run each query from the tables above
5. Record pass/fail and notes in a checklist (e.g., copy this doc and add `[ ]` / `[x]` per row)

### Option B: Scripted Execution

- POST to `/manuals/chat/api/message` (or equivalent chat API route) with session cookie
- Parse SSE stream for complete response
- Assert on: presence of citation pattern `[.*, p\.\d+]`, absence of hallucination keywords, presence of "don't have" for E1-type queries

Start with Option A for validation; add scripted tests if repeatability is needed.

---

## 6. Equipment and System Reference

**Engines:** 3516 (Main), C18 (GenSet), C32 (Thruster), C4.4 (Emergency)

**Systems (from subsystem-tagging-guide):** Fuel, Air Intake, Cooling, Lubrication, Exhaust, Starting, Electrical/Controls, Cylinder Block, Cylinder Head/Valvetrain, Safety/Alarms, General/Maintenance

**Acronyms:** MEUI, HEUI, JWAC, SCAC, ECU, ECM, EFI, SCR, DPF, OBD

---

## 7. Execution Checklist Template

Copy and use during test runs:

```
Category A (Procedures):     A1 [ ] A2 [ ] A3 [ ] A4 [ ] A5 [ ]
Category B (Troubleshooting): B1 [ ] B2 [ ] B3 [ ] B4 [ ] B5 [ ]
Category C (Intervals):      C1 [ ] C2 [ ] C3 [ ] C4 [ ]
Category D (Specs):          D1 [ ] D2 [ ] D3 [ ] D4 [ ]
Edge Cases:                  E1 [ ] E2 [ ] E3 [ ]

Notes:
```
