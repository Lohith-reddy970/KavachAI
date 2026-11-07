"""Tests for uploaded-document analysis: findings must come from the file itself."""
from __future__ import annotations

from app.services import document_analysis
import pytest

REPORT = (
    "Compressor K-220 quarterly inspection.\n"
    "A hairline crack was observed on the discharge flange of K-220 and requires repair.\n"
    "Bearing vibration on K-220 is trending upward; recommend monitoring weekly.\n"
    "The lube oil cooler was cleaned and returned to service without remarks.\n"
)


def _upload(client, name: str, content: bytes) -> dict:
    res = client.post("/api/documents/upload", files={"file": (name, content)})
    assert res.status_code == 200, res.text
    return res.json()


def _analyze(client, doc_id: int, **options) -> dict:
    payload = {"title": "Review for defects", **options}
    res = client.post(f"/api/documents/{doc_id}/analyze", json=payload)
    assert res.status_code == 200, res.text
    return res.json()["run"]


def test_findings_are_extracted_from_the_uploaded_text(client):
    doc = _upload(client, "k220_report.txt", REPORT.encode())
    run = _analyze(client, doc["id"])

    titles = " ".join(f["title"] for f in run["findings"])
    assert "K-220" in titles and "P-101" not in titles  # nothing from the demo scenario
    assert run["findings"][0]["severity"] == "high"
    assert all(ev["source"] == doc["filename"] and ev["excerpt"] in REPORT.replace("\n", " ")
               for f in run["findings"] for ev in f["evidence"])
    assert run["run"]["verification_score"] == 100.0
    assert "vision_agent" in [s["agent"] for s in run["steps"] if s["status"] == "skipped"]
    # The high-severity finding is held for an engineer.
    assert run["run"]["status"] == "awaiting_review"
    assert run["findings"][0]["needs_review"] == 1


def test_document_without_risk_terms_yields_no_findings(client):
    doc = _upload(client, "notes.txt", b"The quarterly meeting was moved to Thursday afternoon.")
    run = _analyze(client, doc["id"])
    assert run["findings"] == []
    assert run["run"]["status"] == "completed"


def test_unreadable_upload_does_not_crash_the_run(client):
    doc = _upload(client, "broken.pdf", b"this is not a pdf")
    run = _analyze(client, doc["id"])
    assert run["findings"] == []
    assert any(s["status"] == "warning" for s in run["steps"])


def test_same_filename_uploads_do_not_overwrite(client):
    first = _upload(client, "dup.txt", b"first")
    second = _upload(client, "dup.txt", b"second")
    assert first["path"] != second["path"]
    assert open(first["path"], "rb").read() == b"first"


def test_analyze_unknown_document_is_404(client):
    assert client.post("/api/documents/999999/analyze", json={"title": "x"}).status_code == 404


def test_profile_catalog_is_available(client):
    catalog = client.get("/api/profiles").json()
    assert {profile["id"] for profile in catalog["profiles"]} == {
        "general", "industrial", "business", "education", "finance", "legal", "healthcare", "hr",
    }
    assert {mode["id"] for mode in catalog["analysis_modes"]} == {
        "risk_review", "summary", "extract_fields",
    }


def test_profiles_apply_different_risk_terms():
    text = "Corrosion was observed on the pipe and requires repair."
    general = document_analysis.find_findings(text, "report.txt", "general")
    industrial = document_analysis.find_findings(text, "report.txt", "industrial")
    assert general == []
    assert industrial and "corro" in industrial[0]["description"]


@pytest.mark.parametrize("profile,text,expected", [
    ("business", "The launch is blocked because the supplier has not shipped the required materials.", "high"),
    ("education", "The research report has uncited passages that need a source before submission.", "medium"),
    ("finance", "Invoice INV-2026-01 remains unpaid and the account needs reconciliation.", "medium"),
    ("legal", "The supplier agreement has expired and needs a renewal decision this week.", "medium"),
    ("healthcare", "The service record contains unsigned consent for the scheduled appointment.", "medium"),
    ("hr", "The staff file shows incomplete onboarding and a training gap for the new employee.", "medium"),
])
def test_nonindustrial_profiles_review_actual_uploaded_content(client, profile, text, expected):
    doc = _upload(client, f"{profile}_example.txt", text.encode())
    run = _analyze(client, doc["id"], profile=profile)
    assert run["findings"] and run["findings"][0]["severity"] == expected
    assert run["run"]["verification_score"] == 100.0
    assert all(ev["source"] == doc["filename"] and ev["excerpt"] in text
               for finding in run["findings"] for ev in finding["evidence"])


def test_everyday_field_extraction_preserves_values_and_citations(client):
    text = ("Invoice INV-2026-01\nInvoice date: 4 November 2026\n"
            "Total: INR 50,000\nOwner: Priya Shah\nContact: priya@example.org\n")
    doc = _upload(client, "invoice.txt", text.encode())
    run = _analyze(client, doc["id"], profile="finance", analysis_mode="extract_fields")
    titles = " | ".join(f["title"] for f in run["findings"])
    for value in ("INV-2026-01", "4 November 2026", "INR 50,000", "Priya Shah", "priya@example.org"):
        assert value in titles
    assert run["run"]["verification_score"] == 100.0
    for finding in run["findings"]:
        citation = finding["evidence"][0]
        location = citation["location"]
        assert text[location["char_start"]:location["char_end"]] == citation["excerpt"]


def test_invoice_fields_inside_a_word_table_are_not_lost(client):
    from io import BytesIO
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_paragraph("Supplier invoice INV-2026-02")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Total:"
    table.cell(0, 1).text = "INR 12,500"
    table.cell(1, 0).text = "Owner:"
    table.cell(1, 1).text = "Priya Shah"
    buffer = BytesIO()
    document.save(buffer)
    doc = _upload(client, "supplier_invoice.docx", buffer.getvalue())
    run = _analyze(client, doc["id"], profile="finance", analysis_mode="extract_fields")
    titles = " | ".join(f["title"] for f in run["findings"])
    assert "INR 12,500" in titles and "Priya Shah" in titles
    assert run["run"]["verification_score"] == 100.0


def test_summary_mode_records_summary_without_risk_findings(client):
    doc = _upload(client, "summary.txt", b"The project started in 2024. It has three open actions.")
    run = _analyze(client, doc["id"], analysis_mode="summary")
    assert run["findings"] == []
    assert run["run"]["verification_score"] is None
    summary_step = next(s for s in run["steps"] if s["message"] == "Document summary generated")
    assert "mode=summary" in summary_step["detail"]
    assert any(s["status"] == "skipped" for s in run["steps"])
    report = next(d for d in run["deliverables"] if d["fmt"] == "md")
    report_text = open(report["path"], encoding="utf-8").read()
    assert "Document Summary" in report_text
    assert "Not applicable: summary mode does not create findings to verify." in report_text


def test_extract_fields_mode_returns_source_cited_values(client):
    content = b"Inspection date: 2026-04-12. Equipment K-220 measured 6.8 mm at 14 bar."
    doc = _upload(client, "fields.txt", content)
    run = _analyze(client, doc["id"], analysis_mode="extract_fields")
    titles = " | ".join(f["title"] for f in run["findings"])
    assert "2026-04-12" in titles
    assert "K-220" in titles
    assert "6.8 mm" in titles
    assert all(f["evidence"][0]["excerpt"] in content.decode() for f in run["findings"])


def test_analyze_rejects_unknown_profile_and_mode(client):
    doc = _upload(client, "profile.txt", b"A routine note with no findings.")
    unknown_profile = client.post(
        f"/api/documents/{doc['id']}/analyze",
        json={"title": "Review", "profile": "unknown"},
    )
    unknown_mode = client.post(
        f"/api/documents/{doc['id']}/analyze",
        json={"title": "Review", "analysis_mode": "compare"},
    )
    assert unknown_profile.status_code == 422
    assert unknown_mode.status_code == 422


def test_image_risk_review_inspects_image_even_without_ocr_text(client):
    doc = _upload(client, "diagram.png", b"\x89PNG\r\n\x1a\nnot-really-an-image")
    run = _analyze(client, doc["id"])
    assert run["findings"] == []
    assert run["run"]["status"] == "completed"
    statuses = {s["agent"]: s["status"] for s in run["steps"]}
    assert statuses["vision_agent"] == "completed"
    assert statuses["knowledge_agent"] == "skipped"
    reasoning = next(s for s in run["steps"] if s["agent"] == "reasoning_agent")
    assert reasoning["status"] == "warning"
    assert "no OCR text" in reasoning["message"]
    assert run["vision"]["text"]
    assert run["vision"]["advisory"] is True


def test_image_summary_uses_vision_output(client):
    doc = _upload(client, "diagram.png", b"\x89PNG\r\n\x1a\nsample-image")
    run = _analyze(client, doc["id"], analysis_mode="summary")
    messages = [s["message"] for s in run["steps"]]
    assert "Uploaded image analysis completed" in messages
    assert "Visual summary captured" in messages
    assert run["findings"] == []
    assert run["run"]["verification_score"] is None


def test_verification_catches_an_excerpt_that_is_not_in_the_document():
    findings = document_analysis.find_findings(REPORT, "r.txt")
    findings[0]["evidence"][0]["excerpt"] = "A sentence the document never contained."
    result = document_analysis.verify_findings(findings, REPORT)
    assert result["score"] < 100
    assert findings[0]["title"] in result["unsupported"]
