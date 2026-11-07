"""Local OCR extraction and page-aware source citation regressions."""
from __future__ import annotations

import sqlite3

from PIL import Image

from app.database import db
from app.services import document_analysis
from app.services.document_analysis import (
    ExtractedDocument,
    OCRWord,
    PageText,
)


def _word(text: str, confidence: float = 89.0) -> OCRWord:
    return OCRWord(
        text=text,
        start=0,
        end=len(text),
        bbox={
            "x": 0.1,
            "y": 0.2,
            "width": 0.7,
            "height": 0.08,
            "coordinate_space": "normalized",
        },
        confidence=confidence,
    )


def test_tesseract_adapter_preserves_word_spans_and_normalized_boxes(monkeypatch):
    monkeypatch.setattr(document_analysis, "ocr_status", lambda: {
        "status": "available",
        "engine": "Tesseract",
        "reason": "",
        "pdf_renderer_available": True,
    })
    monkeypatch.setattr(document_analysis, "_tesseract_data", lambda _image: {
        "text": ["Severe", "corrosion", "found", "P-101", "repair"],
        "conf": [91, 88, 90, 85, 89],
        "block_num": [1, 1, 1, 1, 1],
        "par_num": [1, 1, 1, 1, 1],
        "line_num": [1, 1, 1, 2, 2],
        "left": [10, 60, 140, 10, 80],
        "top": [20, 20, 20, 50, 50],
        "width": [45, 65, 35, 42, 50],
        "height": [12, 12, 12, 12, 12],
    })

    page, note = document_analysis._ocr_image(Image.new("RGB", (200, 100)), 4)

    assert note == ""
    assert page is not None
    assert page.number == 4
    assert page.text == "Severe corrosion found\nP-101 repair"
    assert page.method == "tesseract"
    assert page.ocr_confidence == 88.6
    assert page.words[0].start == 0
    assert page.words[0].bbox["x"] == 0.05
    assert page.words[0].bbox["coordinate_space"] == "normalized"


def test_sparse_pdf_page_uses_local_ocr_and_citation_stays_on_that_page(monkeypatch, tmp_path):
    scan = tmp_path / "inspection.pdf"
    scan.write_bytes(b"fake PDF bytes; PDF reader is mocked")
    ocr_text = "Severe corrosion was observed on pump K-220 and repair is required."

    monkeypatch.setattr(document_analysis, "_read_pdf_pages", lambda _path: [
        "Routine checks were completed and the results were recorded.",
        "",
    ])
    monkeypatch.setattr(document_analysis, "ocr_status", lambda: {
        "status": "available",
        "engine": "Tesseract",
        "reason": "",
        "pdf_renderer_available": True,
    })
    monkeypatch.setattr(document_analysis, "_render_pdf_page", lambda _path, _index:
                        Image.new("RGB", (100, 100)))
    monkeypatch.setattr(document_analysis, "_ocr_image", lambda _image, page_number: (
        PageText(
            page_number,
            ocr_text,
            "tesseract",
            89.0,
            [_word(ocr_text)],
            True,
        ),
        "",
    ))

    extracted = document_analysis.extract_document(str(scan))
    findings = document_analysis.find_findings(
        extracted.text,
        "inspection.pdf",
        "industrial",
        source_pages=extracted.pages,
    )

    assert extracted.metadata() == {
        "status": "ready",
        "method": "mixed",
        "page_count": 2,
        "ocr_pages": 1,
        "ocr_attempted_pages": 1,
        "note": "",
    }
    assert findings
    citation = findings[0]["evidence"][0]
    assert citation["page"] == 2
    assert citation["excerpt"] == ocr_text
    assert citation["extraction_method"] == "tesseract"
    assert citation["ocr_confidence"] == 89.0
    assert citation["location"]["char_start"] == 0
    assert citation["location"]["bbox"]["coordinate_space"] == "normalized"

    verified = document_analysis.verify_findings(
        findings, extracted.text, source_pages=extracted.pages)
    assert verified["score"] == 100.0
    assert verified["page_citation_accuracy"] == 100.0
    assert verified["location_accuracy"] == 100.0

    findings[0]["evidence"][0]["page"] = 1
    wrong_page = document_analysis.verify_findings(
        findings, extracted.text, source_pages=extracted.pages)
    assert wrong_page["score"] == 0.0
    assert findings[0]["title"] in wrong_page["unsupported"]


def test_ocr_page_citation_is_persisted_and_low_confidence_is_held_for_review(
    client, monkeypatch
):
    text = "Severe corrosion was observed on pump K-220 and repair is required."
    pages = [
        PageText(1, "Routine checks were completed and the results were recorded.", "pdf-text"),
        PageText(2, text, "tesseract", 62.0, [_word(text, confidence=62.0)], True),
    ]
    extracted = ExtractedDocument(pages)
    monkeypatch.setattr(document_analysis, "extract_document", lambda _path: extracted)
    upload = client.post(
        "/api/documents/upload",
        files={"file": ("scanned-inspection.pdf", b"fake PDF bytes")},
    )
    assert upload.status_code == 200, upload.text

    response = client.post(
        f"/api/documents/{upload.json()['id']}/analyze",
        json={"title": "Inspect scanned report", "profile": "industrial"},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    evidence = result["run"]["findings"][0]["evidence"][0]

    assert result["document"]["pages"] == 2
    assert result["document"]["extraction_method"] == "mixed"
    assert result["document"]["ocr_pages"] == 1
    assert evidence["page"] == 2
    assert evidence["location"]["char_start"] == 0
    assert evidence["extraction_method"] == "tesseract"
    assert evidence["ocr_confidence"] == 62.0
    assert result["run"]["findings"][0]["needs_review"] == 1
    assert "low OCR confidence" in " ".join(
        result["run"]["findings"][0].get("review_reasons", []))
    assert result["run"]["run"]["status"] == "awaiting_review"

    markdown = next(item for item in result["run"]["deliverables"] if item["fmt"] == "md")
    report = open(markdown["path"], encoding="utf-8").read()
    assert "p.2; chars 0-" in report
    assert "62.0%" in report


def test_ocr_unavailable_is_reported_without_breaking_text_extraction(monkeypatch, tmp_path):
    image = tmp_path / "scan.png"
    Image.new("RGB", (80, 80), "white").save(image)
    monkeypatch.setattr(document_analysis, "ocr_status", lambda: {
        "status": "unavailable",
        "engine": "Tesseract",
        "reason": "Tesseract executable was not found",
        "pdf_renderer_available": False,
    })

    extracted = document_analysis.extract_document(str(image))

    assert extracted.status == "needs_ocr"
    assert extracted.page_count == 1
    assert "OCR is not enabled" in extracted.note
    assert extracted.text == ""


def test_system_status_reports_real_local_ocr_capability(client):
    response = client.get("/api/system/status")

    assert response.status_code == 200
    assert response.json()["ocr"]["engine"] == "Tesseract"
    assert response.json()["ocr"]["status"] in {"available", "unavailable"}
    assert response.json()["ocr"]["status"] != "online"


def test_existing_database_gets_additive_citation_metadata_migration(tmp_path, monkeypatch):
    database_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(database_path)
    connection.executescript("""
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            filename TEXT NOT NULL, path TEXT NOT NULL, doc_type TEXT,
            size_bytes INTEGER DEFAULT 0, pages INTEGER DEFAULT 0,
            status TEXT DEFAULT 'ready', summary TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, title TEXT NOT NULL,
            description TEXT, severity TEXT DEFAULT 'medium', confidence REAL DEFAULT 0,
            equipment_id TEXT, needs_review INTEGER DEFAULT 0,
            review_status TEXT DEFAULT 'pending', created_at TEXT NOT NULL
        );
        CREATE TABLE evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT, finding_id INTEGER, run_id INTEGER,
            source TEXT NOT NULL, page INTEGER, excerpt TEXT, confidence REAL DEFAULT 0,
            created_at TEXT NOT NULL
        );
    """)
    connection.close()
    monkeypatch.setattr(db, "DB_PATH", database_path)

    db.init_db()

    document_columns = {row["name"] for row in db.fetch_all("PRAGMA table_info(documents)")}
    finding_columns = {row["name"] for row in db.fetch_all("PRAGMA table_info(findings)")}
    evidence_columns = {row["name"] for row in db.fetch_all("PRAGMA table_info(evidence)")}
    assert {"extraction_method", "ocr_pages"} <= document_columns
    assert "review_reasons_json" in finding_columns
    assert {"location_json", "extraction_method", "ocr_confidence"} <= evidence_columns
