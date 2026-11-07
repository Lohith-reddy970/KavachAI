"""Regressions for empty installations, real inputs, and visible failures."""
import pytest
from fastapi.testclient import TestClient

from app import config
from app.agents import reasoning_agent
from app.database import db
from app.main import app
from app.models import providers
from app.services import knowledge, system_status
from scripts.remove_legacy_examples import cleanup


def test_fresh_install_has_no_content_or_fabricated_search_results(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "clean.db")
    with TestClient(app) as client:
        assert client.get("/api/documents").json() == []
        assert client.get("/api/agents/runs").json() == []
        assert client.get("/api/deliverables").json()["deliverables"] == []
        assert client.get("/api/knowledge").json()["total_chunks"] == 0
        assert client.post("/api/knowledge/search", json={"query": "anything"}).json()["results"] == []
        assert client.post("/api/demo/run").status_code == 404
        assert client.get("/api/demo/stream").status_code == 404
        assert set(client.get("/api/models").json()["providers"]) == {"ollama", "transformers"}


def test_upload_populates_search_and_survives_restart(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "persist.db")
    with TestClient(app) as client:
        assert client.get("/api/knowledge").json()["total_chunks"] == 0
        uploaded = client.post("/api/documents/upload", files={"file": ("operations.txt", b"A turbine maintenance delay requires repair.")}).json()
        matches = client.post("/api/knowledge/search", json={"query": "turbine maintenance"}).json()["results"]
        assert matches and all(item["source"] == uploaded["filename"] for item in matches)
    monkeypatch.setattr(knowledge, "_KB", None)
    with TestClient(app) as client:
        assert client.get("/api/documents").json()[0]["id"] == uploaded["id"]
        assert client.get("/api/knowledge").json()["total_chunks"] > 0


def test_provider_failure_never_returns_canned_output(monkeypatch):
    class Offline:
        name = "ollama"

        def generate(self, *args, **kwargs):
            raise ConnectionError("runtime unavailable")

    monkeypatch.setattr(providers, "get_provider", lambda: Offline())
    with pytest.raises(providers.InferenceUnavailable):
        providers.generate("Summarize a document")


def test_summary_failure_is_503_and_task_and_run_are_errors(client, monkeypatch):
    def unavailable(*args, **kwargs):
        raise providers.InferenceUnavailable("Local inference unavailable")

    monkeypatch.setattr(reasoning_agent, "generate", unavailable)
    doc = client.post("/api/documents/upload", files={"file": ("availability.txt", b"A private report with content.")}).json()
    response = client.post(f"/api/documents/{doc['id']}/analyze", json={"title": "Availability check", "analysis_mode": "summary"})
    assert response.status_code == 503
    task = db.fetch_one("SELECT * FROM tasks WHERE title='Availability check' ORDER BY id DESC")
    assert task["status"] == "error"
    run = db.fetch_one("SELECT * FROM agent_runs WHERE task_id=?", (task["id"],))
    assert run["status"] == "error"
    assert not db.fetch_all("SELECT * FROM deliverables WHERE run_id=?", (run["id"],))


def test_risk_review_uses_source_when_advisory_model_is_unavailable(client, monkeypatch):
    def unavailable(*args, **kwargs):
        raise providers.InferenceUnavailable("Local inference unavailable")

    monkeypatch.setattr(reasoning_agent, "generate", unavailable)
    content = "A critical safety issue requires immediate repair."
    doc = client.post("/api/documents/upload", files={"file": ("source-review.txt", content.encode())}).json()
    response = client.post(f"/api/documents/{doc['id']}/analyze", json={"title": "Source review"})
    assert response.status_code == 200
    run = response.json()["run"]
    assert run["findings"]
    assert all(ev["excerpt"] in content for f in run["findings"] for ev in f["evidence"])
    assert any(step["message"] == "Advisory model analysis unavailable" for step in run["steps"])


def test_source_is_required_for_tasks_and_planner(client):
    assert client.post("/api/tasks", json={"title": "Review"}).status_code == 422
    assert client.post("/api/agent/run", json={"task": "Review"}).status_code == 422
    assert client.post("/api/agent/run", json={"task": "Review", "document_id": 999999}).status_code == 404


def test_task_api_uses_its_document_and_tracks_review_completion(client):
    doc = client.post("/api/documents/upload", files={"file": ("task-source.txt", b"A critical safety issue requires repair.")}).json()
    response = client.post("/api/tasks", json={"title": "Review selected file", "document_id": doc["id"]})
    assert response.status_code == 200
    result = response.json()
    assert result["task"]["status"] == "awaiting_review"
    for finding in result["run"]["findings"]:
        assert all(evidence["source"] == doc["filename"] for evidence in finding["evidence"])
        if finding["needs_review"]:
            assert client.post(f"/api/review/{finding['id']}/approve").status_code == 200
    task = client.get(f"/api/tasks/{result['task']['id']}").json()["task"]
    assert task["status"] == "completed"


def test_planner_with_no_findings_finishes_without_repeating_reason(client):
    doc = client.post("/api/documents/upload", files={"file": ("routine.txt", b"The meeting starts Thursday.")}).json()
    response = client.post("/api/agent/run", json={"task": "Review the note", "document_id": doc["id"]})
    assert response.status_code == 200
    run = response.json()
    assert run["findings"] == []
    assert run["planner"]["stop_reason"] == "finished"
    assert [step["action"] for step in run["planner"]["trace"]].count("reason") == 1
    assert {report["fmt"] for report in run["deliverables"]} >= {"txt", "md"}


def test_planner_image_summary_uses_vision_without_image_keyword(client):
    doc = client.post("/api/documents/upload", files={"file": ("visual.png", b"test-only image input")}).json()
    response = client.post("/api/agent/run", json={"task": "Summarize this document", "document_id": doc["id"], "analysis_mode": "summary"})
    assert response.status_code == 200
    run = response.json()
    assert run["planner"]["stop_reason"] == "finished"
    assert any(step["message"] == "Uploaded image analysis completed" for step in run["steps"])
    assert run["run"]["verification_score"] is None


def test_missing_gpu_has_null_metrics_and_no_pretend_sandbox(client, monkeypatch):
    monkeypatch.setattr(system_status, "_nvidia_gpu", lambda: None)
    status = client.get("/api/system/status").json()
    assert status["gpu"]["source"] == "unavailable"
    assert status["gpu"]["utilization_pct"] is None
    assert status["gpu"]["memory_used_pct"] is None
    assert status["sandbox"]["status"] == "disabled"


def test_legacy_cleanup_preserves_uploads_with_matching_names(tmp_path, monkeypatch):
    database = tmp_path / "migration.db"
    monkeypatch.setattr(db, "DB_PATH", database)
    db.init_db()
    for path in (tmp_path / "demo-data" / "Project_Status.txt", tmp_path / "data" / "uploads" / "Project_Status.txt"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Private source" if "uploads" in path.parts else "Legacy example")
        db.insert("documents", {"name": path.name, "filename": path.name, "path": str(path), "created_at": "2026-11-05"})
    run_id = db.insert("agent_runs", {"scenario": "document:Project_Status.txt", "started_at": "2026-11-05"})
    db.insert("evidence", {"run_id": run_id, "source": "Project_Status.txt", "created_at": "2026-11-05"})
    preview = cleanup(database, tmp_path)
    assert preview["documents"] == 1 and preview["runs"] == 0
    assert db.count("documents") == 2
    cleanup(database, tmp_path, apply=True)
    assert db.count("documents") == 1 and db.count("agent_runs") == 1
    assert (tmp_path / "data" / "uploads" / "Project_Status.txt").read_text() == "Private source"
