"""All KAVACH AI HTTP routes."""
from __future__ import annotations

import os
import ipaddress
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response

from .. import config
from ..agents import orchestrator, planner_agent
from ..agents.tools import REGISTRY
from ..database import db
from ..domains.profiles import ANALYSIS_MODES, get_profile, list_profiles
from ..models.providers import active_provider_name, all_providers
from ..models.router import routing_rules
from ..schemas.schemas import (AgentRunRequest, DocumentAnalysisRequest,
                               HealthResponse, KnowledgeSearchRequest,
                               KnowledgeSearchResponse, ReviewRequest, TaskCreate,
                               SandboxExecuteRequest)
from ..schemas.schemas import AnalysisJobRequest, BatchAnalysisRequest, DocumentChatRequest, PassageRequest
from ..security.guard import ValidationError, safe_join, validate_upload
from ..security.middleware import write_audit
from ..security import sandbox
from ..services import analysis as analysis_service
from ..services import knowledge as knowledge_service
from ..services import system_status
from ..services import analysis_jobs
from ..services import document_store
from ..services import batch_jobs, document_chat, evidence_preview
from ..services.deliverables import optional_formats

router = APIRouter(prefix="/api")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Health / system ----------------------------------------------------------
@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", mode=config.KAVACH_MODE,
                          version=config.VERSION, app=config.APP_NAME)


@router.get("/system/status")
def system_status_endpoint():
    return system_status.snapshot()


# Explicit user execution, kept outside the document planner's tool allowlist.
def _require_local_sandbox_client(request: Request) -> None:
    try:
        peer = ipaddress.ip_address(request.client.host if request.client else "")
        if isinstance(peer, ipaddress.IPv6Address) and peer.ipv4_mapped is not None:
            peer = peer.ipv4_mapped
        local = peer.is_loopback
    except ValueError:
        local = False
    if not local or request.url.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise HTTPException(status_code=403, detail="Sandbox execution is available only through the local interface.")
    origin = request.headers.get("origin")
    if origin and origin not in config.CORS_ORIGINS:
        raise HTTPException(status_code=403, detail="This browser origin is not permitted to use the sandbox.")


@router.get("/sandbox/status")
def sandbox_status(request: Request):
    _require_local_sandbox_client(request)
    return sandbox.status()


@router.post("/sandbox/execute")
def sandbox_execute(payload: SandboxExecuteRequest, request: Request):
    _require_local_sandbox_client(request)
    if request.headers.get("x-kavach-sandbox") != "execute":
        raise HTTPException(status_code=403, detail="The sandbox execution header is required.")
    try:
        result = sandbox.execute(payload.code, payload.stdin, payload.timeout_seconds)
    except sandbox.SandboxBusy as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except sandbox.SandboxUnavailable as exc:
        write_audit("sandbox.execute", detail=str(exc), outcome="error")
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    write_audit("sandbox.execute", detail=f"job={result['job_id']}; sha256={result['code_sha256']}; "
                f"status={result['status']}; exit={result['exit_code']}; ms={result['duration_ms']}",
                outcome="ok" if result["status"] == "completed" else result["status"])
    return result


# --- Documents ----------------------------------------------------------------
@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    data = await file.read(config.MAX_UPLOAD_BYTES + 1)
    try:
        safe_name, ext = validate_upload(file.filename or "upload", len(data))
        target = safe_join(config.UPLOADS_DIR, safe_name)
    except ValidationError as exc:
        write_audit("document.upload", detail=str(exc), outcome="rejected")
        raise HTTPException(status_code=400, detail=str(exc))

    config.ensure_dirs()
    # Reserve the filename atomically, including concurrent uploads.
    stem, suffix, n = target.stem, target.suffix, 1
    while True:
        try:
            with target.open("xb") as fh:
                fh.write(data)
            break
        except FileExistsError:
            target = target.with_name(f"{stem}_{n}{suffix}")
            n += 1
    safe_name = target.name

    doc_id = db.insert("documents", {
        "name": safe_name,
        "filename": safe_name,
        "path": str(target),
        "doc_type": ext,
        "size_bytes": len(data),
        "pages": 0,
        "status": "uploaded",
        "summary": f"User-uploaded {ext} document.",
        "created_at": _now(),
    })
    write_audit("document.upload", detail=f"stored {safe_name} ({len(data)} bytes)")
    return db.fetch_one("SELECT * FROM documents WHERE id=?", (doc_id,))


@router.get("/documents")
def list_documents():
    return db.fetch_all("SELECT * FROM documents WHERE retired_sample=0 "
                        "ORDER BY id")


@router.get("/documents/{doc_id}")
def get_document(doc_id: int):
    return document_store.get_document(doc_id)


@router.get("/documents/{doc_id}/content")
def document_content(doc_id: int, download: bool = False):
    document, path, media_type = document_store.source_file(doc_id)
    write_audit("document.download" if download else "document.open", detail=f"document={doc_id}; filename={document['filename']}")
    return FileResponse(path, media_type=media_type, filename=document["filename"],
                        content_disposition_type="attachment" if download else "inline",
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})


@router.get("/documents/{doc_id}/preview")
def document_preview(doc_id: int):
    preview = document_store.preview_document(doc_id)
    write_audit("document.open", detail=f"document={doc_id}; {preview['kind']} preview")
    return preview


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int):
    return document_store.delete_document(doc_id)


@router.post("/documents/{doc_id}/passage")
def document_passage(doc_id: int, payload: PassageRequest):
    return evidence_preview.passage(doc_id, payload)


@router.get("/documents/{doc_id}/pages/{page_number}/image")
def document_page_image(doc_id: int, page_number: int):
    return Response(evidence_preview.page_image(doc_id, page_number), media_type="image/png",
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/evidence/{evidence_id}/preview")
def evidence_source(evidence_id: int):
    return evidence_preview.for_evidence(evidence_id)


@router.post("/documents/{doc_id}/analyze")
def analyze_document(doc_id: int, payload: DocumentAnalysisRequest):
    try:
        return analysis_service.analyze_document(doc_id, payload)
    except analysis_service.DocumentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except analysis_service.InvalidProfile as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# --- Tasks --------------------------------------------------------------------
@router.post("/tasks")
def create_task(payload: TaskCreate):
    if payload.document_id is None:
        raise HTTPException(status_code=422, detail="document_id is required; upload a source document first.")
    result = analyze_document(payload.document_id, DocumentAnalysisRequest(
        title=payload.title, description=payload.description, task_type=payload.task_type))
    return {**result, "run_id": result["run"]["run"]["id"]}


@router.get("/tasks/{task_id}")
def get_task(task_id: int):
    task = db.fetch_one("SELECT * FROM tasks WHERE id=?", (task_id,))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    run = orchestrator.get_run(task["run_id"]) if task["run_id"] else None
    return {"task": task, "run": run}


# --- Agentic planner ----------------------------------------------------------
@router.get("/agent/tools")
def agent_tools():
    """The fixed tool allowlist available to the planner."""
    return {"tools": REGISTRY.describe(), "actions": list(planner_agent.ACTIONS)}


@router.post("/agent/run")
def agent_run(payload: AgentRunRequest):
    """Run the bounded planner loop for a free-text task."""
    task = payload.task.strip()
    if not task:
        raise HTTPException(status_code=422, detail="Task must not be blank.")
    document = db.fetch_one("SELECT * FROM documents WHERE id=? AND retired_sample=0", (payload.document_id,))
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        get_profile(payload.profile)
    except KeyError:
        raise HTTPException(status_code=422, detail="Unknown analysis profile")
    run = planner_agent.run_agentic(task, max_steps=payload.max_steps, document=document,
                                   profile=payload.profile, analysis_mode=payload.analysis_mode)
    plan = run["planner"]
    write_audit("agent.run",
                detail=f"run {run['run']['id']}: {plan['steps_used']} step(s), "
                       f"stop={plan['stop_reason']}, status={run['run']['status']}")
    return run


# --- Agent runs ---------------------------------------------------------------
@router.post("/analysis/jobs", status_code=202)
def create_analysis_job(payload: AnalysisJobRequest):
    try:
        return analysis_jobs.submit(payload)
    except analysis_service.DocumentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except analysis_service.InvalidProfile as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except analysis_jobs.JobCapacityError as exc:
        raise HTTPException(status_code=429, detail=str(exc))


@router.get("/analysis/jobs/{job_id}")
def analysis_job(job_id: str):
    job = analysis_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    return job


@router.post("/analysis/batches", status_code=202)
def create_analysis_batch(payload: BatchAnalysisRequest):
    try:
        return batch_jobs.submit(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except analysis_jobs.JobCapacityError as exc:
        raise HTTPException(status_code=429, detail=str(exc))


@router.get("/analysis/batches")
def list_analysis_batches():
    return batch_jobs.recent()


@router.get("/analysis/batches/{batch_id}")
def analysis_batch(batch_id: str):
    batch = batch_jobs.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Analysis batch not found")
    return batch


@router.post("/chat")
def chat_with_documents(payload: DocumentChatRequest):
    try:
        return document_chat.answer(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/agents/runs")
def list_runs():
    return orchestrator.list_runs()


@router.get("/agents/runs/{run_id}")
def get_run(run_id: int):
    run = orchestrator.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


# --- Models -------------------------------------------------------------------
@router.get("/profiles")
def analysis_profiles():
    return {"profiles": list_profiles(), "analysis_modes": list(ANALYSIS_MODES)}


@router.get("/models")
def list_models():
    models = db.fetch_all("SELECT * FROM models ORDER BY id")
    providers = {name: p.health() for name, p in all_providers().items()}
    return {
        "models": models,
        "routing_rules": routing_rules(),
        "providers": providers,
        "active_provider": active_provider_name(),
    }


# --- Knowledge ----------------------------------------------------------------
@router.get("/knowledge")
def knowledge():
    return knowledge_service.stats()


@router.post("/knowledge/search", response_model=KnowledgeSearchResponse)
def knowledge_search(payload: KnowledgeSearchRequest):
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Query must not be blank.")
    kb = knowledge_service.get_kb()
    # Drop non-positive similarity: those chunks share nothing with the query.
    results = [r for r in kb.search(query, top_k=payload.top_k) if r["score"] > 0]
    stats = kb.stats()
    write_audit("knowledge.search", detail=f"{len(results)} chunk(s) for '{query[:80]}'")
    return KnowledgeSearchResponse(
        query=query,
        results=results,
        total_chunks=stats["total_chunks"],
        embedding_backend=stats["backend"]["embedding_backend"],
    )


# --- Audit logs ---------------------------------------------------------------
@router.get("/audit-logs")
def audit_logs(limit: int = 100):
    limit = max(1, min(limit, 1000))
    return db.fetch_all("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))


# --- Review -------------------------------------------------------------------
def _review(finding_id: int, decision: str, payload: ReviewRequest | None):
    finding = db.fetch_one("SELECT * FROM findings WHERE id=?", (finding_id,))
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    reviewer = (payload.reviewer if payload else None) or "reviewer@kavach.local"
    note = (payload.note if payload else "") or ""
    db.insert("reviews", {
        "finding_id": finding_id,
        "decision": decision,
        "reviewer": reviewer,
        "note": note,
        "created_at": _now(),
    })
    db.execute("UPDATE findings SET review_status=? WHERE id=?", (decision, finding_id))
    write_audit(f"review.{decision}", actor=reviewer,
                detail=f"finding {finding_id}: {note}")
    # An agentic run held for approval completes once every flagged finding is decided.
    run_id = finding["run_id"]
    pending = db.fetch_one(
        "SELECT COUNT(*) AS n FROM findings WHERE run_id=? AND needs_review=1 "
        "AND review_status='pending'", (run_id,))
    if pending and pending["n"] == 0:
        db.execute("UPDATE agent_runs SET status='completed' WHERE id=? "
                   "AND status='awaiting_review'", (run_id,))
        db.execute("UPDATE tasks SET status='completed' WHERE run_id=? "
                   "AND status='awaiting_review'", (run_id,))
    return db.fetch_one("SELECT * FROM findings WHERE id=?", (finding_id,))


@router.post("/review/{finding_id}/approve")
def approve_finding(finding_id: int, payload: ReviewRequest | None = None):
    return {"ok": True, "finding": _review(finding_id, "approved", payload)}


@router.post("/review/{finding_id}/reject")
def reject_finding(finding_id: int, payload: ReviewRequest | None = None):
    return {"ok": True, "finding": _review(finding_id, "rejected", payload)}


# --- Deliverables -------------------------------------------------------------
@router.get("/deliverables")
def list_deliverables():
    return {
        "deliverables": db.fetch_all(
            "SELECT d.* FROM deliverables d LEFT JOIN agent_runs r ON r.id=d.run_id "
            "WHERE COALESCE(r.retired_sample, 0)=0 ORDER BY d.id DESC"),
        "optional_formats": optional_formats(),
    }


@router.get("/deliverables/{deliverable_id}/download")
def download_deliverable(deliverable_id: int):
    d = db.fetch_one("SELECT * FROM deliverables WHERE id=?", (deliverable_id,))
    if not d:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    if not os.path.exists(d["path"]):
        raise HTTPException(status_code=410, detail="Deliverable file missing on disk")
    write_audit("deliverable.download", detail=f"id={deliverable_id} {d['filename']}")
    return FileResponse(d["path"], filename=d["filename"])
