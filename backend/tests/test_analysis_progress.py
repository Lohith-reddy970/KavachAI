"""Real-operation progress, asynchronous delivery, recovery, and inline results."""
from __future__ import annotations

import threading
import time

from app.agents import reasoning_agent
from app.database import db
from app.models.providers import GenerationResult, InferenceUnavailable
from app.services import analysis_jobs, document_analysis


def upload(client, content=b"A critical issue requires immediate repair."):
    response = client.post("/api/documents/upload", files={"file": ("progress.txt", content)})
    assert response.status_code == 200
    return response.json()["id"]


def start(client, document_id, **options):
    response = client.post("/api/analysis/jobs", json={"document_id": document_id, "title": "Analyze this source", **options})
    assert response.status_code == 202, response.text
    return response.json()["id"]


def finish(client, job_id):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        response = client.get(f"/api/analysis/jobs/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["status"] in {"completed", "error"}:
            return job
        time.sleep(0.03)
    raise AssertionError("Job did not finish")


def test_progress_is_visible_before_model_returns_and_full_summary_is_saved(client, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    full_summary = "Complete model output. " * 100

    def blocked_model(*args, **kwargs):
        entered.set()
        assert release.wait(10), "Test did not release inference"
        return GenerationResult(full_summary, "local-test-model", "ollama", 100, 5)

    monkeypatch.setattr(reasoning_agent, "generate", blocked_model)
    document_id = upload(client, b"The project contains a source-backed summary.")
    try:
        job_id = start(client, document_id, analysis_mode="summary")
        assert entered.wait(3)
        active = client.get(f"/api/analysis/jobs/{job_id}").json()
        states = {stage["id"]: stage for stage in active["stages"]}
        assert active["status"] == "running" and active["result"] is None
        assert states["extraction"]["status"] == "completed"
        assert states["reasoning"]["status"] == "running"
        assert states["reasoning"]["metadata"]["model"]
        assert states["verification"]["status"] == "pending"
        assert states["deliverables"]["status"] == "pending"
    finally:
        release.set()
    final = finish(client, job_id)
    assert final["status"] == "completed"
    result = final["result"]["run"]
    assert result["analysis"]["text"] == full_summary
    assert result["extraction"]["page_count"] == 1
    assert result["run"]["analysis_mode"] == "summary"
    assert result["deliverables"]
    saved = client.get(f"/api/agents/runs/{result['run']['id']}").json()
    assert saved["analysis"]["text"] == full_summary
    assert client.get(f"/api/analysis/jobs/{job_id}").json()["result"]["run"]["analysis"]["text"] == full_summary


def test_failed_generation_keeps_completed_progress_and_skips_future_stages(client, monkeypatch):
    def unavailable(*args, **kwargs):
        raise InferenceUnavailable("Local model is unavailable")
    monkeypatch.setattr(reasoning_agent, "generate", unavailable)
    job_id = start(client, upload(client), analysis_mode="summary")
    job = finish(client, job_id)
    stages = {stage["id"]: stage for stage in job["stages"]}
    assert job["status"] == "error" and "unavailable" in job["error"]
    assert stages["extraction"]["status"] == "completed"
    assert stages["reasoning"]["status"] == "error"
    assert stages["verification"]["status"] == "not_run"
    assert stages["deliverables"]["status"] == "not_run"
    assert job["result"] is None
    assert db.fetch_one("SELECT status FROM agent_runs WHERE id=?", (job["run_id"],))["status"] == "error"


def test_background_review_results_remain_current_after_human_decisions(client):
    job_id = start(client, upload(client))
    job = finish(client, job_id)
    run = job["result"]["run"]
    assert run["findings"] and run["run"]["status"] == "awaiting_review"
    for finding in run["findings"]:
        if finding["needs_review"]:
            client.post(f"/api/review/{finding['id']}/approve")
    refreshed = client.get(f"/api/analysis/jobs/{job_id}").json()
    assert refreshed["result"]["run"]["run"]["status"] == "completed"
    assert all(f["review_status"] == "approved" for f in refreshed["result"]["run"]["findings"] if f["needs_review"])


def test_planner_uses_same_progress_and_inline_result_contract(client):
    job_id = start(client, upload(client), workflow="planner")
    job = finish(client, job_id)
    assert job["status"] == "completed", job["error"]
    assert job["result"]["run"]["planner"]["stop_reason"] == "finished"
    assert job["result"]["run"]["extraction"]["page_count"] == 1
    assert any(stage["id"] == "reasoning" and stage["status"] == "completed" for stage in job["stages"])


def test_full_queue_and_invalid_requests_do_not_start_new_work(client, monkeypatch):
    document_id = upload(client)
    monkeypatch.setattr(analysis_jobs, "_capacity", threading.BoundedSemaphore(0))
    assert client.post("/api/analysis/jobs", json={"document_id": document_id, "title": "Review"}).status_code == 429
    assert client.post("/api/analysis/jobs", json={"document_id": 999999, "title": "Review"}).status_code == 404
    assert client.post("/api/analysis/jobs", json={"document_id": document_id, "title": "Review", "profile": "unknown"}).status_code == 422
    assert client.get("/api/analysis/jobs/not-a-job").status_code == 404


def test_pdf_page_progress_describes_actual_extraction_operations(monkeypatch, tmp_path):
    path = tmp_path / "scanned.pdf"
    path.write_bytes(b"PDF test fixture; reader isolated below")
    monkeypatch.setattr(document_analysis, "_read_pdf_pages", lambda path: ["A full embedded page of readable text.", ""])
    monkeypatch.setattr(document_analysis, "ocr_status", lambda: {"status": "available", "pdf_renderer_available": True})
    class RenderedPage:
        def close(self): pass
    monkeypatch.setattr(document_analysis, "_render_pdf_page", lambda *args: RenderedPage())
    monkeypatch.setattr(document_analysis, "_ocr_image", lambda image, number: (document_analysis.PageText(number, "Scanned text", "tesseract", ocr_attempted=True), ""))
    events = []
    extracted = document_analysis.extract_document(str(path), on_progress=events.append)
    assert extracted.page_count == 2 and extracted.ocr_pages == 1
    assert [event["metadata"]["page"] for event in events] == [1, 2]
    assert events[0]["detail"] == "Reading embedded text"
    assert events[1]["detail"] == "Running local OCR"


def test_restart_recovery_retains_trace_and_marks_unfinished_jobs(client):
    stages = analysis_jobs._stages()
    stages[0].update(status="completed")
    stages[1].update(status="running", message="Reading pages")
    job_id = "interrupted-progress-test"
    db.insert("analysis_jobs", {"id": job_id, "document_id": upload(client), "status": "running",
              "request_json": "{}", "stages_json": db.dumps(stages),
              "created_at": analysis_jobs._now(), "updated_at": analysis_jobs._now()})
    analysis_jobs.recover_interrupted()
    job = client.get(f"/api/analysis/jobs/{job_id}").json()
    assert job["status"] == "error" and "restarted" in job["error"]
    assert job["stages"][0]["status"] == "completed"
    assert job["stages"][1]["status"] == "error"
    assert job["stages"][2]["status"] == "not_run"
