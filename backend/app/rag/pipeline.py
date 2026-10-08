"""Deterministic RAG pipeline for KAVACH AI.

Design goals:
    * Works with ZERO heavy dependencies via a pure-python hash embedding.
    * Transparently upgrades to sentence-transformers + chromadb when they are
      importable (all such imports are guarded).
    * Fully deterministic so retrieval results are stable across demo runs.

Public API:
    chunk_text(text, ...)            -> list[str]
    hash_embedding(text, dim=256)    -> list[float]
    embed(text)                      -> list[float]
    cosine_similarity(a, b)          -> float
    KnowledgeBase                    -> in-memory index with add/search
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Any

from .. import config

# --- Optional heavy deps (guarded) -------------------------------------------
_ST_AVAILABLE = False
_CHROMA_AVAILABLE = False
_st_model = None
_ollama_embedding_failed = False
_active_embedding_backend: str | None = None

try:  # pragma: no cover - environment dependent
    from sentence_transformers import SentenceTransformer  # type: ignore

    _ST_AVAILABLE = True
except Exception:  # noqa: BLE001
    SentenceTransformer = None  # type: ignore

try:  # pragma: no cover - environment dependent
    import chromadb  # type: ignore

    _CHROMA_AVAILABLE = True
except Exception:  # noqa: BLE001
    chromadb = None  # type: ignore

EMBED_DIM = 256
_WORD_RE = re.compile(r"[A-Za-z0-9]+")


def backend_info() -> dict[str, Any]:
    """Report which embedding/vector backends are active."""
    if _active_embedding_backend:
        embed_backend = _active_embedding_backend
    elif config.INFERENCE_PROVIDER == "ollama" and not _ollama_embedding_failed:
        embed_backend = f"ollama ({config.OLLAMA_EMBED_MODEL})"
    elif _ST_AVAILABLE:
        embed_backend = "sentence-transformers"
    else:
        embed_backend = "hash-embedding (pure-python fallback)"
    vector_backend = "chromadb" if _CHROMA_AVAILABLE else "in-memory numpy-free cosine"
    return {
        "embedding_backend": embed_backend,
        "vector_backend": vector_backend,
        "embedding_dim": EMBED_DIM,
        "sentence_transformers_available": _ST_AVAILABLE,
        "chromadb_available": _CHROMA_AVAILABLE,
    }


def chunk_text(text: str, chunk_size: int = 480, overlap: int = 80) -> list[str]:
    """Split text into overlapping character chunks on sentence-ish boundaries."""
    text = (text or "").strip()
    if not text:
        return []
    # Prefer to break on paragraph/sentence boundaries where possible.
    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for word in words:
        current.append(word)
        length += len(word) + 1
        if length >= chunk_size:
            chunks.append(" ".join(current))
            # keep overlap words
            keep = []
            klen = 0
            for w in reversed(current):
                klen += len(w) + 1
                keep.insert(0, w)
                if klen >= overlap:
                    break
            current = keep
            length = sum(len(w) + 1 for w in current)
    if current:
        chunks.append(" ".join(current))
    return chunks


def hash_embedding(text: str, dim: int = EMBED_DIM) -> list[float]:
    """Deterministic bag-of-words hash embedding (pure python, no deps).

    Each token is hashed into one of ``dim`` buckets with a signed weight; the
    resulting vector is L2-normalized. Same text -> same vector, always.
    """
    vec = [0.0] * dim
    tokens = _WORD_RE.findall((text or "").lower())
    for tok in tokens:
        h = hashlib.md5(tok.encode("utf-8")).digest()
        idx = int.from_bytes(h[:4], "big") % dim
        sign = 1.0 if h[4] & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def embed(text: str) -> list[float]:
    """Embed locally with Ollama/Nomic, Sentence Transformers, or hash fallback."""
    global _st_model
    global _ollama_embedding_failed, _active_embedding_backend

    if config.INFERENCE_PROVIDER == "ollama" and not _ollama_embedding_failed:
        try:
            from ..models.providers import get_provider

            vector = get_provider().embed(text, model=config.OLLAMA_EMBED_MODEL)
            if vector:
                _active_embedding_backend = f"ollama ({config.OLLAMA_EMBED_MODEL})"
                return vector
            _ollama_embedding_failed = True
        except Exception:  # noqa: BLE001 - local RAG remains available without Ollama
            _ollama_embedding_failed = True

    if _ST_AVAILABLE:  # pragma: no cover - environment dependent
        try:
            if _st_model is None:
                _st_model = SentenceTransformer("all-MiniLM-L6-v2")
            vec = _st_model.encode(text, normalize_embeddings=True)
            _active_embedding_backend = "sentence-transformers"
            return [float(x) for x in vec]
        except Exception:  # noqa: BLE001 - fall back on any failure
            _active_embedding_backend = "hash-embedding (pure-python fallback)"
            return hash_embedding(text)
    _active_embedding_backend = "hash-embedding (pure-python fallback)"
    return hash_embedding(text)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(x * x for x in a[:n]))
    nb = math.sqrt(sum(x * x for x in b[:n]))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@dataclass
class Chunk:
    id: str
    text: str
    source: str
    page: int
    embedding: list[float] = field(default_factory=list)


class KnowledgeBase:
    """A tiny deterministic vector index (in-memory)."""

    def __init__(self) -> None:
        self._chunks: list[Chunk] = []

    def add(self, text: str, source: str, page: int = 1) -> int:
        added = 0
        for i, ch in enumerate(chunk_text(text)):
            cid = f"{source}::p{page}::c{i}"
            self._chunks.append(
                Chunk(id=cid, text=ch, source=source, page=page, embedding=embed(ch))
            )
            added += 1
        return added

    def add_chunk(self, text: str, source: str, page: int = 1) -> None:
        cid = f"{source}::p{page}::c{len(self._chunks)}"
        self._chunks.append(
            Chunk(id=cid, text=text, source=source, page=page, embedding=embed(text))
        )

    def search(self, query: str, top_k: int = 4) -> list[dict]:
        qv = embed(query)
        scored = [
            {
                "id": c.id,
                "source": c.source,
                "page": c.page,
                "text": c.text,
                "score": round(cosine_similarity(qv, c.embedding), 4),
            }
            for c in self._chunks
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def stats(self) -> dict[str, Any]:
        sources: dict[str, int] = {}
        for c in self._chunks:
            sources[c.source] = sources.get(c.source, 0) + 1
        return {
            "total_chunks": len(self._chunks),
            "sources": [{"name": k, "chunks": v} for k, v in sources.items()],
            "backend": backend_info(),
        }

    def sample_chunks(self, n: int = 5) -> list[dict]:
        out = []
        for c in self._chunks[:n]:
            out.append({"id": c.id, "source": c.source, "page": c.page,
                        "text": c.text[:220]})
        return out
