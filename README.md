# MDC CMR Course-Selection Pipeline (POC)

Deterministic pipeline + web UI to ingest the Miami Dade College **CMR** schedule
export, validate/clean it, and prepare it for faculty course selection.

Full process spec: [`docs/CMR_Course_Selection_Process.md`](docs/CMR_Course_Selection_Process.md).

## What it does (Steps 0 → 2)

- **Step 0 – Ingest** the CMR `.xlsb` workbook (Schedule tab).
- **Step 1 – Filter** to Kendall Architecture / Engineering / Technology
  (`Acad Org` ∈ {300020, 450034, 450060}, active, `Cap Enrl ≠ 9999`) → 184 sections.
- **Step 1b – Validate & clean** (data-quality gate before faculty selection):
  - **Duration validation** — `Expected = Crs Cntct Hrs × 50 ÷ weeks ÷ days`
    (BL = ×0.5; 450060 contact-hour remap; linked LEC+LAB/PRA combined), 10% tolerance.
  - **Integrity checks (A1–D1)** — cap mismatch, mislabel, time misalignment, orphan
    lab, duplicates, rollovers, missing fields. Two-tier Error / Warning.
- **Step 2 – Adjunct pool** — extract unassigned sections (`Assigned Instr(s)? = N`).
- **Analysis** — deterministic summary + optional live Claude narrative.

## Install

```bash
pip install -r requirements.txt
```

## Run the web UI

```bash
python -m webapp.app          # http://localhost:5000
# optional: PORT=8080  ANTHROPIC_API_KEY=sk-...  (enables live Claude analysis)
```

Upload the CMR, then view results and download the processed workbook
(Main + Adjunct Pool tabs) and reports.

## Run the CLI

```bash
python -m cmr_pipeline.run path/to/CMR.xlsb --out output [--no-analyze]
```

## Layout

```
cmr_pipeline/   deterministic engine (config, io, step1_filter, step1b_duration,
                integrity, step2_adjunct, analysis, run)
webapp/         Flask UI
docs/           living process specification
```
