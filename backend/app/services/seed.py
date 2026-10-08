"""Database seeding for KAVACH AI.

Populates the models catalog and the demo documents metadata on startup. Idempotent:
seeding only runs when the relevant tables are empty. Document metadata reflects the
files produced by demo-data/generate_demo_data.py (or their .txt fallbacks).
"""
from __future__ import annotations

from datetime import datetime, timezone

from .. import config
from ..database import db
from . import scenario

MODELS = [
    {"name": config.OLLAMA_REASONING_MODEL, "provider": "ollama", "kind": "reasoning",
     "status": "configured", "params": "8.2B · Q4_K_M",
     "routing_rule": "General reasoning and evidence synthesis."},
    {"name": config.OLLAMA_VISION_MODEL, "provider": "ollama", "kind": "vision",
     "status": "configured", "params": "7B · Q4_0",
     "routing_rule": "P&ID and image analysis."},
    {"name": config.OLLAMA_OTHER_MODEL, "provider": "ollama", "kind": "other",
     "status": "configured", "params": "3.2B · Q4_K_M",
     "routing_rule": "Code, classification, extraction, and planner choices."},
    {"name": config.OLLAMA_EMBED_MODEL, "provider": "ollama", "kind": "embedding",
     "status": "configured", "params": "137M · F16 · 768d",
     "routing_rule": "Local knowledge-base embeddings."},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed_models() -> None:
    # This is a configuration-derived catalog, so refresh it at startup to pick
    # up changed local model tags rather than leaving the old demo placeholders.
    db.execute("DELETE FROM models")
    for m in MODELS:
        db.insert("models", m)


def seed_documents() -> None:
    if db.count("documents") > 0:
        return
    for d in scenario.DEMO_DOCUMENTS:
        # Determine actual path (file may be the pdf/png OR the .txt fallback).
        primary = config.DEMO_DATA_DIR / d["filename"]
        fallback = primary.with_suffix(".txt")
        if primary.exists():
            path, size = primary, primary.stat().st_size
        elif fallback.exists():
            path, size = fallback, fallback.stat().st_size
        else:
            path, size = primary, 0
        db.insert("documents", {
            "name": d["name"],
            "filename": path.name,
            "path": str(path),
            "doc_type": d["doc_type"],
            "size_bytes": size,
            "pages": d["pages"],
            "status": "ready",
            "summary": d["summary"],
            "created_at": _now(),
        })


def seed_all() -> None:
    seed_models()
    seed_documents()
    # Warm the knowledge base so /api/knowledge is populated immediately.
    from . import knowledge
    knowledge.get_kb()
