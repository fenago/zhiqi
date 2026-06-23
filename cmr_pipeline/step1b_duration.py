"""Step 1b - Duration validation (data-quality / cleaning gate).

Validates that each section's scheduled meeting duration matches the expected
duration derived from contact hours, weeks, and meeting days. Mismatches are the
data errors to fix before the schedule goes to faculty for selection.

Spec: docs/CMR_Course_Selection_Process.md S5, from
Instructions_for_Duration_Validation_Fall_Spring.docx.

Appends 4 columns to each row:
  Current Duration (min), Expected Duration (min), Validation Status, Notes
"""
from __future__ import annotations

from . import config

# Output column names
C_CURRENT = "Current Duration (min)"
C_EXPECTED = "Expected Duration (min)"
C_STATUS = "Validation Status"
C_NOTES = "Notes"
OUTPUT_COLS = [C_CURRENT, C_EXPECTED, C_STATUS, C_NOTES]


# ---- small helpers ----------------------------------------------------------
def _org(row) -> str:
    v = row.get("Acad Org")
    return "" if v is None else str(v).split(".")[0]


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _instr_code(row) -> str:
    """'P (In Person)' -> 'P', 'BL (Blended)' -> 'BL'."""
    v = row.get("Instr Mode")
    if not v:
        return ""
    return str(v).split("(")[0].strip().split()[0] if str(v).strip() else ""


def _comp(row) -> str:
    v = row.get("Comp")
    return "" if v is None else str(v).strip().upper()


def is_ignored(row) -> bool:
    """LAB/PRA rows in a no-lab Acad Org (e.g. 450060) are ignored everywhere."""
    return _org(row) in config.NO_LAB_ORGS and _comp(row) in config.LAB_COMPONENTS


def _days(row) -> int:
    v = row.get("Concat Days")
    if not v:
        return 0
    return sum(1 for ch in str(v).upper() if ch in config.DAY_LETTERS)


def _weeks(row):
    return config.WEEK_MAP.get(str(row.get("Session Code")).strip())


def _duration_min(row):
    """Duration is stored as fraction-of-day; minutes = frac * 1440."""
    d = _f(row.get("Duration"))
    return None if d is None else round(d * 1440, 1)


def _cch(row):
    """Contact hours, with the 450060 remap applied."""
    cch = _f(row.get("Crs Cntct Hrs"))
    if cch is None:
        return None
    if _org(row) == config.REMAP_ORG and cch in config.CCH_REMAP:
        cch = config.CCH_REMAP[cch]
    return cch


def _expected_min(cch, weeks, days, factor):
    if not weeks or not days or cch is None or factor is None:
        return None
    return round(cch * config.CONTACT_HOUR_MINUTES / weeks / days * factor, 1)


def _within_tolerance(actual, expected) -> bool:
    diff = abs(actual - expected)
    if config.TOLERANCE_MODE == "minutes":
        return diff <= config.TOLERANCE_MINUTES
    return diff <= config.TOLERANCE_PCT * expected


def _note_for(actual, expected) -> str:
    diff = round(expected - actual, 1)
    if diff == 0:
        return ""
    if diff > 0:
        return f"Add {abs(diff):g} min"
    return f"Subtract {abs(diff):g} min"


# ---- linking ----------------------------------------------------------------
def _is_linked_pair(lec, lab) -> bool:
    """True if `lab` (LAB/PRA) links to `lec` (LEC) per the spec conditions.

    ALL must hold (Acad Org 300020/450034 only; checked by caller):
      1. lec is LEC, lab is LAB or PRA (LEC immediately precedes the lab)
      2. same Class Descr (exact, case/space-sensitive)
      3. same Concat Days
      4. lab Mtg Start == lec Mtg End, exactly (zero tolerance, to the minute)
    Cardinality is 1:1 -- the caller pairs a LEC with only the next row.
    """
    if _comp(lec) != "LEC" or _comp(lab) not in config.LAB_COMPONENTS:
        return False
    if lec.get("Class Descr") != lab.get("Class Descr"):       # exact match
        return False
    if str(lec.get("Concat Days")) != str(lab.get("Concat Days")):
        return False
    lec_end = _f(lec.get("Mtg End"))
    lab_start = _f(lab.get("Mtg Start"))
    if lec_end is None or lab_start is None:
        return False
    # Zero tolerance: LAB/PRA must start exactly when the LEC ends (to the minute).
    return round(lab_start * 1440) == round(lec_end * 1440)


# ---- main -------------------------------------------------------------------
def validate(rows: list[dict]):
    """Validate durations in place (rows mutated with output cols). Returns report."""
    n = len(rows)
    handled = [False] * n  # rows already consumed as a linked LAB/PRA

    for i, row in enumerate(rows):
        if handled[i]:
            continue

        if is_ignored(row):  # spurious LAB/PRA in a no-lab org (e.g. 450060)
            _set(row, _duration_min(row), None, config.STATUS_IGNORED,
                 f"Acad Org {_org(row)} has no lab component")
            continue

        org = _org(row)
        comp = _comp(row)
        actual = _duration_min(row)

        # Try to form a linked LEC + LAB/PRA pair (adjacent rows, linked orgs only)
        if org in config.LINKED_ORGS and comp == "LEC" and i + 1 < n:
            nxt = rows[i + 1]
            if not handled[i + 1] and _is_linked_pair(row, nxt):
                _validate_linked(row, nxt)
                handled[i + 1] = True
                continue

        # Standalone validation (also covers unlinked LAB/PRA and 450060)
        _validate_single(row)

    return _build_report(rows)


def _validate_single(row):
    actual = _duration_min(row)
    code = _instr_code(row)
    factor = config.INSTR_MODE_FACTOR.get(code, 1.0)
    cch = _cch(row)
    weeks = _weeks(row)
    days = _days(row)

    if factor is None:  # EX / IN -> no meeting pattern
        _set(row, actual, None, config.STATUS_NA, "")
        return
    if cch in (None, 0.0):
        _set(row, actual, None, config.STATUS_INSUFFICIENT, "No contact hours")
        return

    expected = _expected_min(cch, weeks, days, factor)
    if actual is None or expected is None:
        _set(row, actual, expected, config.STATUS_INSUFFICIENT,
             "Missing duration/weeks/days")
        return

    if _within_tolerance(actual, expected):
        note = "" if actual == expected else f"Within tolerance ({_note_for(actual, expected)})"
        _set(row, actual, expected, config.STATUS_VALIDATED, note)
    else:
        _set(row, actual, expected, config.STATUS_MISMATCH, _note_for(actual, expected))


def _validate_linked(lec, lab):
    """Validate a linked LEC + LAB/PRA as one combined block; result on LEC row."""
    lec_actual = _duration_min(lec) or 0.0
    lab_actual = _duration_min(lab) or 0.0
    combined_actual = round(lec_actual + lab_actual, 1)

    code = _instr_code(lec)
    factor = config.INSTR_MODE_FACTOR.get(code, 1.0)
    cch = _cch(lec)  # expected from LEC's contact hours only
    weeks = _weeks(lec)
    days = _days(lec)
    expected = _expected_min(cch, weeks, days, factor) if factor is not None else None

    if expected is None or factor is None or cch in (None, 0.0):
        _set(lec, combined_actual, None, config.STATUS_INSUFFICIENT,
             "Linked: missing data")
        _set(lab, _duration_min(lab), config.SEE_ABOVE, config.STATUS_LINKED,
             config.SEE_ABOVE)
        return

    if _within_tolerance(combined_actual, expected):
        note = "" if combined_actual == expected else f"Within tolerance ({_note_for(combined_actual, expected)})"
        _set(lec, combined_actual, expected, config.STATUS_VALIDATED, note)
        _set(lab, _duration_min(lab), config.SEE_ABOVE, config.STATUS_LINKED,
             config.SEE_ABOVE)
    else:
        # mismatch -> both rows marked Mismatch
        _set(lec, combined_actual, expected, config.STATUS_MISMATCH,
             _note_for(combined_actual, expected))
        _set(lab, _duration_min(lab), config.SEE_ABOVE, config.STATUS_MISMATCH,
             config.SEE_ABOVE)


def _set(row, current, expected, status, notes):
    row[C_CURRENT] = current
    row[C_EXPECTED] = expected
    row[C_STATUS] = status
    row[C_NOTES] = notes


def _build_report(rows):
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.get(C_STATUS)] = counts.get(r.get(C_STATUS), 0) + 1
    mismatches = [r for r in rows if r.get(C_STATUS) == config.STATUS_MISMATCH]
    return {
        "total": len(rows),
        "status_counts": counts,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "tolerance": (config.TOLERANCE_MODE,
                      config.TOLERANCE_PCT if config.TOLERANCE_MODE == "pct"
                      else config.TOLERANCE_MINUTES),
    }
