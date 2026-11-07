"""Refresh model assignments from configuration; no content is preloaded."""
from __future__ import annotations

from pathlib import Path

from .. import config
from ..database import db

MODELS = [
    {"name": config.OLLAMA_REASONING_MODEL, "provider": "ollama", "kind": "reasoning",
     "status": "configured", "params": "configured model",
     "routing_rule": "General reasoning and evidence synthesis."},
    {"name": config.OLLAMA_VISION_MODEL, "provider": "ollama", "kind": "vision",
     "status": "configured", "params": "configured model",
     "routing_rule": "P&ID and image analysis."},
    {"name": config.OLLAMA_OTHER_MODEL, "provider": "ollama", "kind": "other",
     "status": "configured", "params": "configured model",
     "routing_rule": "Code, classification, extraction, and planner choices."},
    {"name": config.OLLAMA_EMBED_MODEL, "provider": "ollama", "kind": "embedding",
     "status": "configured", "params": "configured model",
     "routing_rule": "Local knowledge-base embeddings."},
]


def refresh_models() -> None:
    # Refresh configuration-derived assignments at startup.
    db.execute("DELETE FROM models")
    for m in _model_catalog():
        db.insert("models", m)


def _local_model_entry(path: str, *, name: str, kind: str,
                       routing_rule: str) -> dict:
    directory = Path(path).expanduser() if path else None
    configured = bool(directory and directory.is_dir()
                      and (directory / "config.json").is_file())
    return {
        "name": directory.name if configured else name,
        "provider": "transformers",
        "kind": kind,
        "status": "configured" if configured else "unconfigured",
        "params": "local model files" if configured else "local path required",
        "routing_rule": routing_rule,
    }


def _model_catalog() -> list[dict]:
    if config.INFERENCE_PROVIDER != "transformers":
        return MODELS
    entries = [
        _local_model_entry(
            config.TRANSFORMERS_MODEL_PATH,
            name="Transformers text model",
            kind="reasoning",
            routing_rule="Local text generation for reasoning, summaries, and other text tasks.",
        ),
    ]
    if config.TRANSFORMERS_EMBED_MODEL_PATH:
        entries.append(_local_model_entry(
            config.TRANSFORMERS_EMBED_MODEL_PATH,
            name="Transformers embedding model",
            kind="embedding",
            routing_rule="Configured local RAG encoder.",
        ))
    return entries
