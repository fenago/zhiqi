"""Flask UI for the CMR pipeline POC.

Upload an initial CMR (.xlsb), run Step 0 -> Step 1 -> Step 1b (duration +
integrity) -> Step 2 (adjunct pool), view results, and download the processed
workbook and reports.

Run:  python -m webapp.app   (or  flask --app webapp.app run)
"""
from __future__ import annotations

import os
import uuid

from flask import (Flask, render_template, request, redirect, url_for,
                   send_from_directory, abort)
from werkzeug.utils import secure_filename

from cmr_pipeline import run as pipeline
from cmr_pipeline.step1b_duration import C_STATUS, C_CURRENT, C_EXPECTED, C_NOTES
from cmr_pipeline.integrity import C_INT_STATUS, C_INT_FLAGS

BASE = os.path.dirname(os.path.abspath(__file__))
RUNS_DIR = os.path.join(os.path.dirname(BASE), "runs")
os.makedirs(RUNS_DIR, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 80 * 1024 * 1024  # 80 MB uploads

RESULTS: dict[str, dict] = {}  # run_id -> view model (in-memory for the session)


def _course(r):
    pre = str(r.get("Course Prefix (Subject)") or "").strip()
    num = str(r.get("Course Number (Catalog Nbr)") or "").strip().split(".")[0]
    return f"{pre}{num}"


def _org(r):
    return str(r.get("Acad Org")).split(".")[0]


def _num(r, k):
    v = r.get(k)
    try:
        return str(int(float(v)))
    except (TypeError, ValueError):
        return "" if v is None else str(v)


def _view_model(result: dict) -> dict:
    kept = result["kept"]
    integ = result["integrity"]
    int_rows = integ["errors"] + integ["warnings"]
    integrity_view = [{
        "course": _course(r), "descr": r.get("Class Descr"), "comp": r.get("Comp"),
        "org": _org(r), "severity": r.get(C_INT_STATUS), "flags": r.get(C_INT_FLAGS),
    } for r in int_rows]

    adjunct_view = [{
        "course": _course(r), "descr": r.get("Class Descr"), "comp": r.get("Comp"),
        "org": _org(r), "section": r.get("Class Section"), "days": r.get("Concat Days"),
        "mode": str(r.get("Instr Mode") or ""), "cap": _num(r, "Cap Enrl"),
        "class_nbr": _num(r, "Class Nbr"),
    } for r in result["adjunct_rows"]]

    d = result["duration"]
    return {
        "filter": result["filter"],
        "duration": {
            "status_counts": d["status_counts"],
            "mismatch_count": d["mismatch_count"],
            "within_tolerance_count": d.get("within_tolerance_count", 0),
            "tolerance": d["tolerance"],
        },
        "integrity_counts": integ["status_counts"],
        "integrity_flags": integ["code_counts"],
        "integrity_view": integrity_view,
        "adjunct": result["adjunct"],
        "adjunct_view": adjunct_view,
        "main_workbook": result["main_workbook"],
        "llm": result["llm"],
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/process", methods=["POST"])
def process():
    f = request.files.get("cmr")
    if not f or not f.filename:
        return redirect(url_for("index"))
    if not f.filename.lower().endswith((".xlsb", ".xlsx")):
        return render_template("index.html", error="Please upload a .xlsb (or .xlsx) CMR file.")

    run_id = uuid.uuid4().hex[:12]
    run_dir = os.path.join(RUNS_DIR, run_id)
    os.makedirs(run_dir, exist_ok=True)
    src = os.path.join(run_dir, secure_filename(f.filename))
    f.save(src)

    want_llm = bool(os.environ.get("ANTHROPIC_API_KEY"))
    try:
        result = pipeline.process(src, run_dir, want_llm=want_llm)
    except Exception as e:  # surface processing errors to the UI
        return render_template("index.html",
                               error=f"Could not process file: {type(e).__name__}: {e}")

    vm = _view_model(result)
    vm["run_id"] = run_id
    vm["filename"] = f.filename
    RESULTS[run_id] = vm
    return redirect(url_for("results", run_id=run_id))


@app.route("/results/<run_id>")
def results(run_id):
    vm = RESULTS.get(run_id)
    if not vm:
        abort(404)
    return render_template("results.html", **vm)


@app.route("/download/<run_id>/<path:filename>")
def download(run_id, filename):
    run_dir = os.path.join(RUNS_DIR, run_id)
    if not os.path.isdir(run_dir):
        abort(404)
    return send_from_directory(run_dir, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
