"""CMR course-selection data pipeline (POC).

Deterministic, step-based processing of the Miami Dade College CMR workbook.
Each step is a pure function ``rows_in -> (rows_out, report)`` so steps can be
tested, re-run, and later wrapped in an API/UI.

Steps implemented:
  - Step 1   : filter to the 3 Kendall departments (Architecture/Engineering/Technology)
  - Step 1b  : duration validation (data-quality / cleaning gate)

The deterministic engine produces the data artifacts; an optional LLM analysis
layer (``analysis.py``) summarizes the results into human-readable insight.
"""
