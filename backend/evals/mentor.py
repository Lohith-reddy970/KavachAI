"""Run five real acceptance scenarios against an isolated local API process.

From the repository root: python backend/evals/mentor.py
No production database is used and no inference doubles are installed.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import hashlib
import html
import json
import os
import re
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_PLANNER_ACTIONS = {"search_knowledge", "inspect_document", "analyze_pid", "reason", "verify", "human_review", "finish"}

CASES = (
    {
        "id": "S1", "title": "PDF review, citations, and human approval", "kind": "success",
        "objective": "Demonstrate PDF extraction, real local reasoning, source verification, review gating, and report download.",
        "input": "inputs/S1_inspection.pdf",
        "steps": ["Upload the controlled PDF.", "Run Industrial risk review and observe the saved job.",
                  "Check the high-severity source match and exact citation.",
                  "Approve the held test finding, then download the text report."],
        "expected": "Analysis finishes with a source-cited high-severity match, initially held for review. The reviewer decision completes the run and a report downloads.",
        "explain": "The successful behavior includes the human-review hold. A critical finding must not be silently cleared. Citation verification checks the excerpt against the supplied PDF; it does not prove the inspection claim is true.",
    },
    {
        "id": "S2", "title": "PNG inspection, OCR, and literal fields", "kind": "success",
        "objective": "Demonstrate real image inspection even in Extract fields mode, local OCR, and source-backed values.",
        "input": "inputs/S2_invoice.png",
        "steps": ["Upload the controlled PNG.", "Select Finance and Extract fields.",
                  "Wait for Inspect images to finish with the local vision model.",
                  "Check the date/amount fields, OCR page count, and separate visual observations."],
        "expected": "Image inspection completes, OCR reads the page, and the known date and amount appear as literal fields with citations. Visual observations are shown separately.",
        "explain": "This checks the PNG regression: field extraction must not skip vision. The field assertions compare known input values with actual output. A nonempty model description proves the path ran, not that every visual statement is accurate.",
    },
    {
        "id": "S3", "title": "Bounded planner execution", "kind": "success",
        "objective": "Demonstrate the real local planner selecting allowlisted tools and finishing within its step budget.",
        "input": "inputs/S3_project_record.txt",
        "steps": ["Upload the controlled text record.", "Run the bounded planner in Extract fields mode.",
                  "Inspect its actual action trace and stop reason.", "Check source-backed values and generated reports."],
        "expected": "Planner stops with finished within 10 steps, uses permitted actions, extracts the known date/amount, and saves reports.",
        "explain": "This is the agentic path rather than the fixed pipeline. The trace shows which allowed action was selected at each step. Awaiting human review is an acceptable completed-analysis outcome.",
    },
    {
        "id": "F1", "title": "Unsupported file rejected", "kind": "expected_failure",
        "objective": "Demonstrate upload-policy enforcement without executing an unsafe file.",
        "input": "inputs/F1_disallowed.exe",
        "steps": ["Record the document count.", "Attempt to upload a harmless test byte string with an .exe filename.",
                  "Record the real error response and verify the document count is unchanged."],
        "expected": "HTTP 400 states that the file type is not allowed. No document record is created.",
        "explain": "The upload operation is expected to fail. The test passes only if the application rejects it correctly. The .exe fixture is plain test text and is never executed.",
    },
    {
        "id": "F2", "title": "Missing source document rejected", "kind": "expected_failure",
        "objective": "Demonstrate that analysis cannot invent a result for a nonexistent document.",
        "input": "inputs/F2_missing_document_request.json",
        "steps": ["Record the run count.", "Submit an analysis job using nonexistent document ID 2147483647.",
                  "Record the error response and verify that no run was created."],
        "expected": "HTTP 404 states Document not found. No analysis run is created.",
        "explain": "The analysis request is expected to fail because its source does not exist. Correct rejection is a passing negative test; a server error or fabricated result would fail the test.",
    },
)


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


@dataclass
class CaseResult:
    id: str
    title: str
    kind: str
    objective: str
    input: str
    steps: list[str]
    expected: str
    explain: str
    started_at: str = field(default_factory=utcnow)
    duration_ms: int = 0
    checks: list[dict] = field(default_factory=list)
    observed: dict = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)
    error: str | None = None

    def check(self, name, passed, actual=None):
        self.checks.append({"name": name, "passed": bool(passed), "actual": actual})

    @property
    def passed(self):
        return bool(self.checks) and all(check["passed"] for check in self.checks) and self.error is None

    def export(self):
        return {**asdict(self), "verdict": "PASS" if self.passed else "FAIL",
                "scenario_outcome": ("successful" if self.kind == "success" else "expected rejection")
                if self.passed else "unexpected result"}


class Api:
    def __init__(self, base: str, output: Path):
        self.base, self.output = base, output
        self.counter = 0
        self.case: CaseResult | None = None

    def call(self, method, path, payload=None, upload: Path | None = None, record=True):
        headers, data = {}, None
        request_evidence = payload
        if upload:
            content = upload.read_bytes()
            boundary = "kavach-acceptance-" + uuid.uuid4().hex
            data = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{upload.name}"\r\n'
                    'Content-Type: application/octet-stream\r\n\r\n').encode() + content + f"\r\n--{boundary}--\r\n".encode()
            headers["Content-Type"] = "multipart/form-data; boundary=" + boundary
            request_evidence = {"filename": upload.name, "bytes": len(content),
                                "sha256": hashlib.sha256(content).hexdigest()}
        elif payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        started = time.monotonic()
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            response = urllib.request.urlopen(request, timeout=20)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            code, raw = response.code, response.read()
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            body = raw.decode("utf-8", errors="replace")
        if record and self.case:
            self.counter += 1
            relative = f"evidence/{self.case.id}/{self.counter:03d}_{method.lower()}.json"
            write_json(self.output / relative, {"at": utcnow(), "method": method, "path": path,
                       "request": request_evidence, "http_status": code,
                       "elapsed_ms": round((time.monotonic() - started) * 1000), "response": body})
            self.case.evidence.append(relative)
        return code, body


def make_inputs(directory: Path):
    """Controlled test documents, never seed data for the user's application."""
    from PIL import Image, ImageDraw, ImageFont
    import pymupdf

    directory.mkdir(parents=True, exist_ok=True)
    lines = ["CONTROLLED ACCEPTANCE TEST INPUT", "This is test material, not a real inspection.",
             "Inspection record: T-401", "A critical crack was observed on equipment T-401 and requires repair.",
             "Inspection date: 2026-11-05", "An engineer must review this observation before action."]
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=595, height=842)
        for i, line in enumerate(lines):
            page.insert_text((45, 55 + i * 28), line, fontsize=12, fontname="helv")
        pdf.save(directory / "S1_inspection.pdf")

    fonts = [Path("C:/Windows/Fonts/arial.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]
    font_path = next((p for p in fonts if p.is_file()), None)
    font = ImageFont.truetype(str(font_path), 40) if font_path else ImageFont.load_default(size=40)
    image = Image.new("RGB", (1600, 700), "white")
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(["CONTROLLED ACCEPTANCE TEST INPUT", "TEST INVOICE - NOT A REAL PAYMENT",
                              "Invoice: INV-2026-005", "Date: 2026-11-05", "Total: INR 2500",
                              "Owner: Test Coordinator", "Contact: quality@example.org"]):
        draw.text((55, 45 + i * 85), line, fill="black", font=font)
    image.save(directory / "S2_invoice.png")
    (directory / "S3_project_record.txt").write_text(
        "CONTROLLED ACCEPTANCE TEST INPUT\nTest project record, not a real purchase.\n"
        "Reference: PRJ-2026-103\nDate: 2026-11-06\nBudget: INR 4800\n"
        "Owner: Test Coordinator\nContact: planner@example.org\n", encoding="utf-8")
    (directory / "F1_disallowed.exe").write_bytes(b"Harmless plain text for a disallowed-extension upload test. This is not executable software.")
    write_json(directory / "F2_missing_document_request.json", {
        "document_id": 2147483647, "title": "Analyze a missing source", "analysis_mode": "extract_fields"})


def uploaded(api: Api, source: Path):
    code, document = api.call("POST", "/api/documents/upload", upload=source)
    api.case.check("Upload succeeds", code == 200 and isinstance(document, dict) and "id" in document, code)
    if code != 200 or "id" not in document:
        raise RuntimeError(f"Upload did not succeed: {code}")
    api.case.observed["document_id"] = document["id"]
    return document


def analyze(api: Api, document: dict, timeout: float, **options):
    payload = {"document_id": document["id"], "title": "Acceptance test " + api.case.id,
               "description": "Analyze the selected controlled test input using only its content.", **options}
    code, job = api.call("POST", "/api/analysis/jobs", payload)
    api.case.check("Job accepted", code == 202 and "id" in job, code)
    if code != 202 or "id" not in job:
        raise RuntimeError("Analysis job was not accepted")
    api.case.observed["job_id"] = job["id"]
    deadline, previous = time.monotonic() + timeout, None
    while time.monotonic() < deadline:
        code, snapshot = api.call("GET", f"/api/analysis/jobs/{job['id']}")
        if code != 200:
            raise RuntimeError(f"Progress request failed: {code}")
        active = next((stage for stage in snapshot["stages"] if stage["status"] == "running"), None)
        state = (snapshot["status"], active["id"] if active else "")
        if state != previous:
            print(f"  {api.case.id}: {state[0]} / {state[1]}", flush=True)
            previous = state
        if snapshot["status"] in {"completed", "error"}:
            api.case.observed.update(job_status=snapshot["status"], run_id=snapshot["run_id"],
                                     stage_statuses={stage["id"]: stage["status"] for stage in snapshot["stages"]})
            api.case.check("Analysis finishes", snapshot["status"] == "completed", snapshot.get("error") or snapshot["status"])
            if not snapshot["result"]:
                raise RuntimeError(snapshot.get("error") or "Analysis returned no result")
            run = snapshot["result"]["run"]
            api.case.observed.update(run_status=run["run"]["status"], fields_or_matches=len(run["findings"]),
                                     verification_score=run["run"]["verification_score"],
                                     evidence_backed=run["run"]["evidence_backed"],
                                     report_formats=[item["fmt"] for item in run["deliverables"]])
            return run
        time.sleep(1)
    raise TimeoutError("Timed out waiting for the saved analysis job")


def successful_pdf(api, directory, timeout):
    from pypdf import PdfReader
    document = uploaded(api, directory / "inputs/S1_inspection.pdf")
    run = analyze(api, document, timeout, profile="industrial", analysis_mode="risk_review", workflow="pipeline")
    model = run.get("analysis") or {}
    api.case.observed["reasoning_model"] = model.get("model")
    api.case.check("Real local reasoning output is recorded", model.get("provider") == "ollama" and bool(model.get("text")), model.get("model"))
    api.case.check("PDF text extracted", run["extraction"]["page_count"] == 1 and run["extraction"]["method"] == "pdf-text", run["extraction"])
    critical = [f for f in run["findings"] if f["severity"] == "high" and "crack" in f["title"].lower()]
    api.case.check("Critical source match found", bool(critical), [f["title"] for f in run["findings"]])
    source_text = " ".join((PdfReader(directory / "inputs/S1_inspection.pdf").pages[0].extract_text() or "").split())
    citations = [ev for finding in run["findings"] for ev in finding["evidence"]]
    api.case.check("Citations independently match the supplied PDF", run["run"]["verification_score"] == 100
                   and bool(citations) and all(ev["source"] == document["filename"] and ev["page"] == 1
                   and bool(ev["excerpt"].strip()) and " ".join(ev["excerpt"].split()) in source_text for ev in citations), run["run"]["evidence_backed"])
    held = [f for f in run["findings"] if f["needs_review"]]
    api.case.check("High-risk result is held for review", run["run"]["status"] == "awaiting_review" and bool(held), run["run"]["status"])
    for finding in held:
        code, _ = api.call("POST", f"/api/review/{finding['id']}/approve", {"reviewer": "acceptance-test-reviewer", "note": "Approval of controlled test input only."})
        api.case.check(f"Review decision stored for finding {finding['id']}", code == 200, code)
    code, final = api.call("GET", f"/api/agents/runs/{run['run']['id']}")
    api.case.observed["run_status_after_review"] = final["run"]["status"]
    api.case.check("All required decisions complete the run", code == 200 and final["run"]["status"] == "completed", final["run"]["status"])
    text_report = next(item for item in run["deliverables"] if item["fmt"] == "txt")
    code, text = api.call("GET", f"/api/deliverables/{text_report['id']}/download")
    api.case.check("Actual report downloads", code == 200 and "T-401" in text, code)


def successful_image(api, directory, timeout):
    document = uploaded(api, directory / "inputs/S2_invoice.png")
    run = analyze(api, document, timeout, profile="finance", analysis_mode="extract_fields", workflow="pipeline")
    vision = run.get("vision") or {}
    api.case.observed.update(vision_model=vision.get("model"), vision_output=vision.get("text"), ocr_pages=run["extraction"]["ocr_pages"])
    api.case.check("Image inspection ran", api.case.observed["stage_statuses"]["vision"] == "completed", api.case.observed["stage_statuses"]["vision"])
    api.case.check("Real vision output is saved separately", vision.get("provider") == "ollama" and bool(vision.get("text")), vision.get("model"))
    api.case.check("Local OCR processed the page", run["extraction"]["ocr_pages"] == 1, run["extraction"])
    titles = [finding["title"] for finding in run["findings"]]
    api.case.observed["extracted_fields"] = titles
    api.case.check("Known date is extracted", any("2026-11-05" in title for title in titles), titles)
    api.case.check("Known amount is extracted", any(re.search(r"\bINR\s+2500\b", title) for title in titles), titles)
    api.case.check("Literal field citations verify", run["run"]["verification_score"] == 100, run["run"]["evidence_backed"])


def successful_planner(api, directory, timeout):
    document = uploaded(api, directory / "inputs/S3_project_record.txt")
    run = analyze(api, document, timeout, profile="business", analysis_mode="extract_fields", workflow="planner", max_steps=10)
    planner = run["planner"]
    api.case.observed["planner"] = planner
    api.case.check("Planner finishes normally", planner["stop_reason"] == "finished", planner["stop_reason"])
    api.case.check("Step budget respected", planner["steps_used"] == len(planner["trace"]) <= 10, planner["steps_used"])
    actions = [step["action"] for step in planner["trace"]]
    api.case.check("Only specified permitted actions used", set(actions) <= EXPECTED_PLANNER_ACTIONS, actions)
    titles = [finding["title"] for finding in run["findings"]]
    api.case.observed["extracted_fields"] = titles
    api.case.check("Planner returns known literal values", any("2026-11-06" in title for title in titles)
                   and any(re.search(r"\bINR\s+4800\b", title) for title in titles), titles)
    api.case.check("Planner saves reports and verifies citations", bool(run["deliverables"]) and run["run"]["verification_score"] == 100, run["run"]["evidence_backed"])


def rejected_upload(api, directory, timeout):
    _, before = api.call("GET", "/api/documents")
    code, response = api.call("POST", "/api/documents/upload", upload=directory / "inputs/F1_disallowed.exe")
    _, after = api.call("GET", "/api/documents")
    api.case.observed.update(http_status=code, error_response=response, documents_before=len(before), documents_after=len(after))
    api.case.check("Disallowed extension is rejected with HTTP 400", code == 400, code)
    api.case.check("Clear policy error is returned", isinstance(response, dict) and "not allowed" in response.get("detail", "").lower(), response)
    api.case.check("Rejected upload creates no document", len(before) == len(after), len(after))


def rejected_missing_source(api, directory, timeout):
    _, before = api.call("GET", "/api/agents/runs")
    payload = json.loads((directory / "inputs/F2_missing_document_request.json").read_text())
    code, response = api.call("POST", "/api/analysis/jobs", payload)
    _, after = api.call("GET", "/api/agents/runs")
    api.case.observed.update(http_status=code, error_response=response, runs_before=len(before), runs_after=len(after))
    api.case.check("Missing source is rejected with HTTP 404", code == 404, code)
    api.case.check("Clear missing-document error is returned", isinstance(response, dict) and response.get("detail") == "Document not found", response)
    api.case.check("Rejected request creates no run", len(before) == len(after), len(after))


def summary(results):
    return {"total": len(results), "successful_scenarios": sum(r["kind"] == "success" and r["verdict"] == "PASS" for r in results),
            "expected_failure_scenarios": sum(r["kind"] == "expected_failure" and r["verdict"] == "PASS" for r in results),
            "checks_passed": sum(r["verdict"] == "PASS" for r in results),
            "checks_failed": sum(r["verdict"] == "FAIL" for r in results)}


def write_reports(directory, report):
    write_json(directory / "results.json", report)
    with (directory / "results.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["Case", "Scenario", "Planned category", "Observed outcome", "Test verdict", "Duration ms", "HTTP status", "Run ID"])
        for result in report["results"]:
            writer.writerow([result["id"], result["title"], result["kind"], result["scenario_outcome"], result["verdict"], result["duration_ms"], result["observed"].get("http_status", ""), result["observed"].get("run_id", "")])
    lines = ["# Five acceptance test results", "", f"Executed: {report['finished_at']}", "",
             "Three valid workflow cases and two expected failure cases. A correct rejection is a passing negative test, not an application defect.", "",
             "| Case | Scenario | Actual outcome | Test verdict | Duration |", "|---|---|---|---|---|"]
    for r in report["results"]:
        lines.append(f"| {r['id']} | {r['title']} | {r['scenario_outcome']} | {r['verdict']} | {r['duration_ms'] / 1000:.2f}s |")
    lines += ["", "## Interpretation", "", "These are controlled acceptance checks on an isolated database with real local model calls. They do not estimate general model accuracy or prove production readiness.", ""]
    for r in report["results"]:
        lines += [f"## {r['id']} - {r['title']}", "", f"**Input:** [{r['input']}]({r['input']})", "", f"**Expected:** {r['expected']}", "",
                  f"**Observed:** {json.dumps(r['observed'], ensure_ascii=False)}", "", f"**Explain to the mentor:** {r['explain']}", "", "Checks:", ""]
        lines += [f"- {'PASS' if check['passed'] else 'FAIL'}: {check['name']}" for check in r["checks"]]
        if r["error"]:
            lines += ["", f"Unexpected error: {r['error']}"]
        lines += ["", "Raw evidence:", ""] + [f"- [{path}]({path})" for path in r["evidence"]] + [""]
    (directory / "report.md").write_text("\n".join(lines), encoding="utf-8")
    cards = []
    for r in report["results"]:
        esc = html.escape
        checks = "".join(f"<li class='{ 'pass' if c['passed'] else 'fail' }'>{'PASS' if c['passed'] else 'FAIL'}: {esc(c['name'])}</li>" for c in r["checks"])
        evidence = "".join(f"<li><a href='{esc(path, quote=True)}'>{esc(Path(path).name)}</a></li>" for path in r["evidence"])
        steps = "".join(f"<li>{esc(step)}</li>" for step in r["steps"])
        cards.append(f"""<article id='{r['id']}'><header><div><small>{esc(r['id'])} / {'Successful workflow' if r['kind'] == 'success' else 'Expected failure case'}</small><h2>{esc(r['title'])}</h2></div><strong class='{ 'pass' if r['verdict'] == 'PASS' else 'fail' }'>{r['verdict']}</strong></header>
<p>{esc(r['objective'])}</p><p><b>Actual scenario outcome:</b> {esc(r['scenario_outcome'])} / {r['duration_ms'] / 1000:.2f}s</p>
<p><a href='{esc(r['input'], quote=True)}'>Open test input</a></p><details><summary>How to demonstrate</summary><ol>{steps}</ol></details>
<h3>Expected result</h3><p>{esc(r['expected'])}</p><h3>Observed result</h3><pre>{esc(json.dumps(r['observed'], indent=2, ensure_ascii=False))}</pre>
<h3>Assertions</h3><ul>{checks}</ul><h3>Explanation for your mentor</h3><p>{esc(r['explain'])}</p>
{('<p class="fail">' + esc(r['error']) + '</p>') if r['error'] else ''}<details><summary>Raw API evidence ({len(r['evidence'])} responses)</summary><ul>{evidence}</ul></details></article>""")
    stats = report["summary"]
    rows = "".join(f"<tr><td><a href='#{r['id']}'>{r['id']}</a></td><td>{html.escape(r['title'])}</td><td>{r['scenario_outcome']}{' / HTTP ' + str(r['observed']['http_status']) if 'http_status' in r['observed'] else ''}</td><td class='{ 'pass' if r['verdict'] == 'PASS' else 'fail' }'>{r['verdict']}</td></tr>" for r in report["results"])
    document = f"""<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>KAVACH AI - Five acceptance tests</title>
<style>body{{font:16px/1.6 Arial,sans-serif;background:#f2f5f8;color:#142333;margin:0}}main{{max-width:1100px;margin:auto;padding:32px}}h1{{font-size:34px;line-height:1.2}}h2{{font-size:23px;margin:5px 0}}h3{{font-size:17px;margin-bottom:5px}}a{{color:#1659a0}}article,.intro{{background:white;border:1px solid #dce3ea;border-radius:12px;padding:26px;margin:22px 0}}header{{display:flex;justify-content:space-between;gap:20px}}small{{color:#526679}}.pass{{color:#137447}}.fail{{color:#a72525}}.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}.stats p{{background:#eaf0f6;border-radius:8px;padding:18px}}.stats b{{display:block;font-size:32px}}table{{border-collapse:collapse;width:100%}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #dce3ea}}pre{{background:#f3f6f9;padding:16px;border-radius:8px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}}summary{{cursor:pointer;font-weight:bold}}@media(max-width:650px){{main{{padding:12px}}.stats{{grid-template-columns:1fr}}header{{display:block}}td,th{{padding:5px;font-size:12px}}}}@media print{{body{{background:white}}main{{padding:0}}article{{break-before:page;border:0}}pre{{font-size:10px}}details{{display:block}}}}</style>
<main><h1>KAVACH AI: five acceptance test results</h1><p>Executed {html.escape(report['finished_at'])}. Real API responses and local model execution; isolated test storage.</p>
<div class='stats'><p><b>{stats['successful_scenarios']}/3</b>Successful workflow scenarios</p><p><b>{stats['expected_failure_scenarios']}/2</b>Expected failure scenarios</p><p><b>{stats['checks_passed']}/{stats['total']}</b>Passing test verdicts</p></div>
<section class='intro'><h2>How to explain the two failures</h2><p>F1 and F2 intentionally submit invalid input. Their application operations should fail with clear HTTP errors. The test verdict is PASS when that rejection is correct. An unexpected server error or acceptance would produce FAIL. This report never changes results to force a 3/2 split.</p><p><a href='results.json'>Full JSON</a> / <a href='results.csv'>Five-row CSV</a> / <a href='report.md'>Markdown report</a> / <a href='backend.log'>API server log</a></p><table><thead><tr><th>Case</th><th>Scenario</th><th>Actual outcome</th><th>Test verdict</th></tr></thead><tbody>{rows}</tbody></table></section>
{''.join(cards)}<section class='intro'><h2>Scope and limits</h2><p>Controlled inputs demonstrate selected functional paths. Citation scores measure literal source support, and visual descriptions remain advisory. Five cases do not establish a general accuracy percentage or certify production security. The existing application on port 8000 and its documents were not used by this isolated test process.</p><pre>{html.escape(json.dumps(report['environment'], indent=2, ensure_ascii=False))}</pre></section></main></html>"""
    (directory / "report.html").write_text(document, encoding="utf-8")


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New, empty result directory (default: mentor-testing/results/<timestamp>)")
    parser.add_argument("--timeout", type=float, default=300, help="Maximum seconds per analysis job")
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    output = (args.output or ROOT / "mentor-testing" / "results" / (datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6])).resolve()
    output.mkdir(parents=True, exist_ok=False)
    try:
        make_inputs(output / "inputs")
    except Exception as exc:
        write_json(output / "setup_error.json", {"at": utcnow(), "status": "not_run",
                   "reason": f"{type(exc).__name__}: {exc}", "executed_cases": 0})
        print(f"Test inputs could not be prepared: {exc}. See {output / 'setup_error.json'}", file=sys.stderr)
        return 2
    runtime = output / "runtime"
    runtime.mkdir()
    port = free_port()
    env = {**os.environ, "KAVACH_DB": str(runtime / "kavach.db"), "KAVACH_DATA": str(runtime),
           "KAVACH_UPLOADS": str(runtime / "uploads"), "KAVACH_GENERATED": str(runtime / "generated"),
           "KAVACH_MODE": "airgapped", "KAVACH_INFERENCE_PROVIDER": "ollama",
           "KAVACH_EMBEDDING_BACKEND": "hash", "KAVACH_SANDBOX_ENABLED": "false"}
    api = Api(f"http://127.0.0.1:{port}", output)
    log = (output / "backend.log").open("wb")
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
                               cwd=ROOT / "backend", env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    results = []
    report = {"started_at": utcnow(), "environment": {"python": sys.version.split()[0], "api_url": api.base,
              "isolated_storage": str(runtime), "inference": "real local Ollama", "test_doubles": False}, "results": results}
    try:
        deadline = time.monotonic() + 45
        while True:
            if process.poll() is not None:
                raise RuntimeError("Isolated API failed to start. Read backend.log.")
            try:
                code, health = api.call("GET", "/api/health", record=False)
                if code == 200:
                    break
            except (OSError, urllib.error.URLError):
                pass
            if time.monotonic() > deadline:
                raise TimeoutError("Isolated API startup timed out")
            time.sleep(0.2)
        _, models = api.call("GET", "/api/models", record=False)
        report["environment"].update(health=health, configured_models=models.get("models", []))
        functions = (successful_pdf, successful_image, successful_planner, rejected_upload, rejected_missing_source)
        for definition, function in zip(CASES, functions):
            case = CaseResult(**definition)
            api.case = case
            print(f"Running {case.id}: {case.title}", flush=True)
            started = time.monotonic()
            try:
                function(api, output, args.timeout)
            except Exception as exc:
                case.error = f"{type(exc).__name__}: {exc}"
            case.duration_ms = round((time.monotonic() - started) * 1000)
            results.append(case.export())
            print(f"  {case.id}: {results[-1]['scenario_outcome']} / test {results[-1]['verdict']}", flush=True)
            report.update(finished_at=utcnow(), summary=summary(results))
            write_reports(output, report)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        log.close()
    # Hash the actual test inputs so a reviewer can identify the executed files.
    report["input_sha256"] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (output / "inputs").iterdir()}
    report.update(finished_at=utcnow(), summary=summary(results))
    write_reports(output, report)
    print(json.dumps({"report": str(output / "report.html"), "summary": report["summary"]}), flush=True)
    return 0 if len(results) == 5 and report["summary"]["checks_failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
