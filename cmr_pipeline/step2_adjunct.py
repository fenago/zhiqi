"""Step 2 (start) - Adjunct pool extraction.

Faculty selection: any class whose `Assigned Instr(s)?` == 'N' has no instructor
assigned and therefore falls to the **adjunct pool** (an adjunct must be found for
it). This module extracts those rows into a separate tab/list.

Ignored rows (spurious 450060 labs) are excluded - they are not real sections to
staff.
"""
from __future__ import annotations

from .step1b_duration import is_ignored

ASSIGNED_COL = "Assigned Instr(s)?"
UNASSIGNED = "N"


def extract_adjunct_pool(rows: list[dict]):
    """Return (adjunct_rows, report). Order preserved."""
    pool = [r for r in rows
            if str(r.get(ASSIGNED_COL)).strip() == UNASSIGNED and not is_ignored(r)]

    def org(r):
        return str(r.get("Acad Org")).split(".")[0]

    by_org: dict[str, int] = {}
    for r in pool:
        by_org[org(r)] = by_org.get(org(r), 0) + 1

    report = {
        "adjunct_count": len(pool),
        "assigned_count": sum(1 for r in rows
                              if str(r.get(ASSIGNED_COL)).strip() == "Y"),
        "by_org": by_org,
    }
    return pool, report
