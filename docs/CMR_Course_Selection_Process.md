# MDC Course Selection — Process Specification (Living Document)

> **Purpose.** This document captures, step by step, the manual process for course
> selection at Miami Dade College (MDC) so it can later be built into an
> application. It is being written **as we walk through the process manually**, to
> preserve every step and its nuances. Treat this as the source of truth /
> evolving PRD for the POC.
>
> **Status:** 🟡 In progress — capturing steps manually.
> **Last updated:** 2026-06-23
> **Scope (POC):** Kendall campus, Term `2273` (Spring 2027), 3 departments
> (Architecture, Engineering, Technology).

---

## 1. Glossary & Conventions

| Term | Meaning |
|---|---|
| **CMR** | The master input spreadsheet (working expansion: *Course/Class Master Report* — TBD/confirm). It is the single input that flows through the entire workflow. |
| **Section** | A specific class offering (one row in the `Schedule` tab). |
| **FTF** | Full-Time Faculty. |
| **ADJ / Adjunct** | Part-time faculty. |
| **Term `2273`** | Spring 2027 (the only term present in the current CMR). |
| **Acad Org** | Academic organization (department) code. |
| **SCH** | Student Credit Hours. |
| **Mailbox-as-a-service** | External mailbox the app reads/sends from to auto-respond (esp. for adjunct coordination). |

**Conventions**
- Each pipeline step **reads from and writes back to** the master CMR (the `Schedule` tab is the spine).
- Decisions that affect the build are recorded in the **Decision Log** (§9).
- Open questions are tracked in **Open Questions** (§8) until resolved, then moved to the Decision Log.

---

## 2. System Overview

> **Core objective.** The CMR arrives with **many data errors**. The early stages of
> this pipeline are fundamentally a **data quality / cleaning effort**: validate and
> correct the schedule so it is trustworthy **before** it is sent to faculty for course
> selection. Garbage-in would propagate into faculty selection, room assignment, and
> capacity — so cleaning up front is the whole point of Steps 1–1b.

The workflow is a multi-stage pipeline. The CMR is a **living master**; each stage
applies validations / gateways / constraints (via a set of prompts to be supplied)
and writes results back.

```
Step 0  Ingest CMR (provided spreadsheet)
   │
Step 1  Filter / Scope            → narrow to Kendall + 3 departments
   │
Step 1b Duration                  → sessions/terms, decide if new sections needed
   │
Step 2  Selection
   ├─ 2a Full-Time Faculty pick first ("first dibs")
   └─ 2b Leftover → Adjunct sub-process (coordination, availability, schedules)
   │
Step 3  Classroom Assignment      → rooms, with gateways/constraints/validations
   │
Step 4  Capacity Check            → seats, SCH, room capacity validations
```

> **Note on step numbering.** In early discussion, "Step 1 = duration." During the
> manual walkthrough the user introduced **filtering as the first concrete action**.
> This document treats **Filtering as Step 1** and **Duration as Step 1b** for now;
> numbering may be reconciled later (see Open Questions).

Running alongside the pipeline: a **mailbox-as-a-service / auto-respond** layer,
primarily for the human coordination in the adjunct sub-process (Step 2b).

---

## 3. Step 0 — Ingest the CMR

**Input:** the CMR workbook, provided externally.
**Reference file analyzed:** `Collegewide_CMR (2273) Spring 2027` — generated 2026-06-22 (`.xlsb`).

### 3.1 Workbook structure (8 tabs)

| Tab | Approx size | Role |
|---|---|---|
| **Schedule** | 10,172 rows × 95 cols | **Master table.** One row per section/meeting. The spine of the pipeline. |
| **Instructors** | ~5,508 × 39 | Instructor↔class assignments; In-Load / Over-Load FTF and In-Load ADJ split. |
| **Quick View Schedule** | ~25,744 (many blank spacer rows) × 22 | Condensed human-readable schedule. |
| **Workload** | ~5,439 × 8 | Per-instructor workload rollup (Load FTF / Over-Load FTF / In-Load ADJ). |
| **Report** | tiny | Pivot summary. KENDL totals: SCH 33,190, Tot Enrl 10,892, Cap 48,783, 1,468 classes. |
| **PT Kendl** | ~184 | Pivot of part-time (adjunct) Kendall assignments. |
| **Tables 1 – 4** | ~1,615 × 49 | **Lookup / constraint reference tables** (see below). Where the rules/gateways live. |
| **Rooms** | ~157 | Room inventory: Facility ID, Course, Class Nbr, meeting times, Room Capacity. |

**`Tables 1 – 4` reference blocks (constraint/lookup data):**
Room_Cap, Load_Enrl, Times, Session_Duration, Area_Study, GE, FTF_Kendall,
Chairs, Dual_Enrl, Paid (Kendall), ADJ_Kendall.

### 3.2 Key `Schedule` columns observed (95 total; selected)

- Identity: `Term & Class Nbr`, `Term`, `Class Nbr`, `Course Prefix (Subject)`, `Course Number (Catalog)`, `Class Descr`, `Class Section`, `Course ID`.
- Org/location: `Acad Group`, `Acad Org`, `Acad Org Name`, `Acad Org Campus`, `Class Loc`, `Loc Short Desc`.
- Status/enrollment: `Class Status`, `Tot Enrl`, `Cap Enrl`, `Seat Available`, `SCH`, `Tot Enroll / Cap Enrl`.
- Scheduling: `Session Code`, `Start Date`, `End Date`, `Concat Days`, `Mtg Start`, `Mtg End`, `Duration`, `Class Duration`, `Instr Mode`.
- Room: `Facility ID`, `Building`, `Room ID`, `Room Capacity`.
- Faculty: `Assigned Instr(s)?`, `Instructor`, `Empl ID`, `E-Mail`, `Assigned Work Load`, `Instr Role`, `KENDL FTF`, `KENDL FTF Org`, `KENDL ADJ`, `KENDL ADJ Org`, `Kendl Chair`.

### 3.3 Whole-CMR distributions (10,172 data rows)

- **Term:** `2273` (Spring 2027) — effectively the entire file.
- **Loc Short Desc:** Kendall 1,804 · North 1,565 · Wolfson 1,321 · Virtual 1,169 · Padron 733 · Medical 660 · Hialeah 573 · Homestead 529 · West 491 · Area Hospital 322.
- **Class Status:** A (active) 8,772 · T 663 · X (cancelled) 639 · S 97.
- **Instr Mode:** In-Person 4,574 · MDC Live 2,329 · Blended 1,960 · Online 1,169 · Independent 137 · Credit-by-Exam 2.
- **Session Code:** `1` (full) 5,465 · `8W2` 1,269 · `12W` 1,149 · `8W1` 1,088 · `14W` 564 · `DYN` 413 · `WKD` 216 · `DYS` 7.
- **Assigned Instr(s)?:** Y 5,467 · N 4,704.

**Although named "Collegewide," this copy is Kendall-centric** — it carries
Kendall-specific columns (`KENDL FTF`, `KENDL ADJ`, `Kendl Chair`) and the summary
tabs total to KENDL.

---

## 4. Step 1 — Filter / Scope to the 3 Kendall Departments

**Goal:** reduce the CMR to only the sections this process governs (the selection pool).

### 4.1 Canonical Step 1 filter (CONFIRMED → 184 sections)

Apply, in order:

1. **`Acad Org`** ∈ `{300020, 450034, 450060}` (the 3 target departments)
2. **`Class Status = A`** (active only)
3. **`Cap Enrl ≠ 9999`** (exclude the 9999 sentinel-cap category)

| Filter step | Rows remaining |
|---|---|
| 3 Acad Orgs | 278 |
| …`Class Status = A` | 236 |
| …exclude `Cap Enrl = 9999` | **184** ✅ |

This **184** is the agreed Step 1 output (matches the user's manual count).

### 4.2 The 3 departments

| `Acad Org` | Department | Rows (unfiltered) |
|---|---|---|
| `300020` | Architect & Interior Design KE (Architecture) | 77 |
| `450034` | Engineering – Kendall | 31 |
| `450060` | Technology – Kendall | 170 |
| | **Total** | **278** |

All three codes resolve to the **Kendall** versions of those departments; the same
departments at other campuses (North, Wolfson, Padron, Hialeah, West, Homestead)
are correctly **excluded**. All 278 rows have `Acad Org Campus = KENDL`, so the
Acad Org filter inherently scopes to Kendall — no separate campus filter needed.

### 4.3 What gets excluded, and why it matters for the build

- **`Class Status ≠ A` → −42 rows** (X-cancelled 35, S 4, T 3). Non-active sections.
- **`Cap Enrl = 9999` → −52 rows** (of the active set). **`9999` is a sentinel /
  placeholder cap** ("no real cap set" — likely non-enrollment shells, TBD, or
  special sections), **not** a single row. It is a whole *category* to exclude.

> ⚠️ **Open intent (Q7):** should the excluded **42 non-active** and **52 `9999`-cap**
> rows be **dropped entirely**, or **set aside** (retained in the master CMR but out of
> the selection pool) in case they're needed later for capacity/room math? Default
> assumption until told otherwise: **set aside, don't delete** — the CMR is a living
> master.

### 4.4 Edge case (location)
Of the 278, **277 meet at Kendall** but **1 meets at North** (`Loc Short Desc = North`)
while still owned by the Kendall org. Filter is by **department ownership** (`Acad Org`),
so this class stays in scope; physical location is tracked separately for Step 3
(room assignment).

### 4.5 Snapshot of the 184 selection pool
- Assigned Instr(s)?: ~half still need an instructor (to re-confirm on the 184).
- KENDL FTF / KENDL ADJ flags partially pre-populated (to re-confirm on the 184).

---

## 5. Step 1b — Duration Validation (Data Quality / Cleaning)

> **Objective (WHY this step exists).** The CMR arrives with **many data errors**.
> Step 1b is a **data quality / validation check** whose goal is to **clean and
> validate** the schedule data so it is correct **before** it is sent out to
> full-time faculty for course selection (Step 2). It is a remediation gate, not
> just a report — mismatches are meant to be **found and fixed**. A clean schedule
> is a precondition for the selection process.

**Input:** the `"Main_…"` file — i.e., the **Step 1 filtered output (the 184 sections)**.
**Source spec:** `Instructions_for_Duration_Validation_Fall_Spring.docx` (captured below).

### 5.1 Reference data (from the spec)

- **`Duration`** column displays as `H:MM:SS` (stored as fraction-of-day in the xlsb;
  minutes = `Duration × 1440`).
- **`Crs Cntct Hrs`**: 1 contact hour = **50 minutes**.
- **`Session Code` → weeks:** `1`→16, `WKD`→16, `6W1`→6, `6W2`→6, `8W1`→8, `8W2`→8,
  `10W`→10, `12W`→12, `14W`→14.
- **`Concat Days` → number of days:** `M/T/W/R/F/S`→1, `MW`→2, `TR`→2, `MWF`→3, `MTWR`→4
  (count the day letters).
- **`Instr Mode`:** `P (In Person)` full meeting/full duration; `LV (MDC Live)` full;
  `BL (Blended)` **half** meeting pattern / **half** duration; `EX (Credit by Exam)`
  none; `IN (Independent Study)` none.
- **`Comp`:** `LEC` lecture, `LAB` lab, `PRA` practicum (**treat PRA as LAB**).

### 5.2 Core validation logic

```
expected_min = Crs Cntct Hrs * 50 / weeks / days
  - if Acad Org == 450060: remap Crs Cntct Hrs first (80→64, 64→48)  [see 5.4]
  - if Instr Mode == BL:   expected_min *= 0.5  (blended = half duration)
  - if Instr Mode in (EX, IN): no meeting/no duration → N/A (skip)
actual_min = Duration * 1440
```

### 5.3 Linked LEC + LAB/PRA sections — Acad Org `300020` and `450034` only

Treat a linked LEC and its LAB/PRA as **one combined class** for validation.

**Precise link definition (confirmed 2026-06-23). ALL conditions must hold (AND):**

| # | Condition | Exactness (confirmed) |
|---|---|---|
| 1 | **Ordering:** the LEC **immediately precedes** the lab — LEC at row N, LAB/PRA at row N+1, nothing between | LEC always first |
| 2 | **Same `Class Descr`** | **Exact** match, case- and space-sensitive |
| 3 | **Same `Concat Days`** | Exact |
| 4 | **LAB/PRA `Mtg Start` == LEC `Mtg End`** | **Zero tolerance** — equal to the minute; 1 minute off breaks the link |

- **Cardinality:** strictly **1 LEC ↔ 1 LAB/PRA**. One LEC never links to multiple
  labs; a LEC is paired only with the single immediately-following row.
- **Adjacency basis:** consecutive rows **in the `Main_` file being validated** (after
  Step 1 filtering).
- **Scope:** Acad Org `300020` and `450034` only. `450060` (Technology) does **not**
  link — it uses the contact-hour remap and validates LEC/LAB independently.

**Near-misses are error signals (double duty):** when a pair is *meant* to be one class
but fails exactly one condition, the broken link is the data error —
- Condition 4 fails (lab starts late, e.g. 7:05 vs 6:55) → not linked → surfaces as a
  duration mismatch.
- Second row mislabeled `LEC` instead of `LAB/PRA` (condition 1 component test) → not
  linked → two "lectures" that don't validate correctly.

**Out of scope of the link definition:** equal `Cap Enrl` between LEC and LAB is **not**
a linking condition — it is a **separate integrity check** layered on linked pairs
(e.g. ARC2580: links cleanly, validates on duration, but LEC cap 40 ≠ LAB cap 30).

When linked:
- `actual = LEC actual + LAB/PRA actual` (sum both durations).
- `expected = computed from the LEC's `Crs Cntct Hrs` only`; put combined total on LEC row.
- Validate **once** using the combined duration.
- **LEC row** carries the actual validation result.
- **LAB/PRA row** is **not** independently validated → mark
  `"Validated together with linked LEC section"`; use `"See above"` in the
  *Expected Duration* and *Notes* columns.
- If combined result = **mismatch** → mark **both** rows `"Mismatch"`.
- If combined result = validated within tolerance → LEC `"Validated"`,
  LAB/PRA `"Validated together with linked LEC section"`.

### 5.4 Acad Org `450060` (Technology) special remap

Before computing expected duration, remap `Crs Cntct Hrs`:
- `80` → `64`
- `64` → `48`

**High impact:** in the 184 set, 74 of 450060's rows have `80` and 7 have `64`, so
this remap affects nearly every Technology section. (Working assumption: clock-hour →
contact-hour conversion for Technology programs — confirm.)

**450060 has no lab component (confirmed 2026-06-23).** Technology classes are
single-component (combined `C`-suffix sections), so any `LAB`/`PRA` row in Acad Org
`450060` is spurious and is **ignored** everywhere — not duration-validated (status
`Ignored - Acad Org has no lab component`) and not integrity-checked. In the current
file this affects exactly **1 row** (CTS1120 LAB). Config: `NO_LAB_ORGS = {"450060"}`.

### 5.5 Tolerance (DECIDED: 10% of expected)

- **Canonical tolerance = 10% of the expected duration** (the doc's explicit "off by
  less than 10% … should be considered validated"). Configurable in `config.py`
  (`TOLERANCE_MODE`/`TOLERANCE_PCT`); a `minutes` mode (10 min) is available as an
  alternative the doc also cites.
- **Behavior:**
  - off by 0 → `Validated`, no note.
  - off by >0 but ≤ tolerance → `Validated`, **flagged + noted** (`Within tolerance: …`).
  - off by > tolerance → `Mismatch`, with `Add/Subtract N min`.
- **First-run effect:** 0 mismatches; **36** rows pass but are flagged within-tolerance
  (all tiny ≤7 min deviations, e.g. a blended class scheduled 195 vs 200 min). At a 10
  min absolute tolerance the result is identical (0 mismatches) for this file.

### 5.6 Output (append columns; preserve original row order)

| Column | Meaning |
|---|---|
| Current Duration in minutes | `Duration × 1440` (combined for linked LEC) |
| Expected Duration in minutes | computed; `"See above"` for inherited LAB/PRA rows |
| Validation Status | `Validated` / `Mismatch` / `Validated together with linked LEC section` / `N/A` |
| Notes | how many minutes to **add or subtract** for mismatches; `"See above"` for inherited rows |

Use consistent terminology throughout the file.

### 5.8 First-run results (against `Collegewide_CMR (2273) Spring 2027`)

Implemented as Python (`cmr_pipeline/`) and run end-to-end. Step 1 → **184** sections.
Duration validation (10% tolerance) results:

| Status | Count |
|---|---|
| Validated | 135 |
| Validated together with linked LEC section | 48 |
| N/A – insufficient data (cch = 0) | 1 |
| **Mismatch** | **0** |

**Gap distribution** (rows with a computable expected duration): 99 exact, 35 within
5 min, 1 within 5–10 min, **none beyond 20 min**.

**Key findings:**
- **The 450060 remap is critical.** With the remap OFF, **81 of 83** Technology
  sections fail (>10%); with it ON, they pass. The rule is essential and correctly
  implemented.
- **For these 3 departments, duration data is essentially clean.** The only
  deviations are tiny (≤7 min, e.g. a blended class scheduled 195 min vs expected 200).
  → The "many errors" in the CMR are likely concentrated in *other* validation
  dimensions (rooms, capacity, instructor) or other departments — **not** duration for
  Arch/Eng/Tech. (Confirm where the known errors live.)
- **Tolerance choice now has visible stakes (Q8):** mismatches by rule —
  exact: 36 (all ≤7 min) · 5 min: 1 · 10 min: 0 · 10%: 0 · 5%: 0.

### 5.9 Integrity-check catalog (Step 1b extension) — FINALIZED (best-judgment)

> **Status: all rules below are decided (best judgment, 2026-06-23) and ready to
> build.** They are open to override — flag any that are wrong.

The duration formula (S5.2) is one check. These are **additional, independent**
checks layered on top — they catch errors the formula cannot see (a row can pass
duration yet still be bad, e.g. ARC2580). Each check emits a flag; a row may carry
several. All checks run on the **184-row `Main_` file**, in original order.

**Severity model (two tiers):**
- **Error** = a definite data error that **must be fixed before** the schedule goes to
  faculty selection. Used for the structural errors that corrupt the combined-class
  logic.
- **Warning** = flag for **human review**, non-blocking.

**Candidate-pair definition (basis for B1/B2):** two **adjacent** rows (N, N+1) with the
**same `Class Descr`** (exact) **and** the **same `Concat Days`** — i.e. 2 of the 4 link
conditions already hold, so the pair was *meant* to be one combined class.

| ID | Check | Severity | Flag code |
|---|---|---|---|
| A1 | Linked-pair Cap Enrl mismatch | **Error** | `CAP_MISMATCH` |
| A2 | Linked-pair field consistency (Instr Mode / Session Code / Crs Cntct Hrs) | **Warning** | `PAIR_FIELD_MISMATCH` |
| B1 | Comp mislabel (`LEC/LEC` that should be `LEC/LAB`) | **Error** | `COMP_MISLABEL` |
| B2 | Linked-pair time misalignment | **Error** | `TIME_MISALIGN` |
| B3 | Orphan component | **Warning** | `ORPHAN_LAB` |
| B4 | Duplicate component | **Warning** | `DUPLICATE_COMPONENT` |
| C1 | Rollover / invalid meeting times | **Warning** | `TIME_ROLLOVER` |
| C2 | Internal duration inconsistency | **Warning** | `DURATION_INCONSISTENT` |
| D1 | Missing required fields | **Warning** | `MISSING_FIELDS` |

**Precise rule for each (deterministic):**

- **A1 — `CAP_MISMATCH` (Error).** For a linked LEC↔LAB/PRA pair, `LEC.Cap Enrl` must
  **exactly equal** `LAB/PRA.Cap Enrl`. If not, flag **both** rows. *(ARC2580: 40 ≠ 30.)*

- **A2 — `PAIR_FIELD_MISMATCH` (Warning).** Within a linked pair, flag **both** rows if
  any of `Instr Mode`, `Session Code`, or `Crs Cntct Hrs` differ between LEC and LAB.
  (Days already match by the link rule.) Safety net; does not occur in the current file.

- **B1 — `COMP_MISLABEL` (Error).** For a candidate pair where the 2nd row's `Comp` is
  `LEC` (not LAB/PRA) **and** the 2nd row's `Mtg Start` == the 1st row's `Mtg End`
  (contiguous, to the minute) → the lab was mislabeled as a lecture. Flag **both** rows.
  (Contiguous time + same descr + same days is strong evidence it was meant to be a
  LEC/LAB block. Two same-descr lectures that are **not** contiguous are left alone —
  legitimately separate sections.)

- **B2 — `TIME_MISALIGN` (Error).** For a candidate pair that **is** LEC→LAB/PRA (correct
  components) but the LAB/PRA `Mtg Start` ≠ the LEC `Mtg End` → the only failing link
  condition. Flag **both** rows; in Notes report the gap/overlap in minutes
  (positive = gap, negative = overlap). *(The 6:55 → 7:05 case.)*

- **B3 — `ORPHAN_LAB` (Warning).** In a linked org (300020/450034), a `LAB/PRA` row that
  is **not** part of any valid linked pair (the immediately preceding row is not a LEC
  that links to it). Flag the orphan lab. *(LEC-without-lab detection is out of scope —
  it would require catalog data on which courses require a lab.)*

- **B4 — `DUPLICATE_COMPONENT` (Warning).** Two rows with **identical** `Class Descr`,
  `Comp`, `Concat Days`, `Session Code`, **`Instr Mode`**, **`Cap Enrl`**, `Mtg Start`,
  and `Mtg End` → an apparent exact duplicate. Flag both. `Instr Mode` and `Cap Enrl` are
  in the identity key to avoid false positives on legitimately distinct sections that
  merely share a time slot — e.g. an In-Person and an MDC-Live section of the same course
  at the same time (real case found in CGS1060C during the first run).

- **C1 — `TIME_ROLLOVER` (Warning).** Any row with both `Mtg Start` and `Mtg End` present
  where `Mtg End` ≤ `Mtg Start`. This captures AM/PM and hour rollovers (an end that
  computes at/before the start). Needs human eyes.

- **C2 — `DURATION_INCONSISTENT` (Warning).** The `Duration` column (in minutes) must
  equal (`Mtg End` − `Mtg Start`) in minutes, compared to the minute. If they disagree,
  the source row is self-contradictory → flag. (Skipped for EX/IN, which have no meeting
  pattern.)

- **D1 — `MISSING_FIELDS` (Warning).** For an **active** section that requires a meeting
  pattern (Instr Mode not EX/IN): flag if any of `Mtg Start`, `Mtg End`, or
  `Concat Days` is blank, or if `Cap Enrl` is blank. (The `9999` sentinel is already
  removed in Step 1.)

**Output (two new appended columns, in addition to the duration columns in S5.6):**

| Column | Meaning |
|---|---|
| Integrity Status | `Error` / `Warning` / `OK` (highest severity among this row's flags) |
| Integrity Flags | semicolon-separated `CODE: detail` list (empty if OK) |

The duration validation columns (S5.6) are independent — a row can be duration-
`Validated` while carrying an `Integrity Status = Error` (ARC2580 is exactly this).

**First-run integrity results (184 sections, after 450060 no-lab rule):**
Error 2 · Warning 0 · OK 182.
- `CAP_MISMATCH` ×2 — **ARC2580** "Arch Structures 1": LEC cap 40 ≠ LAB cap 30 (Error).
  The only real defect in the 3 departments.
- Duration: 135 Validated · 48 linked · **1 Ignored** (CTS1120 LAB, 450060 no-lab rule).
- (CTS1120's earlier `MISSING_FIELDS` warning is now suppressed — that lab is ignored
  per the 450060 rule. A B4 false positive on CGS1060C was caught during the run and the
  rule tightened — see B4.) Implemented in `cmr_pipeline/integrity.py`.

### 5.10 LLM analysis layer (live Claude wiring)

Deterministic results are fed to Claude for a human-readable narrative ("best of both
worlds" — rules stay in Python, the LLM only interprets). `cmr_pipeline/analysis.py`:

- Always writes `analysis_prompt.txt` (exact prompt), `analysis_summary.md`
  (deterministic narrative), and `summary.json`.
- **Live call:** builds an Anthropic client from `ANTHROPIC_API_KEY` (or
  `ANTHROPIC_AUTH_TOKEN`), honors `ANTHROPIC_BASE_URL`, and trusts the agent-proxy CA
  (`/root/.ccr/ca-bundle.crt`). On success writes `analysis_llm.md`; otherwise writes
  `analysis_llm_SKIPPED.txt` with the reason. Model via `ANTHROPIC_MODEL`
  (default `claude-opus-4-8`). Disable with `--no-analyze`.
- **Verified:** the call path reaches the live API through the proxy (a dummy key
  returns a real `401 invalid x-api-key` with a request_id). Set a valid
  `ANTHROPIC_API_KEY` to produce `analysis_llm.md`.

### 5.7 Implementation approach (recommended)

- Build as a **deterministic rules engine** (Python), with this spec as the written
  reference — *not* a literal LLM prompt. The arithmetic and row-adjacency logic must
  be exact and reproducible across 184+ rows. Optionally use an LLM only for fuzzy
  value parsing or natural-language Notes (hybrid).
- Validated against real data: e.g. 300020 "Arch Design 1" (P, MW, full term, 48 cch):
  LEC 25 min + LAB 50 min = 75 min combined; expected `48×50/16/2 = 75` → **Validated**.
  Blended example (48 cch, 12W, 1 day): LEC 55 + LAB 45 = 100; expected `48×50/12/1 = 200`,
  halved = 100 → **Validated**. Formula and combine-logic confirmed against the CMR.

## 6. Step 2 — Selection

- **2a — Full-Time Faculty** pick first ("first dibs"). Signals: `KENDL FTF`,
  `Assigned Instr(s)?`, `Instructor`, `FTF_Kendall` + `Chairs` tables, `Workload` tab.
- **2b — Adjunct sub-process** for leftover/unselected sections: coordination,
  availability, schedule collection. Signals: `KENDL ADJ`, `ADJ_Kendall` table,
  `PT Kendl` pivot. **Mailbox/auto-respond integration lives here.**

### 6.1 Adjunct pool extraction (IMPLEMENTED)

**Rule:** a class with **`Assigned Instr(s)? = N`** has no instructor assigned and
therefore falls to the **adjunct pool** (an adjunct must be found for it). Extract all
`N` rows into a separate tab.

- Implemented in `cmr_pipeline/step2_adjunct.py`; runs on the Step 1 / Step 1b output.
- **Ignored rows excluded:** spurious 450060 labs (the 450060 no-lab rule) are not real
  sections to staff, so they're left out of the pool.
- **First-run result:** **38** sections in the adjunct pool (Architecture 10,
  Engineering 12, Technology 16). (39 rows are `N`; 1 is the ignored CTS1120 lab.)
- Output: a dedicated **`Adjunct Pool`** tab in the processed workbook, plus a standalone
  `Adjunct_Pool.xlsx`.

## 6b. Web UI (IMPLEMENTED)

`webapp/` is a Flask app to upload a CMR and run the pipeline through Step 2.

- **Run:** `pip install -r requirements.txt` then `python -m webapp.app`
  (visit `http://localhost:5000`). Optional `PORT=` and `ANTHROPIC_API_KEY=` (enables the
  live Claude analysis).
- **Flow:** upload `.xlsb`/`.xlsx` → Step 0 ingest → Step 1 filter → Step 1b duration +
  integrity → Step 2 adjunct pool → results page with summary cards (sections in scope,
  duration mismatches, integrity errors/warnings, adjunct pool), an integrity-issues
  table, the adjunct-pool table, and downloads (processed workbook with Main + Adjunct
  Pool tabs, focused reports, analysis).
- The pipeline is exposed programmatically via `cmr_pipeline.run.process(cmr, out_dir)`.

## 7. Step 3 — Classroom Assignment & Step 4 — Capacity Check *(to be captured)*

- **Step 3:** assign rooms via `Facility ID`/`Building`/`Room ID`/`Room Capacity`,
  the `Rooms` tab, and `Room_Cap` + `Times` tables. **Prompts (gateways/constraints/
  validations) to be supplied.**
- **Step 4:** validate `Cap Enrl`, `Tot Enrl`, `Seat Available`, `SCH`,
  `Room Capacity` against the `Load_Enrl` table. **Prompts to be supplied.**

---

## 8. Open Questions

| # | Question | Status |
|---|---|---|
| Q1 | What does **CMR** actually stand for? | Open (working: Course/Class Master Report) |
| Q2 | Should the pipeline **write back into the .xlsb** or to a proper data store (DB) with spreadsheet import/export? | Open |
| Q3 | Mailbox provider — Gmail vs Microsoft 365 / Outlook? (MDC is typically Microsoft.) | Open |
| Q4 | POC scope: Kendall + Spring 2027 only, or campus/term-agnostic from the start? | Open (assuming Kendall + 2273 for POC) |
| Q5 | Step 1 filter authority: `Acad Org` only (278) vs `Acad Org` + Kendall location (277)? | Resolved → filter by `Acad Org` (ownership); location tracked separately. |
| Q6 | Reconcile step numbering (Filter vs Duration as "Step 1"). | Open |
| Q7 | Should excluded rows (non-active 42, `9999`-cap 52) be dropped entirely or set aside in the master CMR? | Open (default: set aside, don't delete) |
| Q8 | Duration tolerance | **DECIDED: 10% of expected** (within-tolerance passes but is flagged/noted); configurable. |
| Q9 | Confirm 450060 remap (80→64, 64→48) applies only to Acad Org 450060 and to all its sections. | Open (working: yes, clock→contact hr conversion) |
| Q10 | "Main_" file = the Step 1 filtered 184-row output? | Open (adjacency basis = Main_ file: **confirmed**) |
| Q11 | Dynamic sessions (`DYN`/`DYS`): compute weeks from `Start/End Date` when Session Code not in week map? | Open |
| Q12 | Step 1b is a **remediation gate**: should the app auto-fix durations, or only flag for human correction before Step 2? | Open |

---

## 9. Decision Log

| Date | Decision |
|---|---|
| 2026-06-23 | POC scope set to **Kendall + Term 2273 (Spring 2027)**, 3 departments (Architecture/Engineering/Technology). |
| 2026-06-23 | Step 1 filter targets **`Acad Org` ∈ {300020, 450034, 450060}**, validated to 278 rows. |
| 2026-06-23 | **Canonical Step 1 filter CONFIRMED**: `Acad Org ∈ {300020,450034,450060}` + `Class Status = A` + `Cap Enrl ≠ 9999` → **184 sections** (matches manual count). `9999` is a sentinel-cap category (52 rows), not a single row. |
| 2026-06-23 | Step 1 scoped by **`Acad Org` (department ownership)**; physical location handled later (Q5 resolved). |
| 2026-06-23 | **Core objective recorded:** Steps 1–1b are a data-quality/cleaning effort — validate & fix the CMR *before* it goes to faculty for selection. Step 1b (Duration Validation) is a **remediation gate**, not just a report. |
| 2026-06-23 | Duration Validation spec captured from `Instructions_for_Duration_Validation_Fall_Spring.docx`; formula confirmed against real CMR data. |
| 2026-06-23 | **Duration tolerance decided = 10% of expected** (within-tolerance → Validated + flagged note; configurable to 10-min mode). 36 rows flagged within-tolerance in this file, 0 mismatches. |
| 2026-06-23 | **Live Claude analysis wired** (`analysis.py`): API key/auth-token + base URL + proxy-CA; writes `analysis_llm.md` when a key is present, else a skip note. Call path verified against the live API (dummy key → real 401). |
| 2026-06-23 | **Integrity-check catalog A1–D1 finalized (best judgment):** two-tier Error/Warning; A1 (cap mismatch) & B1/B2 (mislabel, time-misalign) = Error; A2, B3, B4, C1, C2, D1 = Warning. Candidate-pair = adjacent + same Class Descr + same Concat Days. "Rollover" (C1) defined as `Mtg End ≤ Mtg Start`. Output adds `Integrity Status` + `Integrity Flags` columns. See §5.9. Open to override. |
| 2026-06-23 | **Linked LEC/LAB definition finalized:** LEC immediately precedes lab (LEC first); 1:1 cardinality; exact `Class Descr` match; lab `Mtg Start` == lec `Mtg End` with **zero tolerance** (to the minute). Adjacency = within the `Main_` file. Code updated (removed prior 1-min tolerance). Equal `Cap Enrl` is a **separate** integrity check, not part of linking. |
| 2026-06-23 | Process to be captured in this living document **before** building the application. |
