"""Offline-only behavior for the optional local Transformers provider."""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from app import config
from app.models import providers
from app.models.providers import TransformersProvider
from app.models.router import route, routing_rules
from app.rag import pipeline
from app.security.guard import assert_provider_allowed


def test_transformers_provider_rejects_remote_model_ids():
    provider = TransformersProvider()

    with pytest.raises(RuntimeError, match="remote model IDs are disabled"):
        provider.generate("Summarize this report", model="org/model-name")


def test_transformers_model_directory_must_exist_locally(tmp_path):
    provider = TransformersProvider()

    with pytest.raises(RuntimeError, match="existing local model directory"):
        provider.generate("Summarize this report", model=str(tmp_path))


def test_transformers_loaders_are_local_only_and_never_enable_remote_code(
    monkeypatch, tmp_path
):
    model_dir = tmp_path / "local-model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    calls = {}

    class FakeModel:
        def to(self, _device):
            return self

        def eval(self):
            return self

    class FakeLoader:
        @staticmethod
        def from_pretrained(model_path, **kwargs):
            calls["model_path"] = model_path
            calls.update(kwargs)
            return FakeModel()

    class FakeCuda:
        @staticmethod
        def is_available():
            return False

    fake_torch = SimpleNamespace(cuda=FakeCuda, float16="float16", float32="float32")
    fake_transformers = SimpleNamespace(
        AutoTokenizer=FakeLoader,
        AutoModelForCausalLM=FakeLoader,
    )
    provider = TransformersProvider()
    monkeypatch.setattr(provider, "_runtime", lambda: (fake_torch, fake_transformers))

    provider._load_causal_model(str(model_dir))

    assert calls["model_path"] == str(model_dir)
    assert calls["local_files_only"] is True
    assert calls["trust_remote_code"] is False
    assert calls["use_safetensors"] is True


def test_transformers_forces_hugging_face_offline_environment(monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "0")
    monkeypatch.setenv("HF_HUB_DISABLE_TELEMETRY", "0")

    TransformersProvider._force_offline_mode()

    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"
    assert os.environ["HF_HUB_DISABLE_TELEMETRY"] == "1"


def test_transformers_generation_errors_without_local_model(monkeypatch):
    monkeypatch.setattr(config, "INFERENCE_PROVIDER", "transformers")
    monkeypatch.setattr(config, "TRANSFORMERS_MODEL_PATH", "")

    with pytest.raises(providers.InferenceUnavailable, match="Local inference unavailable"):
        providers.generate("Summarize a local report", role="reasoning")


def test_transformers_model_routing_uses_local_text_model_and_marks_vision_unsupported(monkeypatch):
    model_path = "C:/kavach-models/instruct"
    monkeypatch.setattr(config, "INFERENCE_PROVIDER", "transformers")
    monkeypatch.setattr(config, "TRANSFORMERS_MODEL_PATH", model_path)

    assert providers.model_for_role("reasoning") == model_path
    assert route("Review this inspection report").model == model_path
    assert "unsupported" in route("Describe this P&ID image").model
    assert routing_rules()[0]["model"] == model_path
    assert "unsupported" in routing_rules()[1]["model"]


def test_transformers_embedding_uses_configured_local_encoder(monkeypatch):
    calls = {}

    class CaptureProvider:
        def embed(self, text, *, model=None):
            calls.update(text=text, model=model)
            return [0.25, 0.75]

    monkeypatch.setattr(config, "INFERENCE_PROVIDER", "transformers")
    monkeypatch.setattr(config, "TRANSFORMERS_EMBED_MODEL_PATH", "C:/kavach-models/embed")
    monkeypatch.setattr(providers, "get_provider", lambda: CaptureProvider())
    monkeypatch.setattr(config, "EMBEDDING_BACKEND", "provider")

    assert pipeline.embed("local evidence") == [0.25, 0.75]
    assert calls == {
        "text": "local evidence",
        "model": "C:/kavach-models/embed",
    }
    assert pipeline.backend_info()["embedding_backend"] == "transformers (configured local encoder)"


def test_hash_embeddings_do_not_require_a_model(monkeypatch):
    monkeypatch.setattr(config, "INFERENCE_PROVIDER", "transformers")
    monkeypatch.setattr(config, "EMBEDDING_BACKEND", "hash")
    assert pipeline.embed("local retrieval") == pipeline.hash_embedding("local retrieval")
    assert "lexical" in pipeline.backend_info()["embedding_backend"]



def test_transformers_provider_is_advertised_as_local_only():
    health = TransformersProvider().health()

    assert health["provider"] == "transformers"
    assert health["external"] is False
    assert health["local_only"] is True
    assert health["vision_supported"] is False


def test_transformers_provider_is_allowed_in_airgapped_mode():
    assert_provider_allowed("transformers", is_external=TransformersProvider.is_external)


def test_models_api_advertises_transformers_as_local_provider(client):
    response = client.get("/api/models")

    assert response.status_code == 200
    health = response.json()["providers"]["transformers"]
    assert health["external"] is False
    assert health["local_only"] is True
    assert health["vision_supported"] is False
