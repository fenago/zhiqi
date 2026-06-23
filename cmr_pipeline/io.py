"""Workbook I/O for the CMR pipeline.

Reads the ``Schedule`` tab of the ``.xlsb`` CMR into a list of row dicts (original
order preserved, with an ``_row`` index for adjacency logic), and writes results
back out as ``.xlsx`` plus a mismatch-only report.
"""
from __future__ import annotations

from pyxlsb import open_workbook
from openpyxl import Workbook

SCHEDULE_SHEET = "Schedule"


def read_schedule(path: str, sheet: str = SCHEDULE_SHEET):
    """Read a sheet into (headers, rows).

    ``rows`` is a list of dicts keyed by header name. Each row also carries
    ``_row`` = its 0-based position in the original sheet data (for adjacency).
    """
    headers: list[str] = []
    rows: list[dict] = []
    with open_workbook(path) as wb:
        with wb.get_sheet(sheet) as sh:
            col_index: dict[int, str] = {}
            data_pos = 0
            for r in sh.rows():
                cells = {c.c: c.v for c in r}
                ri = r[0].r if r else None
                if ri == 0:  # header row
                    for ci, v in cells.items():
                        col_index[ci] = str(v)
                    headers = [col_index[k] for k in sorted(col_index)]
                    continue
                row = {col_index.get(ci, f"col{ci}"): v for ci, v in cells.items()}
                # ensure every header key exists
                for h in headers:
                    row.setdefault(h, None)
                row["_row"] = data_pos
                data_pos += 1
                rows.append(row)
    return headers, rows


def write_rows(path: str, headers: list[str], rows: list[dict],
               extra_cols: list[str] | None = None, sheet_name: str = "Sheet1"):
    """Write rows to an .xlsx file. ``extra_cols`` are appended after ``headers``."""
    return write_sheets(path, [(sheet_name, rows)], headers, extra_cols)


def write_sheets(path: str, sheets: list[tuple[str, list[dict]]],
                 headers: list[str], extra_cols: list[str] | None = None):
    """Write multiple named sheets to one .xlsx. ``sheets`` = [(name, rows), ...]."""
    extra_cols = extra_cols or []
    out_headers = list(headers) + [c for c in extra_cols if c not in headers]
    wb = Workbook()
    for i, (name, rows) in enumerate(sheets):
        ws = wb.active if i == 0 else wb.create_sheet()
        ws.title = name[:31]  # Excel sheet-name limit
        ws.append(out_headers)
        for row in rows:
            ws.append([_clean(row.get(h)) for h in out_headers])
    wb.save(path)
    return path


def _clean(v):
    """openpyxl can't store some pyxlsb artifacts; coerce to safe types."""
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float, str)):
        return v
    return str(v)
