"""Images must get real vision inspection in every mode and workflow."""
from __future__ import annotations

import time

import pytest

from app.agents import reasoning_agent, vision_agent
from app.models.providers import GenerationResult, InferenceUnavailable
from app.services import document_analysis
from app.services.document_analysis import ExtractedDocument, PageText

VISUAL = "The image is an architecture diagram with a router, model branches, and a tools section."


@pytest.fixture
def image_source(client, monkeypatch):
    source = client.post("/api/documents/upload", files={"file": ("architecture.png", b"image bytes isolated by the test provider")}).json()
    monkeypatch.setattr(document_analysis, "extract_document", lambda *args, **kwargs:
                        ExtractedDocument([PageText(1, "ARCHITECTURE: ROUTER AND VISION TOOLS", "tesseract", ocr_attempted=True)]))

    def vision(prompt, *, role, images, **kwargs):
        assert role == "vision" and images
        return GenerationResult(VISUAL, "llava:7b", "ollama", 20, 3)
    monkeypatch.setattr(vision_agent, "generate", vision)
    return source


@pytest.mark.parametrize("mode", ["risk_review", "summary", "extract_fields"])
@pytest.mark.parametrize("workflow", ["pipeline", "planner"])
def test_all_image_modes_and_workflows_perform_vision(client, image_source, mode, workflow):
    accepted = client.post("/api/analysis/jobs", json={
        "document_id": image_source["id"], "title": "Analyze this upload", "profile": "education",
        "analysis_mode": mode, "workflow": workflow,
    })
    assert accepted.status_code == 202
    job_id = accepted.json()["id"]
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        job = client.get(f"/api/analysis/jobs/{job_id}").json()
        if job["status"] in {"completed", "error"}:
            break
        time.sleep(0.03)
    assert job["status"] == "completed", job.get("error")
    result = job["result"]["run"]
    assert next(stage for stage in job["stages"] if stage["id"] == "vision")["status"] == "completed"
    assert result["vision"]["text"] == VISUAL
    assert result["vision"]["source"] == image_source["filename"]
    assert result["vision"]["advisory"] is True
    assert result["findings"] == []  # No values/issues are invented to fill the result count.
    assert result["run"]["verification_score"] is None
    persisted = client.get(f"/api/agents/runs/{result['run']['id']}").json()
    assert persisted["vision"]["text"] == VISUAL
    markdown = next(item for item in result["deliverables"] if item["fmt"] == "md")
    assert VISUAL in client.get(f"/api/deliverables/{markdown['id']}/download").text


def test_image_summary_prefers_visual_content_even_when_ocr_exists(client, image_source, monkeypatch):
    def forbidden_text_generation(*args, **kwargs):
        raise AssertionError("An image summary must preserve the visual model output, not replace it with an OCR-only summary")
    monkeypatch.setattr(reasoning_agent, "generate", forbidden_text_generation)
    response = client.post(f"/api/documents/{image_source['id']}/analyze", json={"title": "Summarize this image", "analysis_mode": "summary"})
    assert response.status_code == 200, response.text
    result = response.json()["run"]
    assert result["analysis"]["text"] == VISUAL
    assert result["vision"]["text"] == VISUAL
    assert result["run"]["verification_score"] is None


def test_missing_vision_model_is_an_explicit_error_not_a_skipped_inspection(client, image_source, monkeypatch):
    def unavailable(*args, **kwargs):
        raise InferenceUnavailable("Local vision model unavailable")
    monkeypatch.setattr(vision_agent, "generate", unavailable)
    response = client.post(f"/api/documents/{image_source['id']}/analyze", json={"title": "Extract image fields", "analysis_mode": "extract_fields"})
    assert response.status_code == 503
    assert "vision" in response.json()["detail"]
