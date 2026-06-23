"""Step 1b integrity checks (A1-D1) - data-quality layer on top of duration.

These catch errors the duration formula cannot see (cap mismatch, mislabeled
component, broken time alignment, rollovers, etc.). A row can be duration-Validated
yet carry an Integrity Error (e.g. ARC2580). See docs S5.9 for the finalized rules.

Appends two columns:
  Integrity Status  -> Error / Warning / OK   (highest severity on the row)
  Integrity Flags   -> "CODE: detail; CODE: detail"  (empty if OK)
"""
from __future__ import annotations

from . import config
from .step1b_duration import _f, _comp, _org, _is_linked_pair, _instr_code, is_ignored

C_INT_STATUS = "Integrity Status"
C_INT_FLAGS = "Integrity Flags"
OUTPUT_COLS = [C_INT_STATUS, C_INT_FLAGS]

ERROR = "Error"
WARNING = "Warning"
OK = "OK"

# Modes that require a meeting pattern (for D1 completeness).
MEETING_MODES = {"P", "LV", "BL"}


def _min(v):
    """Fraction-of-day -> integer minutes (rounded), or None."""
    f = _f(v)
    return None if f is None else round(f * 1440)


def _descr(r):
    return r.get("Class Descr")


def _days(r):
    return str(r.get("Concat Days") or "")


def _course(r):
    pre = str(r.get("Course Prefix (Subject)") or "").strip()
    num = str(r.get("Course Number (Catalog Nbr)") or "").strip().split(".")[0]
    return f"{pre}{num}"


def check(rows: list[dict]):
    """Run all integrity checks; mutate rows with the two output cols. Return report."""
    n = len(rows)
    flags: list[list[tuple[str, str, str]]] = [[] for _ in range(n)]  # (severity, code, detail)
    ignored = [is_ignored(r) for r in rows]  # spurious LAB/PRA in no-lab orgs

    def add(i, severity, code, detail=""):
        flags[i].append((severity, code, detail))

    # --- precompute linked pairs (same logic as duration) ---
    linked: dict[int, int] = {}      # lec index -> lab index
    linked_lab: set[int] = set()
    for i in range(n - 1):
        a, b = rows[i], rows[i + 1]
        if _org(a) in config.LINKED_ORGS and _comp(a) == "LEC" and _is_linked_pair(a, b):
            linked[i] = i + 1
            linked_lab.add(i + 1)

    # --- A1 / A2: within linked pairs ---
    for lec_i, lab_i in linked.items():
        lec, lab = rows[lec_i], rows[lab_i]
        # A1 cap mismatch (Error)
        if _f(lec.get("Cap Enrl")) != _f(lab.get("Cap Enrl")):
            d = f"LEC cap {_f(lec.get('Cap Enrl'))} vs LAB cap {_f(lab.get('Cap Enrl'))}"
            add(lec_i, ERROR, "CAP_MISMATCH", d)
            add(lab_i, ERROR, "CAP_MISMATCH", d)
        # A2 field consistency (Warning)
        diffs = []
        if str(lec.get("Instr Mode")) != str(lab.get("Instr Mode")):
            diffs.append("Instr Mode")
        if str(lec.get("Session Code")) != str(lab.get("Session Code")):
            diffs.append("Session Code")
        if _f(lec.get("Crs Cntct Hrs")) != _f(lab.get("Crs Cntct Hrs")):
            diffs.append("Crs Cntct Hrs")
        if diffs:
            d = "pair differs on: " + ", ".join(diffs)
            add(lec_i, WARNING, "PAIR_FIELD_MISMATCH", d)
            add(lab_i, WARNING, "PAIR_FIELD_MISMATCH", d)

    # --- B1 / B2: candidate pairs (linked orgs only) ---
    for i in range(n - 1):
        a, b = rows[i], rows[i + 1]
        if _org(a) not in config.LINKED_ORGS:
            continue
        # candidate pair = adjacent + same Class Descr (exact) + same Concat Days
        if _descr(a) != _descr(b) or _days(a) != _days(b):
            continue
        a_end, b_start = _min(a.get("Mtg End")), _min(b.get("Mtg Start"))
        if _comp(a) == "LEC" and _comp(b) == "LEC":
            # B1 mislabel: 2nd LEC starts exactly when 1st ends -> should be a LAB
            if a_end is not None and b_start is not None and a_end == b_start:
                d = f"adjacent same-descr LEC/LEC, contiguous at {_hm(a_end)} - 2nd row likely a mislabeled LAB"
                add(i, ERROR, "COMP_MISLABEL", d)
                add(i + 1, ERROR, "COMP_MISLABEL", d)
        elif _comp(a) == "LEC" and _comp(b) in config.LAB_COMPONENTS:
            # B2 misalignment: LEC->LAB but times don't line up
            if a_end is not None and b_start is not None and a_end != b_start:
                gap = b_start - a_end
                kind = "gap" if gap > 0 else "overlap"
                d = f"LAB starts {_hm(b_start)} but LEC ends {_hm(a_end)} ({abs(gap)} min {kind})"
                add(i, ERROR, "TIME_MISALIGN", d)
                add(i + 1, ERROR, "TIME_MISALIGN", d)

    # --- B3: orphan lab (linked orgs only) ---
    for i in range(n):
        r = rows[i]
        if _org(r) in config.LINKED_ORGS and _comp(r) in config.LAB_COMPONENTS \
                and i not in linked_lab:
            add(i, WARNING, "ORPHAN_LAB", "LAB/PRA not linked to a preceding LEC")

    # --- B4: exact duplicate component (all rows) ---
    # Strict identity key: same course/comp/days/session/mode/times/cap. Including
    # Instr Mode and Cap Enrl avoids flagging legitimately distinct sections that
    # merely share a time slot (e.g. an In-Person and an MDC-Live section).
    seen: dict[tuple, list[int]] = {}
    for i, r in enumerate(rows):
        if ignored[i]:
            continue
        key = (_descr(r), _comp(r), _days(r), str(r.get("Session Code")),
               str(r.get("Instr Mode")), _f(r.get("Cap Enrl")),
               _min(r.get("Mtg Start")), _min(r.get("Mtg End")))
        seen.setdefault(key, []).append(i)
    for key, idxs in seen.items():
        if len(idxs) > 1 and key[0] is not None:
            d = f"{len(idxs)} identical rows ({_course(rows[idxs[0]])} {key[1]} {key[2]} {key[4][:2]})"
            for i in idxs:
                add(i, WARNING, "DUPLICATE_COMPONENT", d)

    # --- C1 / C2: time integrity (all rows) ---
    for i, r in enumerate(rows):
        if ignored[i]:
            continue
        ms, me = _min(r.get("Mtg Start")), _min(r.get("Mtg End"))
        dur = _min(r.get("Duration"))
        code = _instr_code(r)
        if ms is not None and me is not None:
            if me <= ms:
                add(i, WARNING, "TIME_ROLLOVER",
                    f"Mtg End {_hm(me)} <= Mtg Start {_hm(ms)}")
            elif code in MEETING_MODES and dur is not None and dur != (me - ms):
                add(i, WARNING, "DURATION_INCONSISTENT",
                    f"Duration {dur} min != (End-Start) {me - ms} min")

    # --- D1: missing required fields (active, meeting-required) ---
    for i, r in enumerate(rows):
        if ignored[i]:
            continue
        code = _instr_code(r)
        missing = []
        if code in MEETING_MODES:
            if _min(r.get("Mtg Start")) is None:
                missing.append("Mtg Start")
            if _min(r.get("Mtg End")) is None:
                missing.append("Mtg End")
            if not _days(r):
                missing.append("Concat Days")
        if _f(r.get("Cap Enrl")) is None:
            missing.append("Cap Enrl")
        if missing:
            add(i, WARNING, "MISSING_FIELDS", "missing: " + ", ".join(missing))

    # --- write status + flags onto rows ---
    for i, r in enumerate(rows):
        fl = flags[i]
        if any(s == ERROR for s, _, _ in fl):
            status = ERROR
        elif fl:
            status = WARNING
        else:
            status = OK
        r[C_INT_STATUS] = status
        r[C_INT_FLAGS] = "; ".join(f"{c}: {d}" if d else c for _, c, d in fl)

    return _report(rows, flags)


def _hm(minutes):
    if minutes is None:
        return "?"
    h, m = divmod(int(minutes), 60)
    ap = "AM" if h < 12 else "PM"
    hh = h % 12 or 12
    return f"{hh}:{m:02d}{ap}"


def _report(rows, flags):
    status_counts = {"Error": 0, "Warning": 0, "OK": 0}
    code_counts: dict[str, int] = {}
    for r in rows:
        status_counts[r[C_INT_STATUS]] += 1
    for fl in flags:
        for _s, c, _d in fl:
            code_counts[c] = code_counts.get(c, 0) + 1
    return {
        "status_counts": status_counts,
        "code_counts": code_counts,
        "errors": [r for r in rows if r[C_INT_STATUS] == ERROR],
        "warnings": [r for r in rows if r[C_INT_STATUS] == WARNING],
    }
