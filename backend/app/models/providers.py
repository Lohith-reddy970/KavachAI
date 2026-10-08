"""Model-provider abstraction for KAVACH AI.

Defines a clean ``BaseModelProvider`` interface and three adapters:

* ``MockLocalModelProvider`` - fully offline, deterministic inference for tests
  and repeatable demos. It produces stable, seed-based responses.
* ``OllamaProvider`` - adapter for a local Ollama runtime
  (http://localhost:11434). Host development defaults to this local provider;
  it is loopback-guarded in airgapped mode.
* ``VLLMProvider`` - stub adapter for a local vLLM OpenAI-compatible server.

All providers advertise ``is_external`` so the airgapped security guard can decide
whether they are permitted. Only cloud providers are considered external.
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .. import config


@dataclass
class GenerationResult:
    text: str
    model: str
    provider: str
    tokens: int
    latency_ms: int
    meta: dict[str, Any] = field(default_factory=dict)


class BaseModelProvider(ABC):
    """Abstract interface every model backend implements."""

    name: str = "base"
    #: True only for cloud services; blocked in airgapped mode.
    is_external: bool = False

    @abstractmethod
    def generate(self, prompt: str, *, model: str, **kwargs: Any) -> GenerationResult:
        ...

    @abstractmethod
    def embed(self, text: str, *, model: str = "local-embed") -> list[float]:
        ...

    @abstractmethod
    def health(self) -> dict[str, Any]:
        ...


def _seed_int(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)


class MockLocalModelProvider(BaseModelProvider):
    """Deterministic, offline provider.

    Responses are derived from a hash of the prompt so the same input always
    yields the same output - ideal for a reproducible hackathon demo. No network,
    no GPU, no external models are touched.
    """

    name = "mock-local"
    is_external = False

    def generate(self, prompt: str, *, model: str = config.OLLAMA_OTHER_MODEL,
                 **kwargs: Any) -> GenerationResult:
        seed = _seed_int(prompt + model)
        # Deterministic pseudo latency/token counts for realism.
        latency = 40 + (seed % 260)
        tokens = 48 + (seed % 400)
        text = (
            f"[{model} @ local] Deterministic analysis for prompt of "
            f"{len(prompt)} chars. Conclusion reference #{seed % 100000:05d}."
        )
        return GenerationResult(
            text=text,
            model=model,
            provider=self.name,
            tokens=tokens,
            latency_ms=latency,
            meta={"deterministic": True, "seed": seed % 100000},
        )

    def embed(self, text: str, *, model: str = "local-embed") -> list[float]:
        # Delegate to the RAG hash-embedding so embeddings are consistent app-wide.
        from ..rag.pipeline import hash_embedding

        return hash_embedding(text)

    def health(self) -> dict[str, Any]:
        return {"provider": self.name, "status": "online", "external": False}


class OllamaProvider(BaseModelProvider):
    """Optional adapter for a local Ollama server (opt-in, never the default).

    Ollama runs models locally (not a cloud API), so it is NOT flagged external.
    Every call is checked by the airgap guard, so only a loopback URL is reachable
    in airgapped mode. Uses the stdlib only (no extra dependency).
    """

    name = "ollama"
    is_external = False

    def __init__(self, base_url: str | None = None, timeout_s: float | None = None) -> None:
        self.base_url = (base_url or config.OLLAMA_BASE_URL).rstrip("/")
        self.timeout_s = timeout_s or config.OLLAMA_TIMEOUT_S

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        from ..security.guard import assert_local_url

        url = f"{self.base_url}{path}"
        assert_local_url(url)
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    def generate(self, prompt: str, *, model: str | None = None,
                 images: list[bytes] | None = None, **kwargs: Any) -> GenerationResult:
        model = model or config.OLLAMA_OTHER_MODEL
        started = time.monotonic()
        payload: dict[str, Any] = {
            "model": model, "prompt": prompt, "stream": False,
            "options": {"temperature": 0, "seed": 0},
        }
        if images:
            payload["images"] = [base64.b64encode(image).decode("ascii") for image in images]
        data = self._post("/api/generate", payload)
        return GenerationResult(
            text=str(data.get("response", "")).strip(),
            model=model,
            provider=self.name,
            tokens=int(data.get("eval_count", 0) or 0),
            latency_ms=int((time.monotonic() - started) * 1000),
            meta={"deterministic": False},
        )

    def embed(self, text: str, *, model: str | None = None) -> list[float]:
        model = model or config.OLLAMA_EMBED_MODEL
        data = self._post("/api/embeddings", {"model": model, "prompt": text})
        return [float(x) for x in data.get("embedding", [])]

    def health(self) -> dict[str, Any]:
        # No network probe here: /api/models must stay fast and offline-safe.
        enabled = config.INFERENCE_PROVIDER == self.name
        return {"provider": self.name, "status": "enabled" if enabled else "disabled",
                "external": False, "base_url": self.base_url,
                "models": dict(config.OLLAMA_MODEL_BY_ROLE),
                "embedding_model": config.OLLAMA_EMBED_MODEL}


class VLLMProvider(BaseModelProvider):
    """Stub adapter for a local vLLM OpenAI-compatible server."""

    name = "vllm"
    is_external = False

    def __init__(self, base_url: str = "http://localhost:8001/v1") -> None:
        self.base_url = base_url

    def generate(self, prompt: str, *, model: str = config.OLLAMA_REASONING_MODEL,
                 **kwargs: Any) -> GenerationResult:
        raise NotImplementedError(
            "VLLMProvider is a stub in the prototype. Point base_url at a running "
            "vLLM server and implement the /v1/completions call to enable it."
        )

    def embed(self, text: str, *, model: str = "local-embed") -> list[float]:
        raise NotImplementedError("VLLMProvider.embed is a stub in the prototype.")

    def health(self) -> dict[str, Any]:
        return {"provider": self.name, "status": "offline-stub", "external": False,
                "base_url": self.base_url}


# Registry -------------------------------------------------------------------
_PROVIDERS: dict[str, BaseModelProvider] = {
    "mock-local": MockLocalModelProvider(),
    "ollama": OllamaProvider(),
    "vllm": VLLMProvider(),
}

#: The offline default. Always available, never touches the network.
DEFAULT_PROVIDER = "mock-local"


def active_provider_name() -> str:
    name = config.INFERENCE_PROVIDER
    return name if name in _PROVIDERS else DEFAULT_PROVIDER


def get_provider(name: str | None = None) -> BaseModelProvider:
    return _PROVIDERS[name or active_provider_name()]


def all_providers() -> dict[str, BaseModelProvider]:
    return dict(_PROVIDERS)


def model_for_role(role: str = "other") -> str:
    """Return the configured Ollama model for a generation role."""
    return config.OLLAMA_MODEL_BY_ROLE.get(role.strip().lower(), config.OLLAMA_OTHER_MODEL)


def generate_with_fallback(prompt: str, *, role: str = "other",
                           model: str | None = None, **kwargs: Any) -> GenerationResult:
    """Generate with the active provider, falling back to the mock on any failure.

    Keeps runs working when an optional local server (e.g. Ollama) is down.
    ``meta['fallback']`` records why the mock was used. If no explicit model is
    supplied, ``role`` selects the locally configured model.
    """
    selected_model = model or model_for_role(role)
    provider = get_provider()
    if provider.name == DEFAULT_PROVIDER:
        return provider.generate(prompt, model=selected_model, **kwargs)
    try:
        return provider.generate(prompt, model=selected_model, **kwargs)
    except Exception as exc:  # noqa: BLE001 - any failure degrades to offline mock
        result = _PROVIDERS[DEFAULT_PROVIDER].generate(
            prompt, model=selected_model, **kwargs)
        result.meta["fallback"] = f"{provider.name} unavailable: {exc!r}"
        return result
