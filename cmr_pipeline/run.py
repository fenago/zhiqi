"""CLI orchestrator for the CMR pipeline (POC).

Usage:
    python -m cmr_pipeline.run <CMR.xlsb> [--out OUTPUT_DIR]

Runs: read Schedule -> Step 1 filter -> Step 1b duration validation ->
write Main file + mismatch report + analysis artifacts.
"""
from __future__ import annotations

import argparse
import os

from . import io, step1_filter, step1b_duration, integrity, analysis
from .step1b_duration import OUTPUT_COLS as DUR_COLS, C_STATUS
from .integrity import OUTPUT_COLS as INT_COLS
from . import config

OUTPUT_COLS = DUR_COLS + INT_COLS


def main(argv=None):
    ap = argparse.ArgumentParser(description="CMR course-selection pipeline (POC)")
    ap.add_argument("cmr", help="Path to the CMR .xlsb workbook")
    ap.add_argument("--out", default="output", help="Output directory")
    args = ap.parse_args(argv)

    os.makedirs(args.out, exist_ok=True)

    print(f"[step 0] Reading {args.cmr} ...")
    headers, rows = io.read_schedule(args.cmr)
    print(f"          {len(rows)} schedule rows, {len(headers)} columns")

    print("[step 1] Filtering to 3 Kendall departments ...")
    kept, freport = step1_filter.filter_schedule(rows)
    print(f"          kept {freport['kept']} sections  (by org: {freport['by_org']})")
    print(f"          dropped reasons: {freport['drop_reasons']}")

    print("[step 1b] Validating durations ...")
    dreport = step1b_duration.validate(kept)
    print(f"          status counts: {dreport['status_counts']}")
    print(f"          mismatches: {dreport['mismatch_count']}  "
          f"(tolerance: {dreport['tolerance']})")

    print("[step 1b] Running integrity checks (A1-D1) ...")
    ireport = integrity.check(kept)
    print(f"          integrity: {ireport['status_counts']}")
    print(f"          flags: {ireport['code_counts']}")

    # --- write data artifacts ---
    main_path = os.path.join(args.out, "Main_Step1b_Duration_Validated.xlsx")
    io.write_rows(main_path, headers, kept, extra_cols=OUTPUT_COLS,
                  sheet_name="Main")
    print(f"[out] {main_path}")

    mismatches = [r for r in kept if r.get(C_STATUS) == config.STATUS_MISMATCH]
    report_path = os.path.join(args.out, "Duration_Mismatch_Report.xlsx")
    io.write_rows(report_path, headers, mismatches, extra_cols=OUTPUT_COLS,
                  sheet_name="Mismatches")
    print(f"[out] {report_path}  ({len(mismatches)} rows)")

    integrity_rows = ireport["errors"] + ireport["warnings"]
    int_path = os.path.join(args.out, "Integrity_Report.xlsx")
    io.write_rows(int_path, headers, integrity_rows, extra_cols=OUTPUT_COLS,
                  sheet_name="Integrity")
    print(f"[out] {int_path}  ({len(integrity_rows)} rows)")

    # --- analysis layer ---
    summary = analysis.build_summary(freport, dreport, ireport)
    for name, text in analysis.run(summary).items():
        p = os.path.join(args.out, name)
        with open(p, "w") as fh:
            fh.write(text)
        print(f"[out] {p}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
