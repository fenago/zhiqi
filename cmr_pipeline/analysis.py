"""LLM analysis layer (best-of-both-worlds).

The deterministic engine produces exact results; this layer turns those results
into human-readable analysis. It is *pluggable*: it always writes a structured
prompt + a deterministic fallback summary, and -- if an Anthropic API key and the
SDK are available -- it also calls Claude for a richer narrative.

Determinism stays in Python (the rules); the LLM only narrates/interprets.
"""
from __future__ import annotations

import json
import os

from . import config
from .step1b_duration import C_CURRENT, C_EXPECTED, C_STATUS, C_NOTES
from .integrity import C_INT_STATUS, C_INT_FLAGS

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")


def build_summary(filter_report: dict, dur_report: dict, int_report: dict = None) -> dict:
    """Compact, JSON-serializable summary of the deterministic results."""
    mismatches = [
        {
            "acad_org": str(m.get("Acad Org")).split(".")[0],
            "course": f"{m.get('Course Prefix (Subject)')}{m.get('Course Number (Catalog)')}".replace("None", ""),
            "class_nbr": str(m.get("Class Nbr")).split(".")[0],
            "descr": m.get("Class Descr"),
            "comp": m.get("Comp"),
            "instr_mode": m.get("Instr Mode"),
            "session": m.get("Session Code"),
            "days": m.get("Concat Days"),
            "current_min": m.get(C_CURRENT),
            "expected_min": m.get(C_EXPECTED),
            "note": m.get(C_NOTES),
        }
        for m in dur_report.get("mismatches", [])
    ]
    summary = {
        "filter": {k: v for k, v in filter_report.items()},
        "duration": {
            "total": dur_report["total"],
            "status_counts": dur_report["status_counts"],
            "mismatch_count": dur_report["mismatch_count"],
            "within_tolerance_count": dur_report.get("within_tolerance_count", 0),
            "tolerance": dur_report["tolerance"],
        },
        "mismatches": mismatches,
    }
    if int_report is not None:
        summary["integrity"] = {
            "status_counts": int_report["status_counts"],
            "code_counts": int_report["code_counts"],
            "flagged": [
                {
                    "course": _course(r),
                    "descr": r.get("Class Descr"),
                    "comp": r.get("Comp"),
                    "integrity_status": r.get(C_INT_STATUS),
                    "flags": r.get(C_INT_FLAGS),
                }
                for r in (int_report["errors"] + int_report["warnings"])
            ],
        }
    return summary


def _course(r):
    pre = str(r.get("Course Prefix (Subject)") or "").strip()
    num = str(r.get("Course Number (Catalog Nbr)") or "").strip().split(".")[0]
    return f"{pre}{num}"


def deterministic_narrative(summary: dict) -> str:
    """A readable Markdown summary produced without any LLM (always available)."""
    f, d = summary["filter"], summary["duration"]
    lines = ["# CMR Duration Validation - Analysis (deterministic summary)", ""]
    lines.append(f"**Sections in selection pool:** {f.get('kept')}")
    lines.append("")
    lines.append("**Validation status breakdown:**")
    for status, n in sorted(d["status_counts"].items(), key=lambda x: -x[1]):
        lines.append(f"- {status}: {n}")
    lines.append("")
    lines.append(f"**Tolerance applied:** {d['tolerance']}")
    lines.append(f"**Within-tolerance (passed but flagged):** {d.get('within_tolerance_count', 0)}")
    lines.append("")
    lines.append(f"**Mismatches to fix:** {d['mismatch_count']}")
    if summary["mismatches"]:
        lines.append("")
        lines.append("| Course | Descr | Comp | Mode | Current | Expected | Fix |")
        lines.append("|---|---|---|---|---|---|---|")
        for m in summary["mismatches"][:50]:
            lines.append(
                f"| {m['course']} | {m['descr']} | {m['comp']} | "
                f"{(m['instr_mode'] or '')[:2]} | {m['current_min']} | "
                f"{m['expected_min']} | {m['note']} |"
            )
    integ = summary.get("integrity")
    if integ:
        sc = integ["status_counts"]
        lines += ["", "## Integrity checks (A1-D1)", "",
                  f"- Error: {sc.get('Error', 0)} · Warning: {sc.get('Warning', 0)} · "
                  f"OK: {sc.get('OK', 0)}",
                  f"- Flags: {integ['code_counts']}"]
        if integ["flagged"]:
            lines += ["", "| Course | Descr | Comp | Severity | Flags |",
                      "|---|---|---|---|---|"]
            for r in integ["flagged"][:50]:
                lines.append(
                    f"| {r['course']} | {r['descr']} | {r['comp']} | "
                    f"{r['integrity_status']} | {r['flags']} |"
                )
    return "\n".join(lines)


def build_prompt(summary: dict) -> str:
    return (
        "You are a scheduling-data analyst for Miami Dade College. The following "
        "JSON is the deterministic output of a duration-validation pass over a "
        "filtered course schedule (Architecture/Engineering/Technology, Kendall). "
        "The numeric validation is already done and correct -- do NOT recompute it. "
        "Write a concise analysis for the department chair: (1) overall data-quality "
        "health, (2) patterns in the mismatches (by department, instruction mode, "
        "session length, or LEC/LAB linking), (3) the most likely root causes, and "
        "(4) a prioritized list of what to fix first before sending the schedule to "
        "faculty for course selection.\n\n"
        f"```json\n{json.dumps(summary, indent=2, default=str)}\n```"
    )


def _build_client():
    """Construct an Anthropic client from available credentials, or None.

    Supports ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN (Bearer), honors
    ANTHROPIC_BASE_URL, and trusts the agent-proxy CA bundle if present so calls
    succeed through the egress proxy.
    """
    try:
        import anthropic
    except ImportError:
        return None, "anthropic SDK not installed (pip install anthropic)"

    # Trust the proxy CA so httpx/TLS verification passes through the egress proxy.
    ca = "/root/.ccr/ca-bundle.crt"
    if os.path.exists(ca):
        os.environ.setdefault("SSL_CERT_FILE", ca)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN")
    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    kwargs = {}
    if base_url:
        kwargs["base_url"] = base_url

    if api_key:
        return anthropic.Anthropic(api_key=api_key, **kwargs), None
    if auth_token:
        return anthropic.Anthropic(auth_token=auth_token, **kwargs), None
    return None, ("no credential found - set ANTHROPIC_API_KEY (or ANTHROPIC_AUTH_TOKEN) "
                  "to enable live Claude analysis")


def llm_analysis(summary: dict):
    """Call Claude. Returns (text, error). text is None on failure."""
    client, err = _build_client()
    if client is None:
        return None, err
    try:
        msg = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": build_prompt(summary)}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        return text, None
    except Exception as e:  # network/auth/policy errors -> graceful fallback
        return None, f"{type(e).__name__}: {str(e)[:200]}"


def run(summary: dict, want_llm: bool = True) -> dict:
    """Produce analysis artifacts. Returns dict of {filename: text}."""
    artifacts = {
        "analysis_prompt.txt": build_prompt(summary),
        "analysis_summary.md": deterministic_narrative(summary),
        "summary.json": json.dumps(summary, indent=2, default=str),
    }
    if want_llm:
        text, err = llm_analysis(summary)
        if text:
            artifacts["analysis_llm.md"] = (
                f"# CMR Duration & Integrity - Claude Analysis ({MODEL})\n\n" + text)
        else:
            artifacts["analysis_llm_SKIPPED.txt"] = (
                f"Live Claude analysis not run: {err}\n\n"
                "The exact prompt is in analysis_prompt.txt and the deterministic "
                "summary in analysis_summary.md. Set ANTHROPIC_API_KEY and re-run "
                "to generate analysis_llm.md.\n")
    return artifacts
