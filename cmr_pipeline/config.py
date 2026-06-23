"""Policy / lookup tables for the CMR pipeline.

Everything here is *policy* (it can change per term, campus, or college rule) and
is deliberately kept out of the logic modules so it can be tuned without touching
code. Each value traces back to the process spec in
``docs/CMR_Course_Selection_Process.md``.
"""

# ---- Step 1: filter ---------------------------------------------------------
# The three target departments (Acad Org codes) -- Kendall campus.
TARGET_ACAD_ORGS = {"300020", "450034", "450060"}
ACAD_ORG_NAMES = {
    "300020": "Architect & Interior Design KE",
    "450034": "Engineering - Kendall",
    "450060": "Technology - Kendall",
}
ACTIVE_STATUS = "A"          # keep only active sections
EXCLUDE_CAP_ENRL = 9999      # sentinel/placeholder cap to exclude

# ---- Step 1b: duration validation ------------------------------------------
CONTACT_HOUR_MINUTES = 50    # 1 "Crs Cntct Hrs" == 50 minutes

# Session Code -> number of weeks
WEEK_MAP = {
    "1": 16, "WKD": 16,
    "6W1": 6, "6W2": 6,
    "8W1": 8, "8W2": 8,
    "10W": 10, "12W": 12, "14W": 14,
}

# Valid day letters in "Concat Days"; the count of these = number of meeting days.
DAY_LETTERS = set("MTWRFS")

# Instr Mode behavior. Codes are parsed from strings like "P (In Person)".
#   full     -> full duration
#   half     -> blended: half meeting pattern / half duration  (expected * 0.5)
#   none     -> no meeting pattern / no duration (validation N/A)
INSTR_MODE_FACTOR = {
    "P": 1.0,    # In Person
    "LV": 1.0,   # MDC Live
    "BL": 0.5,   # Blended
    "EX": None,  # Credit by Exam -> N/A
    "IN": None,  # Independent Study -> N/A
}

# PRA (practicum) is treated as LAB.
LAB_COMPONENTS = {"LAB", "PRA"}

# Acad Orgs that have NO separate lab component. Any LAB/PRA row in these orgs is
# spurious and is ignored (not validated, not integrity-checked). 450060 (Technology)
# courses are single-component (combined C-suffix sections).
NO_LAB_ORGS = {"450060"}

# Orgs whose linked LEC + LAB/PRA pairs are validated as one combined class.
LINKED_ORGS = {"300020", "450034"}

# Acad Org 450060 (Technology) contact-hour remap, applied BEFORE computing
# expected duration. Exact-match lookup (not chained).
REMAP_ORG = "450060"
CCH_REMAP = {80.0: 64.0, 64.0: 48.0}

# ---- Tolerance (Q8 - DECIDED: 10% of total duration) ------------------------
# A class within tolerance is "Validated"; if it is within tolerance but not exact
# it still passes but is flagged + noted ("Within tolerance: ...").
# "pct"     : pass if |actual - expected| <= TOLERANCE_PCT * expected   (default)
# "minutes" : pass if |actual - expected| <= TOLERANCE_MINUTES (alt; doc also cites 10 min)
TOLERANCE_MODE = "pct"
TOLERANCE_PCT = 0.10         # 10% of total duration
TOLERANCE_MINUTES = 10       # alternative absolute tolerance


def tolerance_label() -> str:
    if TOLERANCE_MODE == "minutes":
        return f"{TOLERANCE_MINUTES} min"
    return f"{TOLERANCE_PCT:.0%} of expected"

# ---- Validation status labels ----------------------------------------------
STATUS_VALIDATED = "Validated"
STATUS_MISMATCH = "Mismatch"
STATUS_LINKED = "Validated together with linked LEC section"
STATUS_NA = "N/A - no meeting pattern"
STATUS_INSUFFICIENT = "N/A - insufficient data"
STATUS_IGNORED = "Ignored - Acad Org has no lab component"
SEE_ABOVE = "See above"
