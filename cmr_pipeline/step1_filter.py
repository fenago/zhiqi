"""Step 1 - Filter the CMR to the 3 Kendall departments (the selection pool).

Filter (in order):
  1. Acad Org in {300020, 450034, 450060}
  2. Class Status == 'A' (active)
  3. Cap Enrl != 9999 (sentinel-cap category excluded)

Validated target: 184 sections.
"""
from __future__ import annotations

from . import config


def _org(row) -> str:
    v = row.get("Acad Org")
    if v is None:
        return ""
    return str(v).split(".")[0]


def _as_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def filter_schedule(rows: list[dict]):
    """Return (kept_rows, report). Order preserved."""
    kept, dropped = [], []
    for row in rows:
        org = _org(row)
        status = row.get("Class Status")
        cap = _as_float(row.get("Cap Enrl"))

        if org not in config.TARGET_ACAD_ORGS:
            reason = "acad_org_out_of_scope"
        elif status != config.ACTIVE_STATUS:
            reason = f"status_{status}"
        elif cap == config.EXCLUDE_CAP_ENRL:
            reason = "cap_enrl_9999_sentinel"
        else:
            reason = None

        if reason is None:
            kept.append(row)
        else:
            dropped.append((row, reason))

    report = {
        "kept": len(kept),
        "dropped": len(dropped),
        "by_org": {o: sum(1 for r in kept if _org(r) == o)
                   for o in sorted(config.TARGET_ACAD_ORGS)},
        "drop_reasons": _count_reasons(dropped),
    }
    return kept, report


def _count_reasons(dropped):
    out: dict[str, int] = {}
    for _row, reason in dropped:
        # collapse the in-scope status drops for readability
        key = reason
        if reason.startswith("status_"):
            key = "status_not_active"
        if reason == "acad_org_out_of_scope":
            continue  # not interesting in a per-dept report
        out[key] = out.get(key, 0) + 1
    return out
