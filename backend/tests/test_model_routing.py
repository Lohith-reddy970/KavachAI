"""Role-specific local model selection and Ollama request tests."""
from __future__ import annotations

import base64

from app import config
from app.agents import planner_agent
from app.models import providers
from app.models.providers import GenerationResult, OllamaProvider
from app.models.router import route, routing_rules
from app.rag import pipeline


def test_configured_models_are_assigned_by_role():
    assert providers.model_for_role("reasoning") == "qwen3:8b"
    assert providers.model_for_role("vision") == "llava:7b"
    assert providers.model_for_role("other") == "llama3.2:3b"
    assert providers.model_for_role("unknown") == "llama3.2:3b"


def test_keyword_router_selects_configured_model_for_each_task_kind():
    assert route("Analyze the inspection report for corrosion").model == "qwen3:8b"
    assert route("Inspect the P&ID image").model == "llava:7b"
    assert route("Review this Python source code").model == "llama3.2:3b"
    assert route("Classify and extract fields from this CSV").model == "llama3.2:3b"
    assert {r["model"] for r in routing_rules()} == {
        "qwen3:8b", "llava:7b", "llama3.2:3b",
    }


def test_generation_for_role_passes_selected_model(monkeypatch):
    calls = {}

    class CaptureProvider:
        name = "ollama"

        def generate(self, prompt, *, model=None, **kwargs):
            calls.update(prompt=prompt, model=model, kwargs=kwargs)
            return GenerationResult("ok", model, self.name, 1, 1)

    monkeypatch.setattr(providers, "get_provider", lambda: CaptureProvider())
    providers.generate_with_fallback("inspect this image", role="vision", images=[b"image"])

    assert calls["model"] == "llava:7b"
    assert calls["kwargs"] == {"images": [b"image"]}


def test_ollama_vision_request_base64_encodes_image(monkeypatch):
    captured = {}
    provider = OllamaProvider(base_url="http://localhost:11434")

    def fake_post(path, payload):
        captured.update(path=path, payload=payload)
        return {"response": "pump P-101 visible", "eval_count": 4}

    monkeypatch.setattr(provider, "_post", fake_post)
    result = provider.generate("Inspect the P&ID", model="llava:7b", images=[b"pid-image"])

    assert result.model == "llava:7b"
    assert captured["path"] == "/api/generate"
    assert captured["payload"]["images"] == [base64.b64encode(b"pid-image").decode("ascii")]


def test_rag_uses_nomic_embedding_when_ollama_is_active(monkeypatch):
    calls = {}

    class CaptureProvider:
        def embed(self, text, *, model=None):
            calls.update(text=text, model=model)
            return [0.25, 0.75]

    monkeypatch.setattr(config, "INFERENCE_PROVIDER", "ollama")
    monkeypatch.setattr(providers, "get_provider", lambda: CaptureProvider())
    monkeypatch.setattr(pipeline, "_ollama_embedding_failed", False)
    monkeypatch.setattr(pipeline, "_active_embedding_backend", None)

    assert pipeline.embed("local evidence") == [0.25, 0.75]
    assert calls == {"text": "local evidence", "model": "nomic-embed-text:latest"}
    assert "nomic-embed-text" in pipeline.backend_info()["embedding_backend"]


def test_planner_uses_other_text_model_for_its_local_choice(monkeypatch):
    calls = {}

    def capture(prompt, *, role="other", **kwargs):
        calls["role"] = role
        return GenerationResult("inspect_document", "llama3.2:3b", "ollama", 1, 1)

    monkeypatch.setattr(planner_agent, "generate_with_fallback", capture)
    options = [
        planner_agent.PlannerDecision("inspect_document", "load docs"),
        planner_agent.PlannerDecision("search_knowledge", "retrieve context"),
    ]
    decision = planner_agent.PlannerAgent()._llm_choice(
        planner_agent.RunContext(task_text="Inspect P&ID"), options)

    assert decision.action == "inspect_document"
    assert calls["role"] == "other"
