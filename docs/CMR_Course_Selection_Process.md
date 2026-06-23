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

## 5. Step 1b — Duration *(to be captured)*

Determine session/term offerings and whether new sections must be created.
Driven by `Session Code`, `Duration`, `Class Duration`, `Start/End Date`, validated
against the `Session_Duration` table in *Tables 1–4*. **Prompts to be supplied.**

## 6. Step 2 — Selection *(to be captured)*

- **2a — Full-Time Faculty** pick first ("first dibs"). Signals: `KENDL FTF`,
  `Assigned Instr(s)?`, `Instructor`, `FTF_Kendall` + `Chairs` tables, `Workload` tab.
- **2b — Adjunct sub-process** for leftover/unselected sections: coordination,
  availability, schedule collection. Signals: `KENDL ADJ`, `ADJ_Kendall` table,
  `PT Kendl` pivot. **Mailbox/auto-respond integration lives here.**

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

---

## 9. Decision Log

| Date | Decision |
|---|---|
| 2026-06-23 | POC scope set to **Kendall + Term 2273 (Spring 2027)**, 3 departments (Architecture/Engineering/Technology). |
| 2026-06-23 | Step 1 filter targets **`Acad Org` ∈ {300020, 450034, 450060}**, validated to 278 rows. |
| 2026-06-23 | **Canonical Step 1 filter CONFIRMED**: `Acad Org ∈ {300020,450034,450060}` + `Class Status = A` + `Cap Enrl ≠ 9999` → **184 sections** (matches manual count). `9999` is a sentinel-cap category (52 rows), not a single row. |
| 2026-06-23 | Step 1 scoped by **`Acad Org` (department ownership)**; physical location handled later (Q5 resolved). |
| 2026-06-23 | Process to be captured in this living document **before** building the application. |
