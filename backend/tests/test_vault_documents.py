"""Source previews, deletion boundaries, and analysis/deletion concurrency."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
import threading

import pytest
from fastapi.testclient import TestClient

from app import config
from app.database import db
from app.main import app
from app.services import document_analysis, document_store


@pytest.fixture
def vault(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "vault.db")
    monkeypatch.setattr(config, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(config, "GENERATED_DIR", tmp_path / "reports")
    with TestClient(app) as client:
        yield client


def upload(client, name="vault-note.txt", content=b"A critical safety issue requires immediate repair."):
    response = client.post("/api/documents/upload", files={"file": (name, content)})
    assert response.status_code == 200, response.text
    return response.json()


def input_bytes(ext):
    if ext == "pdf":
        import pymupdf
        with pymupdf.open() as pdf:
            pdf.new_page().insert_text((50, 50), "Local PDF preview")
            return pdf.tobytes()
    if ext in {"png", "jpg", "jpeg"}:
        from PIL import Image
        output = BytesIO()
        Image.new("RGB", (32, 20), "white").save(output, format="PNG" if ext == "png" else "JPEG")
        return output.getvalue()
    if ext == "docx":
        from docx import Document
        output = BytesIO()
        document = Document()
        document.add_paragraph("Local DOCX preview")
        document.add_table(rows=1, cols=1).cell(0, 0).text = "Value inside a table"
        document.save(output)
        return output.getvalue()
    return b"Local plain text <script>never execute this source</script>"


@pytest.mark.parametrize("ext,kind", [("pdf", "pdf"), ("png", "image"), ("jpg", "image"),
                                       ("jpeg", "image"), ("txt", "text"), ("csv", "text"),
                                       ("py", "text"), ("docx", "text")])
def test_every_upload_type_opens_locally_and_downloads_exact_original(vault, ext, kind):
    content = input_bytes(ext)
    document = upload(vault, f"source.{ext}", content)
    base = f"/api/documents/{document['id']}"
    preview = vault.get(base + "/preview")
    assert preview.status_code == 200
    assert preview.json()["kind"] == kind
    if ext == "docx":
        assert "Local DOCX preview" in preview.json()["text"]
        assert "Value inside a table" in preview.json()["text"]
    elif kind == "text":
        assert preview.json()["text"] == content.decode()
    opened = vault.get(base + "/content")
    assert opened.status_code == 200 and opened.content == content
    assert opened.headers["content-disposition"].startswith("inline;")
    assert opened.headers["x-content-type-options"] == "nosniff"
    assert opened.headers["cache-control"] == "no-store"
    assert opened.headers["content-type"].startswith(document_store.MEDIA_TYPES[ext])
    if ext == "pdf":
        ranged = vault.get(base + "/content", headers={"Range": "bytes=0-15"})
        assert ranged.status_code == 206 and ranged.content == content[:16]
    downloaded = vault.get(base + "/content?download=true")
    assert downloaded.content == content
    assert downloaded.headers["content-disposition"].startswith("attachment;")
    assert db.count("agent_runs") == 0 and db.count("analysis_jobs") == 0


def test_large_text_preview_is_bounded_but_original_is_complete(vault):
    content = b"A" * (document_store.PREVIEW_CHARS + 1234)
    document = upload(vault, content=content)
    base = f"/api/documents/{document['id']}"
    preview = vault.get(base + "/preview").json()
    assert preview["truncated"] and len(preview["text"]) == document_store.PREVIEW_CHARS
    assert vault.get(base + "/content?download=true").content == content


def test_delete_removes_source_and_search_results_but_retains_history(vault):
    document = upload(vault)
    other = upload(vault, "preserved.txt", b"Preserved turbine operating manual")
    run = vault.post(f"/api/documents/{document['id']}/analyze", json={"title": "Review local source"}).json()["run"]
    before = vault.get("/api/knowledge").json()
    assert before["total_chunks"] >= 2
    base = f"/api/documents/{document['id']}"
    result = vault.delete(base)
    assert result.status_code == 200 and result.json()["file_removed"]
    assert not Path(document["path"]).exists() and Path(other["path"]).exists()
    assert [item["id"] for item in vault.get("/api/documents").json()] == [other["id"]]
    matches = vault.post("/api/knowledge/search", json={"query": "critical safety repair"}).json()["results"]
    assert all(item["source"] != document["filename"] for item in matches)
    assert vault.get("/api/knowledge").json()["total_chunks"] == 1
    saved = vault.get(f"/api/agents/runs/{run['run']['id']}")
    assert saved.status_code == 200 and saved.json()["findings"] == run["findings"]
    for report in run["deliverables"]:
        assert vault.get(f"/api/deliverables/{report['id']}/download").status_code == 200
    assert db.fetch_one("SELECT * FROM audit_logs WHERE action='document.delete'")
    for suffix in ("", "/preview", "/content"):
        assert vault.get(base + suffix).status_code == 404
    assert vault.delete(base).status_code == 404
    assert vault.post("/api/analysis/jobs", json={"document_id": document["id"], "title": "Cannot reuse deleted source"}).status_code == 404


def test_outside_storage_path_is_neither_served_nor_deleted(vault, tmp_path):
    document = upload(vault)
    outside = tmp_path / "private.txt"
    outside.write_text("Must not be exposed or removed")
    db.execute("UPDATE documents SET path=? WHERE id=?", (str(outside), document["id"]))
    base = f"/api/documents/{document['id']}"
    assert vault.get(base + "/content").status_code == 409
    assert vault.get(base + "/preview").status_code == 409
    assert vault.delete(base).status_code == 409
    assert outside.read_text() == "Must not be exposed or removed"
    assert vault.get(base).status_code == 200


def test_missing_disk_file_can_be_removed_from_vault(vault):
    document = upload(vault)
    Path(document["path"]).unlink()
    base = f"/api/documents/{document['id']}"
    assert vault.get(base + "/content").status_code == 404
    assert vault.get(base + "/preview").status_code == 404
    response = vault.delete(base)
    assert response.status_code == 200 and not response.json()["file_removed"]


def test_failed_file_removal_keeps_document_record(vault, monkeypatch):
    document = upload(vault)
    original = Path.unlink

    def unavailable(path, *args, **kwargs):
        if path == Path(document["path"]):
            raise PermissionError("File is open in another program")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unavailable)
    assert vault.delete(f"/api/documents/{document['id']}").status_code == 409
    assert Path(document["path"]).is_file()
    assert vault.get(f"/api/documents/{document['id']}").status_code == 200


@pytest.mark.parametrize("status", ["queued", "running"])
def test_persisted_active_job_prevents_deletion(vault, status):
    document = upload(vault)
    db.insert("analysis_jobs", {"id": "active-job", "document_id": document["id"], "status": status,
                               "request_json": "{}", "stages_json": "[]", "created_at": "now", "updated_at": "now"})
    assert vault.delete(f"/api/documents/{document['id']}").status_code == 409
    assert Path(document["path"]).exists()
    db.execute("UPDATE analysis_jobs SET status='completed' WHERE id='active-job'")
    assert vault.delete(f"/api/documents/{document['id']}").status_code == 200


@pytest.mark.parametrize("workflow", ["pipeline", "planner"])
def test_sync_analysis_pins_source_even_before_run_is_created(vault, monkeypatch, workflow):
    document = upload(vault)
    entered, release = threading.Event(), threading.Event()
    original = document_analysis.extract_document

    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(10), "Test did not release extraction"
        return original(*args, **kwargs)

    monkeypatch.setattr(document_analysis, "extract_document", blocked)
    path, payload = (f"/api/documents/{document['id']}/analyze", {"title": "Concurrent review"}) if workflow == "pipeline" else (
        "/api/agent/run", {"document_id": document["id"], "task": "Review the selected source"})
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(vault.post, path, json=payload)
        try:
            assert entered.wait(3)
            assert vault.delete(f"/api/documents/{document['id']}").status_code == 409
            assert Path(document["path"]).is_file()
        finally:
            release.set()
        assert future.result(timeout=15).status_code == 200
    assert vault.delete(f"/api/documents/{document['id']}").status_code == 200
