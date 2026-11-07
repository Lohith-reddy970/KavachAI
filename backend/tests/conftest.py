"""Test fixtures: isolated SQLite DB + generated dir, airgapped configuration and test-only provider doubles."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="kavach-tests-"))
os.environ["KAVACH_DB"] = str(_TMP / "kavach.db")
os.environ["KAVACH_GENERATED"] = str(_TMP / "generated")
os.environ["KAVACH_UPLOADS"] = str(_TMP / "uploads")
os.environ["KAVACH_MODE"] = "airgapped"
os.environ["KAVACH_INFERENCE_PROVIDER"] = "ollama"
os.environ["KAVACH_EMBEDDING_BACKEND"] = "hash"
os.environ["KAVACH_SANDBOX_ENABLED"] = "false"
os.environ["OLLAMA_REASONING_MODEL"] = "qwen3:8b"
os.environ["OLLAMA_VISION_MODEL"] = "llava:7b"
os.environ["OLLAMA_OTHER_MODEL"] = "llama3.2:3b"
os.environ["OLLAMA_EMBED_MODEL"] = "nomic-embed-text:latest"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def local_inference_double(monkeypatch):
    """Unit tests isolate inference; no substitute provider ships in app code."""
    from app.agents import reasoning_agent, vision_agent, planner_agent
    from app.models.providers import GenerationResult, model_for_role

    def generate(prompt, *, role="other", **kwargs):
        text = "inspect_document" if role == "other" else "Test-only provider output for inference integration."
        return GenerationResult(text, model_for_role(role), "ollama", 7, 1)

    for module in (reasoning_agent, vision_agent, planner_agent):
        monkeypatch.setattr(module, "generate", generate)
