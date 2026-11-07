"""Local document chunking, embeddings, and an in-memory cosine index."""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Any

from .. import config

EMBED_DIM = 256
_WORD_RE = re.compile(r"[A-Za-z0-9]+")


def backend_info() -> dict[str, Any]:
    return {
        "embedding_backend": "hash-embedding (local lexical retrieval)" if config.EMBEDDING_BACKEND == "hash"
        else f"{config.INFERENCE_PROVIDER} (configured local encoder)",
        "vector_backend": "in-memory cosine index",
        "embedding_dim": EMBED_DIM if config.EMBEDDING_BACKEND == "hash" else None,
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
    """Compute real vectors using a single configured backend for the index."""
    if config.EMBEDDING_BACKEND == "hash":
        return hash_embedding(text)
    from ..models.providers import InferenceUnavailable, get_provider
    model = (config.OLLAMA_EMBED_MODEL if config.INFERENCE_PROVIDER == "ollama"
             else config.TRANSFORMERS_EMBED_MODEL_PATH)
    try:
        vector = get_provider().embed(text, model=model)
        if not vector or not all(math.isfinite(x) for x in vector):
            raise ValueError("Invalid embedding")
        return vector
    except Exception as exc:
        raise InferenceUnavailable("Local embedding model unavailable. Check the configured encoder.") from exc


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        raise ValueError("Embedding dimensions differ; rebuild the index.")
    n = len(a)
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
    document_id: int | None = None
    char_start: int | None = None
    char_end: int | None = None


class KnowledgeBase:
    """A tiny deterministic vector index (in-memory)."""

    def __init__(self) -> None:
        self._chunks: list[Chunk] = []

    def add(self, text: str, source: str, page: int = 1, document_id: int | None = None) -> int:
        added = 0
        # Map normalized chunk text to exact source spans, retaining whitespace for citations.
        tokens = list(re.finditer(r"\S+", text))
        cursor = 0
        for i, ch in enumerate(chunk_text(text)):
            words = ch.split()
            while cursor < len(tokens) and tokens[cursor].group() != words[0]:
                cursor += 1
            start = tokens[cursor].start() if cursor < len(tokens) else None
            end_index = cursor + len(words) - 1
            end = tokens[end_index].end() if end_index < len(tokens) else None
            exact = text[start:end] if start is not None and end is not None else ch
            cid = f"{source}::p{page}::c{i}"
            self._chunks.append(
                Chunk(id=cid, text=exact, source=source, page=page, embedding=embed(ch),
                      document_id=document_id, char_start=start, char_end=end)
            )
            added += 1
            # The next chunk starts at the overlap retained by chunk_text.
            overlap_length, overlap_words = 0, 0
            for word in reversed(words):
                overlap_length += len(word) + 1
                overlap_words += 1
                if overlap_length >= 80:
                    break
            cursor += len(words) - overlap_words
        return added

    def add_chunk(self, text: str, source: str, page: int = 1) -> None:
        cid = f"{source}::p{page}::c{len(self._chunks)}"
        self._chunks.append(
            Chunk(id=cid, text=text, source=source, page=page, embedding=embed(text))
        )

    def search(self, query: str, top_k: int = 4, document_ids: set[int] | None = None) -> list[dict]:
        if not self._chunks:
            return []
        qv = embed(query)
        scored = [
            {
                "id": c.id,
                "source": c.source,
                "page": c.page,
                "text": c.text,
                "score": round(cosine_similarity(qv, c.embedding), 4),
                "document_id": c.document_id, "char_start": c.char_start, "char_end": c.char_end,
            }
            for c in self._chunks
            if document_ids is None or c.document_id in document_ids
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

    def preview_chunks(self, n: int = 5) -> list[dict]:
        out = []
        for c in self._chunks[:n]:
            out.append({"id": c.id, "source": c.source, "page": c.page,
                        "text": c.text[:220]})
        return out
