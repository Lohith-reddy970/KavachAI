"""All KAVACH AI HTTP routes."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse

from .. import config
from ..agents import orchestrator, planner_agent
from ..agents.tools import REGISTRY
from ..database import db
from ..domains.profiles import ANALYSIS_MODES, get_profile, list_profiles
from ..models.providers import active_provider_name, all_providers
from ..models.router import routing_rules
from ..schemas.schemas import (AgentRunRequest, DemoRunRequest, DocumentAnalysisRequest,
                               HealthResponse, KnowledgeSearchRequest,
                               KnowledgeSearchResponse, ReviewRequest, TaskCreate)
from ..security.guard import ValidationError, safe_join, validate_upload
from ..security.middleware import write_audit
from ..services import document_analysis
from ..services import knowledge as knowledge_service
from ..services import system_status
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


# --- Documents ----------------------------------------------------------------
@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    data = await file.read()
    try:
        safe_name, ext = validate_upload(file.filename or "upload", len(data))
        target = safe_join(config.UPLOADS_DIR, safe_name)
    except ValidationError as exc:
        write_audit("document.upload", detail=str(exc), outcome="rejected")
        raise HTTPException(status_code=400, detail=str(exc))

    config.ensure_dirs()
    # Never overwrite an earlier upload that shares the filename.
    stem, suffix, n = target.stem, target.suffix, 1
    while target.exists():
        target = target.with_name(f"{stem}_{n}{suffix}")
        n += 1
    safe_name = target.name
    with open(target, "wb") as fh:
        fh.write(data)

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
    return db.fetch_all("SELECT * FROM documents ORDER BY id")


@router.get("/documents/{doc_id}")
def get_document(doc_id: int):
    doc = db.fetch_one("SELECT * FROM documents WHERE id=?", (doc_id,))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.post("/documents/{doc_id}/analyze")
def analyze_document(doc_id: int, payload: DocumentAnalysisRequest):
    """Run a profile- and mode-aware analysis on one uploaded document."""
    document = db.fetch_one("SELECT * FROM documents WHERE id=?", (doc_id,))
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        get_profile(payload.profile)
    except KeyError:
        allowed = ", ".join(item["id"] for item in list_profiles())
        raise HTTPException(status_code=422,
                            detail=f"Unknown profile '{payload.profile}'. Available: {allowed}.")
    text, note = document_analysis.extract_text(document["path"])
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
    run = orchestrator.run_pipeline(
        task_text=task_text,
        scenario_name=f"document:{document['filename']}",
        task_id=task_id,
        document=document,
        document_text=text,
        document_note=note,
        profile=payload.profile,
        analysis_mode=payload.analysis_mode,
    )
    db.execute("UPDATE tasks SET status=?, run_id=? WHERE id=?",
               ("completed", run["run"]["id"], task_id))
    write_audit("document.analyze",
                detail=f"document {doc_id} ({document['filename']}) -> run {run['run']['id']}: "
                       f"profile={payload.profile}, mode={payload.analysis_mode}, "
                       f"{len(run['findings'])} finding(s), status={run['run']['status']}")
    return {"task": db.fetch_one("SELECT * FROM tasks WHERE id=?", (task_id,)), "run": run}


# --- Tasks --------------------------------------------------------------------
@router.post("/tasks")
def create_task(payload: TaskCreate):
    from ..models.router import classify

    task_type = payload.task_type or classify(payload.title + " " + (payload.description or ""))
    task_id = db.insert("tasks", {
        "title": payload.title,
        "description": payload.description or "",
        "task_type": task_type,
        "status": "running",
        "run_id": None,
        "created_at": _now(),
    })
    # Kick off the agent run synchronously (mock).
    run = orchestrator.run_pipeline(
        task_text=payload.title + " " + (payload.description or ""),
        scenario_name="refinery_inspection",
        task_id=task_id,
    )
    run_id = run["run"]["id"]
    db.execute("UPDATE tasks SET status=?, run_id=? WHERE id=?",
               ("completed", run_id, task_id))
    write_audit("task.create", detail=f"task {task_id} -> run {run_id}")
    task = db.fetch_one("SELECT * FROM tasks WHERE id=?", (task_id,))
    return {"task": task, "run_id": run_id, "run": run}


@router.get("/tasks/{task_id}")
def get_task(task_id: int):
    task = db.fetch_one("SELECT * FROM tasks WHERE id=?", (task_id,))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    run = orchestrator.get_run(task["run_id"]) if task["run_id"] else None
    return {"task": task, "run": run}


# --- Demo ---------------------------------------------------------------------
@router.post("/demo/run")
def demo_run(payload: DemoRunRequest | None = None):
    scenario_name = (payload.scenario if payload else None) or "refinery_inspection"
    write_audit("demo.run", detail=f"scenario={scenario_name}")
    run = orchestrator.run_pipeline(
        task_text="Inspect Unit 4 P&ID and inspection report for corrosion and integrity issues",
        scenario_name=scenario_name,
    )
    return run


@router.get("/demo/stream")
async def demo_stream():
    """Server-sent events emitting each pipeline step as it 'runs'."""
    async def event_gen():
        # The pipeline is synchronous; run it off the event loop.
        run = await run_in_threadpool(
            orchestrator.run_pipeline,
            task_text="Inspect Unit 4 P&ID and inspection report (streaming demo)",
            scenario_name="refinery_inspection",
        )
        for step in run["steps"]:
            payload = {"agent": step["agent"], "message": step["message"],
                       "status": step["status"], "detail": step["detail"]}
            yield f"event: step\ndata: {json.dumps(payload)}\n\n"
            await asyncio.sleep(0.15)
        summary = {"run_id": run["run"]["id"],
                   "verification_score": run["run"]["verification_score"],
                   "evidence_backed": run["run"]["evidence_backed"],
                   "findings": len(run["findings"]),
                   "deliverables": len(run["deliverables"])}
        yield f"event: complete\ndata: {json.dumps(summary)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


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
    run = planner_agent.run_agentic(task, max_steps=payload.max_steps)
    plan = run["planner"]
    write_audit("agent.run",
                detail=f"run {run['run']['id']}: {plan['steps_used']} step(s), "
                       f"stop={plan['stop_reason']}, status={run['run']['status']}")
    return run


# --- Agent runs ---------------------------------------------------------------
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
        "deliverables": db.fetch_all("SELECT * FROM deliverables ORDER BY id DESC"),
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
