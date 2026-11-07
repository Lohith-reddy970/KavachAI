"""Batch recovery, scoped local chat, and exact source highlight boundaries."""
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app import config
from app.database import db
from app.main import app
from app.models.providers import GenerationResult, InferenceUnavailable
from app.rag.pipeline import KnowledgeBase
from app.services import analysis, analysis_jobs, batch_jobs, document_analysis, document_chat, knowledge


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "features.db")
    monkeypatch.setattr(config, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(config, "GENERATED_DIR", tmp_path / "reports")
    with TestClient(app) as client:
        yield client


def upload(client, name="note.txt", content=b"A critical safety issue requires immediate repair."):
    response = client.post("/api/documents/upload", files={"file": (name, content)})
    assert response.status_code == 200, response.text
    return response.json()


def wait_batch(client, batch_id):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        batch = client.get(f"/api/analysis/batches/{batch_id}").json()
        if batch["status"] in {"completed", "completed_with_errors"}:
            return batch
        time.sleep(0.05)
    raise AssertionError("Batch did not finish")


def test_batch_partial_failure_idempotency_and_saved_individual_runs(workspace, monkeypatch):
    docs = [upload(workspace, f"source-{n}.txt") for n in range(6)]
    original = analysis.analyze_document

    def process(document_id, *args, **kwargs):
        if document_id == docs[2]["id"]:
            raise RuntimeError("This source could not be analyzed")
        return original(document_id, *args, **kwargs)

    monkeypatch.setattr(analysis, "analyze_document", process)
    payload = {"document_ids": [d["id"] for d in docs], "request_id": "repeatable-batch-01"}
    first = workspace.post("/api/analysis/batches", json=payload)
    assert first.status_code == 202
    assert workspace.post("/api/analysis/batches", json=payload).json()["id"] == first.json()["id"]
    final = wait_batch(workspace, first.json()["id"])
    assert final["status"] == "completed_with_errors"
    assert final["counts"]["completed"] == 5 and final["counts"]["error"] == 1
    assert len({item["job_id"] for item in final["items"]}) == 6
    failed = next(item for item in final["items"] if item["document_id"] == docs[2]["id"])
    assert "could not be analyzed" in failed["error"]
    for item in final["items"]:
        if item["status"] == "completed":
            assert workspace.get(f"/api/agents/runs/{item['run_id']}").status_code == 200
            assert workspace.get(f"/api/analysis/jobs/{item['job_id']}").json()["result"]
    assert len(workspace.get("/api/analysis/batches").json()) == 1
    assert db.count("analysis_jobs") == 6
    assert workspace.post("/api/analysis/batches", json={**payload, "analysis_mode": "summary"}).status_code == 409


def test_batch_waits_for_capacity_and_pins_pending_sources(workspace, monkeypatch):
    semaphore = threading.BoundedSemaphore(1)
    semaphore.acquire()
    monkeypatch.setattr(analysis_jobs, "_capacity", semaphore)
    documents = [upload(workspace, f"queued-{n}.txt") for n in range(2)]
    response = workspace.post("/api/analysis/batches", json={"document_ids": [d["id"] for d in documents]})
    assert response.status_code == 202
    try:
        time.sleep(0.6)
        pending = workspace.get(f"/api/analysis/batches/{response.json()['id']}").json()
        assert pending["counts"]["pending"] == 2 and db.count("analysis_jobs") == 0
        assert workspace.delete(f"/api/documents/{documents[0]['id']}").status_code == 409
    finally:
        semaphore.release()
    assert wait_batch(workspace, response.json()["id"])["counts"]["completed"] == 2


def test_durable_pending_batch_resumes_and_interrupted_item_is_reported(workspace):
    batch_jobs.shutdown()
    doc = upload(workspace)
    request = {"document_ids": [doc["id"]], "profile": "general", "analysis_mode": "risk_review", "description": "Review the source"}
    db.insert("analysis_batches", {"id": "resume-batch", "status": "queued", "request_json": db.dumps(request), "created_at": "now", "updated_at": "now"})
    db.insert("analysis_batch_items", {"batch_id": "resume-batch", "document_id": doc["id"], "filename": doc["filename"], "job_id": "resume-job"})
    batch_jobs.start()
    assert wait_batch(workspace, "resume-batch")["counts"]["completed"] == 1
    batch_jobs.shutdown()
    db.execute("UPDATE analysis_batches SET status='running' WHERE id='resume-batch'")
    db.execute("UPDATE analysis_jobs SET status='running' WHERE id='resume-job'")
    analysis_jobs.recover_interrupted()
    batch_jobs.start()
    recovered = wait_batch(workspace, "resume-batch")
    assert recovered["status"] == "completed_with_errors"
    assert "restarted" in recovered["items"][0]["error"]


def test_batch_rejects_invalid_sources_without_partial_admission(workspace):
    doc = upload(workspace)
    assert workspace.post("/api/analysis/batches", json={"document_ids": [doc["id"], 99999]}).status_code == 404
    for payload in [{"document_ids": []}, {"document_ids": [doc["id"]] * 2}, {"document_ids": [doc["id"]], "profile": "unknown"}, {"document_ids": [doc["id"]], "description": " "}]:
        assert workspace.post("/api/analysis/batches", json=payload).status_code == 422
    assert db.count("analysis_batches") == 0 and db.count("analysis_jobs") == 0


def test_saved_evidence_opens_exact_unicode_source_and_rejects_changed_or_deleted_file(workspace):
    content = "🔎 Source note\nA critical safety issue requires immediate repair.\nEnd."
    doc = upload(workspace, content=content.encode())
    run = workspace.post(f"/api/documents/{doc['id']}/analyze", json={"title": "Review"}).json()["run"]
    evidence = run["findings"][0]["evidence"][0]
    preview = workspace.get(f"/api/evidence/{evidence['id']}/preview")
    assert preview.status_code == 200, preview.text
    result = preview.json()
    assert result["text"][result["highlight_start"]:result["highlight_end"]] == evidence["excerpt"]
    assert result["document_id"] == doc["id"] and not result["has_image"]
    Path(doc["path"]).write_text("The source content has changed", encoding="utf-8")
    assert workspace.get(f"/api/evidence/{evidence['id']}/preview").status_code == 409
    workspace.delete(f"/api/documents/{doc['id']}")
    assert workspace.get(f"/api/evidence/{evidence['id']}/preview").status_code == 404


def test_pdf_visual_highlight_and_rendered_page(workspace):
    import pymupdf
    pdf = pymupdf.open()
    pdf.new_page().insert_text((50, 70), "A critical safety issue requires immediate repair.")
    doc = upload(workspace, "highlight.pdf", pdf.tobytes())
    pdf.close()
    run = workspace.post(f"/api/documents/{doc['id']}/analyze", json={"title": "Review"}).json()["run"]
    evidence = run["findings"][0]["evidence"][0]
    preview = workspace.get(f"/api/evidence/{evidence['id']}/preview").json()
    assert preview["has_image"] and preview["boxes"]
    assert all(0 <= box["x"] < 1 and 0 < box["width"] <= 1 for box in preview["boxes"])
    response = workspace.get(f"/api/documents/{doc['id']}/pages/1/image")
    assert response.content.startswith(b"\x89PNG") and response.headers["cache-control"] == "no-store"
    assert workspace.get(f"/api/documents/{doc['id']}/pages/99/image").status_code == 404


def test_ocr_word_boxes_are_reused_for_highlighting(workspace, monkeypatch):
    from PIL import Image
    from app.services.document_analysis import ExtractedDocument, OCRWord, PageText
    output = BytesIO(); Image.new("RGB", (100, 50), "white").save(output, format="PNG")
    doc = upload(workspace, "ocr.png", output.getvalue())
    box = {"x": .1, "y": .2, "width": .4, "height": .2}
    monkeypatch.setattr(document_analysis, "extract_document", lambda path: ExtractedDocument([PageText(1, "Invoice 123", "tesseract", words=[OCRWord("Invoice", 0, 7, box, 95)])]))
    response = workspace.post(f"/api/documents/{doc['id']}/passage", json={"excerpt": "Invoice", "page": 1})
    assert response.status_code == 200 and response.json()["boxes"] == [box]


def test_retrieval_preserves_raw_whitespace_spans_and_filters_before_ranking():
    text = "\n\t" + "  \n".join(f"word{n}" for n in range(250))
    kb = KnowledgeBase(); kb.add(text, "selected.txt", document_id=1)
    kb.add("secret deadline 2030", "other.txt", document_id=2)
    matches = kb.search("word50", top_k=10, document_ids={1})
    assert matches and all(m["document_id"] == 1 for m in matches)
    for match in matches:
        assert text[match["char_start"]:match["char_end"]] == match["text"]


def test_chat_is_scoped_and_each_returned_citation_can_be_highlighted(workspace, monkeypatch):
    chosen = upload(workspace, "selected.txt", b"The renewal deadline is 2030-01-12.")
    upload(workspace, "excluded.txt", b"Private unrelated secret 999999 renewal deadline.")
    prompts = []
    read_paths = []
    original_extract = knowledge.extract_document
    def extract_selected(path):
        read_paths.append(path)
        return original_extract(path)
    monkeypatch.setattr(knowledge, "extract_document", extract_selected)

    def model(prompt, **kwargs):
        prompts.append(prompt)
        return GenerationResult("The renewal deadline is 2030-01-12. [1]", "test-local", "ollama", 10, 1)

    monkeypatch.setattr(document_chat, "generate", model)
    response = workspace.post("/api/chat", json={"document_ids": [chosen["id"]], "question": "What is the renewal deadline?"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "cited" and result["model"] == "test-local"
    assert "999999" not in prompts[0] and "excluded.txt" not in prompts[0]
    assert read_paths == [chosen["path"]]
    for citation in result["citations"]:
        assert citation["document_id"] == chosen["id"]
        assert workspace.post(f"/api/documents/{chosen['id']}/passage", json=citation).status_code == 200
    follow = workspace.post("/api/chat", json={"document_ids": [chosen["id"]], "question": "What date?", "history": [{"role": "user", "content": "What is the renewal deadline?"}]})
    assert follow.status_code == 200 and "conversation" in prompts[-1]


@pytest.mark.parametrize("answer", ["An uncited answer.", "A made-up source. [99]", "Unsupported paragraph.\n\nA cited paragraph. [1]", "INSUFFICIENT_EVIDENCE"])
def test_chat_does_not_present_uncited_or_invalid_source_answers(workspace, monkeypatch, answer):
    doc = upload(workspace, content=b"The renewal deadline is 2030-01-12.")
    monkeypatch.setattr(document_chat, "generate", lambda *a, **k: GenerationResult(answer, "local", "ollama", 10, 1))
    response = workspace.post("/api/chat", json={"document_ids": [doc["id"]], "question": "renewal deadline"}).json()
    assert response["status"] == "insufficient_evidence" and not response["citations"]
    assert response["answer"] == document_chat.NO_EVIDENCE


def test_chat_no_readable_evidence_model_failure_and_deleted_sources(workspace, monkeypatch):
    blank = upload(workspace, "blank.txt", b"")
    def unavailable(*args, **kwargs):
        raise InferenceUnavailable("Local model is offline")
    monkeypatch.setattr(document_chat, "generate", unavailable)
    assert workspace.post("/api/chat", json={"document_ids": [blank["id"]], "question": "deadline"}).json()["status"] == "insufficient_evidence"
    doc = upload(workspace, "deadline.txt", b"The deadline is 2030-01-12.")
    assert workspace.post("/api/chat", json={"document_ids": [doc["id"]], "question": "deadline"}).status_code == 503
    assert workspace.post("/api/chat", json={"document_ids": [doc["id"]], "question": " "}).status_code == 422
    workspace.delete(f"/api/documents/{doc['id']}")
    assert workspace.post("/api/chat", json={"document_ids": [doc["id"]], "question": "deadline"}).status_code == 404


def test_chat_limits_concurrent_generation_and_pins_its_source(workspace, monkeypatch):
    doc = upload(workspace, content=b"The renewal deadline is 2030-01-12.")
    entered, release = threading.Event(), threading.Event()
    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        return GenerationResult("The deadline is 2030-01-12. [1]", "local", "ollama", 10, 1)
    monkeypatch.setattr(document_chat, "generate", blocked)
    payload = {"document_ids": [doc["id"]], "question": "renewal deadline"}
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(workspace.post, "/api/chat", json=payload)
        try:
            assert entered.wait(3)
            assert workspace.post("/api/chat", json=payload).status_code == 409
            assert workspace.delete(f"/api/documents/{doc['id']}").status_code == 409
        finally:
            release.set()
        assert future.result(10).status_code == 200
    assert workspace.delete(f"/api/documents/{doc['id']}").status_code == 200


@pytest.mark.parametrize("ext", ["txt", "csv", "py", "docx"])
def test_text_source_formats_highlight_without_html_execution(workspace, ext):
    text = "Header\nAmount USD 200.00\n<script>never execute</script>"
    content = text.encode()
    if ext == "docx":
        from docx import Document
        output = BytesIO(); document = Document(); document.add_paragraph(text); document.save(output)
        content = output.getvalue()
    doc = upload(workspace, f"source.{ext}", content)
    response = workspace.post(f"/api/documents/{doc['id']}/passage", json={"excerpt": "Amount USD 200.00"})
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["text"][preview["highlight_start"]:preview["highlight_end"]] == "Amount USD 200.00"
    assert preview["page_label"] == "Text section 1" and not preview["has_image"]


def test_deleted_evidence_is_not_relinked_to_a_replacement_filename(workspace):
    doc = upload(workspace)
    run = workspace.post(f"/api/documents/{doc['id']}/analyze", json={"title": "Review"}).json()["run"]
    evidence_id = run["findings"][0]["evidence"][0]["id"]
    assert workspace.delete(f"/api/documents/{doc['id']}").status_code == 200
    replacement = upload(workspace)
    assert replacement["filename"] == doc["filename"] and replacement["id"] != doc["id"]
    assert workspace.get(f"/api/evidence/{evidence_id}/preview").status_code == 404


def test_knowledge_search_exposes_real_source_spans_for_highlighting(workspace):
    doc = upload(workspace, content=b"The renewal deadline is 2030-01-12.")
    matches = workspace.post("/api/knowledge/search", json={"query": "renewal deadline"}).json()["results"]
    assert matches and matches[0]["document_id"] == doc["id"]
    hit = matches[0]
    preview = workspace.post(f"/api/documents/{doc['id']}/passage", json={"page": hit["page"], "excerpt": hit["text"], "char_start": hit["char_start"], "char_end": hit["char_end"]})
    assert preview.status_code == 200
