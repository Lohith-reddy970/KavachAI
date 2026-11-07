"""Local Ollama and Transformers inference; errors never fabricate output."""
from __future__ import annotations

import base64
import importlib.util
import json
import os
import threading
import time
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
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


class InferenceUnavailable(RuntimeError):
    """The configured local model cannot fulfill the request."""


class OllamaProvider(BaseModelProvider):
    """Adapter for the configured local Ollama server.

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
        if kwargs.get("max_tokens") is not None:
            payload["options"]["num_predict"] = max(1, min(2048, int(kwargs["max_tokens"])))
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


class TransformersProvider(BaseModelProvider):
    """Strictly local Hugging Face Transformers text and embedding provider.

    Model identifiers from the Hub are deliberately rejected. Models must be
    present in local directories, all ``from_pretrained`` calls use
    ``local_files_only=True`` and remote custom model code is disabled.
    """

    name = "transformers"
    is_external = False

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._causal_models: dict[str, tuple[Any, Any, Any, str]] = {}
        self._embedding_models: dict[str, tuple[Any, Any, Any, str]] = {}

    @staticmethod
    def _force_offline_mode() -> None:
        # Enforce offline behavior even if the wider environment was not set up
        # for an air-gapped Hugging Face installation.
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

    @staticmethod
    def _resolve_model_directory(model: str | None, configured: str = "") -> str:
        value = str(model or configured or "").strip()
        if not value:
            raise RuntimeError("Set a local Transformers model directory first.")
        path = Path(value).expanduser()
        try:
            path = path.resolve(strict=True)
        except OSError as exc:
            raise RuntimeError(
                "Transformers accepts an existing local model directory only; "
                "remote model IDs are disabled."
            ) from exc
        if not path.is_dir() or not (path / "config.json").is_file():
            raise RuntimeError(
                "Transformers accepts an existing local model directory containing "
                "config.json; remote model IDs are disabled."
            )
        return str(path)

    @staticmethod
    def _dependencies_available() -> tuple[bool, str]:
        missing = [name for name in ("torch", "transformers", "safetensors")
                   if importlib.util.find_spec(name) is None]
        if missing:
            return False, f"Install the optional Transformers dependencies: {', '.join(missing)}."
        return True, ""

    def _runtime(self) -> tuple[Any, Any]:
        self._force_offline_mode()
        try:
            import torch  # type: ignore
            import transformers  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Transformers inference needs the optional torch and transformers packages."
            ) from exc
        return torch, transformers

    @staticmethod
    def _device_and_dtype(torch: Any) -> tuple[str, Any]:
        requested = config.TRANSFORMERS_DEVICE
        cuda_available = bool(torch.cuda.is_available())
        if requested == "auto":
            device = "cuda" if cuda_available else "cpu"
        elif requested == "cuda":
            if not cuda_available:
                raise RuntimeError("KAVACH_TRANSFORMERS_DEVICE=cuda but CUDA is unavailable.")
            device = "cuda"
        elif requested == "cpu":
            device = "cpu"
        else:
            raise RuntimeError("KAVACH_TRANSFORMERS_DEVICE must be 'auto', 'cpu', or 'cuda'.")
        dtype = torch.float16 if device == "cuda" else torch.float32
        return device, dtype

    def _load_causal_model(self, model_path: str) -> tuple[Any, Any, Any, str]:
        with self._lock:
            cached = self._causal_models.get(model_path)
            if cached:
                return cached
            torch, transformers = self._runtime()
            device, dtype = self._device_and_dtype(torch)
            tokenizer = transformers.AutoTokenizer.from_pretrained(
                model_path,
                local_files_only=True,
                trust_remote_code=False,
            )
            model = transformers.AutoModelForCausalLM.from_pretrained(
                model_path,
                local_files_only=True,
                trust_remote_code=False,
                use_safetensors=True,
                torch_dtype=dtype,
            )
            model.to(device)
            model.eval()
            loaded = (torch, tokenizer, model, device)
            self._causal_models[model_path] = loaded
            return loaded

    def _load_embedding_model(self, model_path: str) -> tuple[Any, Any, Any, str]:
        with self._lock:
            cached = self._embedding_models.get(model_path)
            if cached:
                return cached
            torch, transformers = self._runtime()
            device, dtype = self._device_and_dtype(torch)
            tokenizer = transformers.AutoTokenizer.from_pretrained(
                model_path,
                local_files_only=True,
                trust_remote_code=False,
            )
            model = transformers.AutoModel.from_pretrained(
                model_path,
                local_files_only=True,
                trust_remote_code=False,
                use_safetensors=True,
                torch_dtype=dtype,
            )
            model.to(device)
            model.eval()
            loaded = (torch, tokenizer, model, device)
            self._embedding_models[model_path] = loaded
            return loaded

    @staticmethod
    def _tokenize_prompt(tokenizer: Any, prompt: str) -> Any:
        chat_template = getattr(tokenizer, "chat_template", None)
        if chat_template:
            try:
                return tokenizer.apply_chat_template(
                    [{"role": "user", "content": prompt}],
                    tokenize=True,
                    add_generation_prompt=True,
                    return_tensors="pt",
                    return_dict=True,
                )
            except (TypeError, ValueError):
                # Older/custom tokenizers may expose a template with a narrower API.
                pass
        return tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=config.TRANSFORMERS_MAX_INPUT_TOKENS,
        )

    def generate(self, prompt: str, *, model: str | None = None,
                 images: list[bytes] | None = None, **kwargs: Any) -> GenerationResult:
        if images:
            raise RuntimeError(
                "The Transformers provider currently supports local text models only; "
                "image requests need a vision-capable adapter."
            )
        model_path = self._resolve_model_directory(
            model, configured=config.TRANSFORMERS_MODEL_PATH)
        started = time.monotonic()
        with self._lock:
            torch, tokenizer, text_model, device = self._load_causal_model(model_path)
            encoded = self._tokenize_prompt(tokenizer, prompt)
            inputs = {key: value.to(device) for key, value in encoded.items()}
            input_ids = inputs["input_ids"]
            input_length = int(input_ids.shape[-1])
            if input_length > config.TRANSFORMERS_MAX_INPUT_TOKENS:
                inputs = {key: value[..., -config.TRANSFORMERS_MAX_INPUT_TOKENS:]
                          for key, value in inputs.items()}
                input_ids = inputs["input_ids"]
                input_length = int(input_ids.shape[-1])

            max_new_tokens = int(kwargs.get("max_new_tokens", config.TRANSFORMERS_MAX_NEW_TOKENS))
            max_new_tokens = max(1, min(2048, max_new_tokens))
            generation_options: dict[str, Any] = {
                "max_new_tokens": max_new_tokens,
                "do_sample": False,
            }
            pad_token_id = getattr(tokenizer, "pad_token_id", None)
            if pad_token_id is None:
                pad_token_id = getattr(tokenizer, "eos_token_id", None)
            if pad_token_id is not None:
                generation_options["pad_token_id"] = pad_token_id

            with torch.inference_mode():
                generated = text_model.generate(**inputs, **generation_options)
            new_tokens = generated[0, input_length:]
            output_text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
            token_count = int(new_tokens.shape[-1])

        return GenerationResult(
            text=output_text,
            model=Path(model_path).name,
            provider=self.name,
            tokens=token_count,
            latency_ms=int((time.monotonic() - started) * 1000),
            meta={"local_only": True, "device": device, "deterministic": True},
        )

    def embed(self, text: str, *, model: str | None = None) -> list[float]:
        model_path = self._resolve_model_directory(
            model, configured=config.TRANSFORMERS_EMBED_MODEL_PATH)
        with self._lock:
            torch, tokenizer, encoder, device = self._load_embedding_model(model_path)
            encoded = tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=min(512, config.TRANSFORMERS_MAX_INPUT_TOKENS),
            )
            inputs = {key: value.to(device) for key, value in encoded.items()}
            with torch.inference_mode():
                output = encoder(**inputs)
                hidden = output.last_hidden_state
                mask = inputs["attention_mask"].unsqueeze(-1).expand(hidden.size()).float()
                pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
                vector = torch.nn.functional.normalize(pooled, p=2, dim=1)[0]
            return [float(value) for value in vector.detach().cpu().tolist()]

    def health(self) -> dict[str, Any]:
        active = config.INFERENCE_PROVIDER == self.name
        dependencies, reason = self._dependencies_available()
        text_configured = False
        embedding_configured = False
        text_name = embedding_name = None
        try:
            text_path = self._resolve_model_directory(
                None, configured=config.TRANSFORMERS_MODEL_PATH)
            text_configured = True
            text_name = Path(text_path).name
        except RuntimeError:
            pass
        try:
            embedding_path = self._resolve_model_directory(
                None, configured=config.TRANSFORMERS_EMBED_MODEL_PATH)
            embedding_configured = True
            embedding_name = Path(embedding_path).name
        except RuntimeError:
            pass

        if not dependencies:
            status = "unavailable"
        elif not text_configured:
            status = "unconfigured" if active else "disabled"
            reason = "Set KAVACH_TRANSFORMERS_MODEL_PATH to a local text-model directory."
        else:
            status = "ready" if active else "available"
            reason = ""
        return {
            "provider": self.name,
            "status": status,
            "external": False,
            "local_only": True,
            "active": active,
            "reason": reason,
            "text_model": text_name,
            "embedding_model": embedding_name,
            "embedding_configured": embedding_configured,
            "vision_supported": False,
        }


# Only implemented providers are exposed to application code.
_PROVIDERS: dict[str, BaseModelProvider] = {
    "ollama": OllamaProvider(),
    "transformers": TransformersProvider(),
}


def active_provider_name() -> str:
    if config.INFERENCE_PROVIDER not in _PROVIDERS:
        raise ValueError(f"Unsupported inference provider: {config.INFERENCE_PROVIDER}")
    return config.INFERENCE_PROVIDER


def get_provider(name: str | None = None) -> BaseModelProvider:
    return _PROVIDERS[name or active_provider_name()]


def all_providers() -> dict[str, BaseModelProvider]:
    return dict(_PROVIDERS)


def model_for_role(role: str = "other") -> str:
    if config.INFERENCE_PROVIDER == "transformers":
        return config.TRANSFORMERS_MODEL_PATH if role.strip().lower() != "vision" else ""
    return config.OLLAMA_MODEL_BY_ROLE.get(role.strip().lower(), config.OLLAMA_OTHER_MODEL)


def generate(prompt: str, *, role: str = "other",
             model: str | None = None, **kwargs: Any) -> GenerationResult:
    """Return actual provider output or a visible availability error."""
    provider = get_provider()
    try:
        result = provider.generate(prompt, model=model or model_for_role(role), **kwargs)
        if not result.text.strip():
            raise ValueError("The model returned an empty response")
        return result
    except Exception as exc:
        raise InferenceUnavailable(
            f"Local inference unavailable ({provider.name}). Check the configured model and runtime."
        ) from exc
