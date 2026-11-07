"""Shared document workflow for synchronous API calls and persistent jobs."""
from __future__ import annotations
from datetime import datetime, timezone
from ..agents import orchestrator
from ..agents.progress import ProgressCallback, publish
from ..database import db
from ..domains.profiles import get_profile, list_profiles
from ..schemas.schemas import DocumentAnalysisRequest
from ..security.middleware import write_audit
from . import document_analysis
from .document_store import DocumentNotFound, use_document

class InvalidProfile(ValueError):
    pass

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def prepare_document(document: dict, on_progress: ProgressCallback | None = None):
    publish(on_progress, "extraction", "running", "Reading source pages", document["filename"])
    extraction = (document_analysis.extract_document(document["path"], on_progress=on_progress)
                  if on_progress else document_analysis.extract_document(document["path"]))
    db.execute(
        "UPDATE documents SET pages=?, extraction_method=?, ocr_pages=?, status=? WHERE id=?",
        (extraction.page_count, extraction.method, extraction.ocr_pages,
         "analyzed" if extraction.status == "ready" else extraction.status, document["id"]),
    )
    document = db.fetch_one("SELECT * FROM documents WHERE id=?", (document["id"],)) or document
    publish(on_progress, "extraction", "warning" if extraction.note or not extraction.text.strip() else "completed",
            f"Read {extraction.page_count} page(s); OCR supplied {extraction.ocr_pages} page(s)",
            extraction.note, **extraction.metadata(), characters=len(extraction.text))
    return document, extraction


def analyze_document(doc_id: int, payload: DocumentAnalysisRequest,
                     on_progress: ProgressCallback | None = None):
    with use_document(doc_id):
        return _analyze_document(doc_id, payload, on_progress)


def _analyze_document(doc_id: int, payload: DocumentAnalysisRequest,
                      on_progress: ProgressCallback | None = None):
    """Run a profile- and mode-aware analysis on one uploaded document."""
    publish(on_progress, "validation", "running", "Checking the document and analysis settings")
    document = db.fetch_one("SELECT * FROM documents WHERE id=?", (doc_id,))
    if not document:
        raise DocumentNotFound("Document not found")
    try:
        get_profile(payload.profile)
    except KeyError:
        allowed = ", ".join(item["id"] for item in list_profiles())
        raise InvalidProfile(f"Unknown profile '{payload.profile}'. Available: {allowed}.")
    publish(on_progress, "validation", "completed", "Document and settings checked",
            document["filename"], profile=payload.profile, mode=payload.analysis_mode)
    document, extraction = prepare_document(document, on_progress)
    text, note = extraction.text, extraction.note
    extraction_metadata = extraction.metadata()
    task_text = payload.title + " " + (payload.description or "")
    task_id = db.insert("tasks", {
        "title": payload.title,
        "description": (f"Profile: {payload.profile}; mode: {payload.analysis_mode}\n"
                        f"Document {document['filename']}: {text[:4000]}"),
        "task_type": payload.task_type or payload.analysis_mode,
        "status": "running",
        "run_id": None,
        "created_at": _now(),
    })
    try:
        run = orchestrator.run_pipeline(
            task_text=task_text,
            scenario_name=f"document:{document['filename']}",
            task_id=task_id,
            document=document,
            document_text=text,
            document_note=note,
            profile=payload.profile,
            analysis_mode=payload.analysis_mode,
            document_pages=extraction.pages,
            document_extraction=extraction_metadata,
            on_progress=on_progress,
        )
    except Exception:
        db.execute("UPDATE tasks SET status='error' WHERE id=?", (task_id,))
        raise
    db.execute("UPDATE tasks SET status=?, run_id=? WHERE id=?",
               (run["run"]["status"], run["run"]["id"], task_id))
    write_audit("document.analyze",
                detail=f"document {doc_id} ({document['filename']}) -> run {run['run']['id']}: "
                        f"profile={payload.profile}, mode={payload.analysis_mode}, "
                        f"{len(run['findings'])} finding(s), extraction={extraction.method}, "
                        f"OCR pages={extraction.ocr_pages}, status={run['run']['status']}")
    return {
        "task": db.fetch_one("SELECT * FROM tasks WHERE id=?", (task_id,)),
        "document": document,
        "run": run,
    }
