"""Read and remove uploaded sources without interrupting admitted analyses."""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from pathlib import Path
import threading

from .. import config
from ..database import db
from ..security.middleware import write_audit
from .document_analysis import extract_document

_lock = threading.RLock()
_readers: Counter[int] = Counter()
PREVIEW_CHARS = 200_000
MEDIA_TYPES = {
    "pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "txt": "text/plain", "csv": "text/plain", "py": "text/plain",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class DocumentNotFound(LookupError):
    pass


class DocumentBusy(RuntimeError):
    pass


class DocumentAccessError(RuntimeError):
    pass


def get_document(doc_id: int) -> dict:
    document = db.fetch_one("SELECT * FROM documents WHERE id=? AND retired_sample=0", (doc_id,))
    if not document:
        raise DocumentNotFound("Document not found")
    return document


@contextmanager
def use_document(doc_id: int):
    """Pin a source while submitting a job or running either analysis workflow."""
    with _lock:
        document = get_document(doc_id)
        _readers[doc_id] += 1
    try:
        yield document
    finally:
        with _lock:
            _readers[doc_id] -= 1
            if not _readers[doc_id]:
                del _readers[doc_id]


def _source_path(document: dict) -> Path:
    base = config.UPLOADS_DIR.resolve()
    path = Path(document["path"]).resolve()
    if path == base or not path.is_relative_to(base):
        raise DocumentAccessError("The stored source is outside the document upload directory.")
    if path.suffix.lower().lstrip(".") not in MEDIA_TYPES:
        raise DocumentAccessError("This stored file type cannot be opened from the Vault.")
    return path


def source_file(doc_id: int) -> tuple[dict, Path, str]:
    document = get_document(doc_id)
    path = _source_path(document)
    if not path.is_file():
        raise DocumentNotFound("The document source file is missing from local storage.")
    return document, path, MEDIA_TYPES[path.suffix.lower().lstrip(".")]


def preview_document(doc_id: int) -> dict:
    with use_document(doc_id):
        document, path, _ = source_file(doc_id)
        ext = path.suffix.lower()
        kind, text, note = "text", "", ""
        if ext == ".pdf":
            kind = "pdf"
        elif ext in {".png", ".jpg", ".jpeg"}:
            kind = "image"
        elif ext in {".txt", ".csv", ".py"}:
            with path.open(encoding="utf-8", errors="replace") as source:
                text = source.read(PREVIEW_CHARS + 1)
            note = "" if text.strip() else "The document contains no text."
        elif ext == ".docx":
            extraction = extract_document(str(path))
            text, note = extraction.text, extraction.note
        return {"id": doc_id, "filename": document["filename"], "kind": kind, "text": text[:PREVIEW_CHARS],
                "truncated": len(text) > PREVIEW_CHARS, "note": note}


def delete_document(doc_id: int) -> dict:
    # The lock shares the admission boundary with synchronous analyses and job submission.
    with _lock, db.db_cursor() as cur:
        cur.execute("BEGIN IMMEDIATE")
        cur.execute("SELECT * FROM documents WHERE id=? AND retired_sample=0", (doc_id,))
        document = db.row_to_dict(cur.fetchone())
        if not document:
            raise DocumentNotFound("Document not found")
        cur.execute("SELECT 1 FROM analysis_jobs WHERE document_id=? AND status IN ('queued', 'running') LIMIT 1", (doc_id,))
        if _readers[doc_id] or cur.fetchone():
            raise DocumentBusy("This document is being analyzed. Wait for its queued or running analysis to finish, then delete it.")
        cur.execute("SELECT 1 FROM analysis_batch_items WHERE document_id=? AND status IN ('pending', 'queued', 'running') LIMIT 1", (doc_id,))
        if cur.fetchone():
            raise DocumentBusy("This document belongs to an unfinished analysis batch. Wait for the batch to finish, then delete it.")
        path = _source_path(document)
        removed = path.exists()
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            raise DocumentAccessError("The source file could not be removed. Close any application using it and try again.") from exc
        cur.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    # KnowledgeBase signatures include document IDs: the next lookup rebuilds without this source.
    write_audit("document.delete", detail=f"document={doc_id}; filename={document['filename']}; file_removed={removed}; analysis history retained")
    return {"id": doc_id, "filename": document["filename"], "deleted": True,
            "file_removed": removed, "history_retained": True}
