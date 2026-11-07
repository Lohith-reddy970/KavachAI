"""Build the local index exclusively from stored user documents."""
from __future__ import annotations

import threading
from pathlib import Path

from .. import config
from ..database import db
from ..rag.pipeline import KnowledgeBase
from .document_analysis import extract_document

_KB: KnowledgeBase | None = None
_signature: tuple = ()
_lock = threading.Lock()


def get_kb(document_ids: set[int] | None = None) -> KnowledgeBase:
    global _KB, _signature
    with _lock:
        documents = db.fetch_all("SELECT id, filename, path FROM documents WHERE retired_sample=0 ORDER BY id")
        if document_ids is not None:
            documents = [document for document in documents if document["id"] in document_ids]
        files = []
        for document in documents:
            path = Path(document["path"])
            try:
                stat = path.stat()
                files.append((document, stat.st_mtime_ns, stat.st_size))
            except OSError:
                continue
        signature = (config.EMBEDDING_BACKEND, config.INFERENCE_PROVIDER,
                     config.OLLAMA_EMBED_MODEL, config.TRANSFORMERS_EMBED_MODEL_PATH,
                     tuple((d["id"], d["path"], modified, size) for d, modified, size in files))
        if _KB is None or signature != _signature:
            index = KnowledgeBase()
            for document, _, _ in files:
                extraction = extract_document(document["path"])
                for page in extraction.pages:
                    if page.text.strip():
                        index.add(page.text, source=document["filename"], page=page.number, document_id=document["id"])
            _KB, _signature = index, signature
        return _KB


def stats() -> dict:
    kb = get_kb()
    return {**kb.stats(), "preview_chunks": kb.preview_chunks(6)}
