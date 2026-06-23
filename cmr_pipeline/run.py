"""CLI / programmatic orchestrator for the CMR pipeline (POC).

Usage:
    python -m cmr_pipeline.run <CMR.xlsb> [--out OUTPUT_DIR] [--no-analyze]

Runs: read Schedule -> Step 1 filter -> Step 1b duration validation + integrity
-> Step 2 adjunct-pool extraction -> write workbook (Main + Adjunct Pool tabs) +
reports + analysis.

``process()`` returns a structured result dict for programmatic callers (e.g. the UI).
"""
from __future__ import annotations

import argparse
import os

from . import io, step1_filter, step1b_duration, integrity, step2_adjunct, analysis
from .step1b_duration import OUTPUT_COLS as DUR_COLS, C_STATUS
from .integrity import OUTPUT_COLS as INT_COLS
from . import config

OUTPUT_COLS = DUR_COLS + INT_COLS

MAIN_WORKBOOK = "Main_CMR_Processed.xlsx"


def process(cmr_path: str, out_dir: str, want_llm: bool = True) -> dict:
    """Run the full pipeline. Returns a structured result dict and writes artifacts."""
    os.makedirs(out_dir, exist_ok=True)

    headers, rows = io.read_schedule(cmr_path)

    kept, freport = step1_filter.filter_schedule(rows)
    dreport = step1b_duration.validate(kept)
    ireport = integrity.check(kept)
    adjunct_rows, areport = step2_adjunct.extract_adjunct_pool(kept)

    # --- workbook with Main + Adjunct Pool tabs ---
    main_path = os.path.join(out_dir, MAIN_WORKBOOK)
    io.write_sheets(main_path,
                    [("Main", kept), ("Adjunct Pool", adjunct_rows)],
                    headers, extra_cols=OUTPUT_COLS)

    # --- focused reports ---
    mismatches = [r for r in kept if r.get(C_STATUS) == config.STATUS_MISMATCH]
    int_rows = ireport["errors"] + ireport["warnings"]
    io.write_rows(os.path.join(out_dir, "Duration_Mismatch_Report.xlsx"),
                  headers, mismatches, extra_cols=OUTPUT_COLS, sheet_name="Mismatches")
    io.write_rows(os.path.join(out_dir, "Integrity_Report.xlsx"),
                  headers, int_rows, extra_cols=OUTPUT_COLS, sheet_name="Integrity")
    io.write_rows(os.path.join(out_dir, "Adjunct_Pool.xlsx"),
                  headers, adjunct_rows, extra_cols=OUTPUT_COLS, sheet_name="Adjunct Pool")

    # --- analysis (deterministic + live Claude) ---
    summary = analysis.build_summary(freport, dreport, ireport)
    artifacts = analysis.run(summary, want_llm=want_llm)
    for name, text in artifacts.items():
        with open(os.path.join(out_dir, name), "w") as fh:
            fh.write(text)

    return {
        "headers": headers,
        "filter": freport,
        "duration": dreport,
        "integrity": ireport,
        "adjunct": areport,
        "adjunct_rows": adjunct_rows,
        "kept": kept,
        "out_dir": out_dir,
        "main_workbook": MAIN_WORKBOOK,
        "llm": "analysis_llm.md" if "analysis_llm.md" in artifacts else None,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="CMR course-selection pipeline (POC)")
    ap.add_argument("cmr", help="Path to the CMR .xlsb workbook")
    ap.add_argument("--out", default="output", help="Output directory")
    ap.add_argument("--no-analyze", action="store_true",
                    help="Skip the live Claude analysis call (still writes prompt+summary)")
    args = ap.parse_args(argv)

    print(f"[step 0] Reading {args.cmr} ...")
    r = process(args.cmr, args.out, want_llm=not args.no_analyze)

    print(f"[step 1]  kept {r['filter']['kept']} sections  (by org: {r['filter']['by_org']})")
    print(f"[step 1b] duration: {r['duration']['status_counts']}")
    print(f"          mismatches: {r['duration']['mismatch_count']}  "
          f"(tolerance: {r['duration']['tolerance']}; "
          f"within-tolerance flagged: {r['duration'].get('within_tolerance_count', 0)})")
    print(f"[step 1b] integrity: {r['integrity']['status_counts']}  "
          f"flags: {r['integrity']['code_counts']}")
    print(f"[step 2]  adjunct pool (Assigned Instr(s)?=N): {r['adjunct']['adjunct_count']}  "
          f"(by org: {r['adjunct']['by_org']})")
    print(f"[analysis] live Claude: {'OK -> analysis_llm.md' if r['llm'] else 'skipped'}")
    print(f"[out] workbook: {os.path.join(args.out, r['main_workbook'])}")
    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
