"""Agent orchestrator for KAVACH AI.

Wires the pipeline:
    Security -> Router(+Planner) -> Document -> Vision -> Knowledge
             -> Reasoning -> Verification -> Deliverable

Produces a deterministic multi-step run trace and persists everything to SQLite
(agent_runs, agent_steps, findings, evidence, deliverables). Returns a rich dict
describing the full run for the API layer.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..database import db
from .base import RunContext
from .security_agent import SecurityAgent
from .router_agent import RouterAgent
from .document_agent import DocumentAgent
from .vision_agent import VisionAgent
from .knowledge_agent import KnowledgeAgent
from .reasoning_agent import ReasoningAgent
from .verification_agent import VerificationAgent
from .deliverable_agent import DeliverableAgent
from .progress import AGENT_STAGES, ProgressCallback, complete_stage, publish


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


PIPELINE = [
    SecurityAgent(),
    RouterAgent(),
    DocumentAgent(),
    VisionAgent(),
    KnowledgeAgent(),
    ReasoningAgent(),
    VerificationAgent(),
    DeliverableAgent(),
]


def run_pipeline(task_text: str, scenario_name: str = "document",
                 task_id: int | None = None, document: dict | None = None,
                 document_text: str = "", document_note: str = "",
                 profile: str = "general", analysis_mode: str = "risk_review",
                 document_pages: list | None = None,
                 document_extraction: dict | None = None,
                 on_progress: ProgressCallback | None = None) -> dict:
    """Execute the full agent pipeline and persist the trace. Returns run dict."""
    if not document:
        raise ValueError("A stored document is required for analysis.")
    # 1) Create the run row up front so agents (deliverables) can reference it.
    run_id = db.insert("agent_runs", {
        "task_id": task_id,
        "scenario": scenario_name,
        "status": "running",
        "verification_score": 0,
        "evidence_backed": "",
        "started_at": _now(),
    })

    ctx = RunContext(task_text=task_text, scenario=scenario_name, on_progress=on_progress)
    if on_progress:
        on_progress({"type": "run", "run_id": run_id})
    ctx.artifacts["run_id"] = run_id
    ctx.artifacts["analysis_profile"] = profile
    ctx.artifacts["analysis_mode"] = analysis_mode
    if document:
        ctx.artifacts["document"] = document
        ctx.artifacts["document_text"] = document_text
        ctx.artifacts["document_note"] = document_note
        ctx.artifacts["document_pages"] = document_pages or []
        ctx.artifacts["document_extraction"] = document_extraction or {}

    # 2) Run agents in order.
    current_stage = ""
    stage_start = 0
    for agent in PIPELINE:
        stage = AGENT_STAGES[agent.name]
        if stage != current_stage:
            if current_stage:
                complete_stage(on_progress, current_stage, ctx.steps[stage_start:])
            current_stage, stage_start = stage, len(ctx.steps)
            publish(on_progress, stage, "running", f"Starting {stage} stage")
        try:
            agent.run(ctx)
        except Exception as exc:  # noqa: BLE001
            ctx.add_step(agent.name, f"{agent.name} failed", status="error",
                         detail=repr(exc))
            db.execute("UPDATE agent_runs SET status=?, finished_at=? WHERE id=?",
                       ("error", _now(), run_id))
            _persist_steps(run_id, ctx)
            publish(on_progress, stage, "error", f"{agent.name} failed", str(exc))
            raise

    # 3) Persist steps.
    _persist_steps(run_id, ctx)

    # 4-5) Persist findings, evidence and deliverables.
    _persist_results(run_id, ctx)

    # Findings requiring a decision hold the run for human review.
    held = any(f.get("needs_review") for f in ctx.findings)
    _finalize(run_id, ctx, "awaiting_review" if held else "completed")
    complete_stage(on_progress, current_stage, ctx.steps[stage_start:])

    return get_run(run_id)


def _persist_results(run_id: int, ctx: RunContext) -> None:
    """Persist findings, their evidence and any deliverables for a run."""
    finding_ids: list[int] = []
    for f in ctx.findings:
        fid = db.insert("findings", {
            "run_id": run_id,
            "title": f["title"],
            "description": f["description"],
            "severity": f["severity"],
            "confidence": f["confidence"],
            "equipment_id": f["equipment_id"],
            "needs_review": f["needs_review"],
            "review_reasons_json": db.dumps(f.get("review_reasons", [])),
            "review_status": "pending",
            "created_at": _now(),
        })
        finding_ids.append(fid)
        for ev in f.get("evidence", []):
            db.insert("evidence", {
                "document_id": ctx.artifacts.get("document", {}).get("id"),
                "finding_id": fid,
                "run_id": run_id,
                "source": ev["source"],
                "page": ev.get("page"),
                "excerpt": ev.get("excerpt", ""),
                "location_json": db.dumps(ev["location"]) if ev.get("location") else None,
                "extraction_method": ev.get("extraction_method", ""),
                "ocr_confidence": ev.get("ocr_confidence"),
                "confidence": ev.get("confidence", 0),
                "created_at": _now(),
            })

    for d in ctx.artifacts.get("deliverables", []):
        db.insert("deliverables", {
            "run_id": run_id,
            "name": d["name"],
            "filename": d["filename"],
            "path": d["path"],
            "fmt": d["fmt"],
            "size_bytes": d.get("size_bytes", 0),
            "created_at": _now(),
        })


def _finalize(run_id: int, ctx: RunContext, status: str) -> None:
    db.execute(
        "UPDATE agent_runs SET status=?, verification_score=?, evidence_backed=?, "
        "finished_at=?, analysis_json=?, vision_json=?, extraction_json=?, analysis_profile=?, analysis_mode=? WHERE id=?",
        (status, ctx.verification_score, ctx.evidence_backed, _now(),
         db.dumps(ctx.artifacts.get("reasoning_analysis")),
         db.dumps(ctx.artifacts.get("vision_result")),
         db.dumps(ctx.artifacts.get("document_extraction")),
         ctx.artifacts.get("analysis_profile", "general"),
         ctx.artifacts.get("analysis_mode", "risk_review"), run_id),
    )


def _persist_steps(run_id: int, ctx: RunContext) -> None:
    for seq, step in enumerate(ctx.steps, start=1):
        db.insert("agent_steps", {
            "run_id": run_id,
            "seq": seq,
            "agent": step.agent,
            "message": step.message,
            "status": step.status,
            "detail": step.detail,
            "started_at": step.started_at,
            "finished_at": step.finished_at,
        })


def get_run(run_id: int) -> dict | None:
    """Assemble the full run trace from the DB."""
    run = db.fetch_one("SELECT * FROM agent_runs WHERE id=?", (run_id,))
    if not run:
        return None
    steps = db.fetch_all("SELECT * FROM agent_steps WHERE run_id=? ORDER BY seq",
                         (run_id,))
    findings = db.fetch_all("SELECT * FROM findings WHERE run_id=? ORDER BY id",
                            (run_id,))
    for f in findings:
        f["review_reasons"] = db.loads(f.pop("review_reasons_json", None)) or []
        f["evidence"] = db.fetch_all(
            "SELECT * FROM evidence WHERE finding_id=? ORDER BY id", (f["id"],))
        for ev in f["evidence"]:
            ev["location"] = db.loads(ev.pop("location_json", None))
    evidence = db.fetch_all("SELECT * FROM evidence WHERE run_id=? ORDER BY id",
                            (run_id,))
    for ev in evidence:
        ev["location"] = db.loads(ev.pop("location_json", None))
    deliverables = db.fetch_all(
        "SELECT * FROM deliverables WHERE run_id=? ORDER BY id", (run_id,))
    return {
        "run": run,
        "steps": steps,
        "findings": findings,
        "evidence": evidence,
        "deliverables": deliverables,
        "analysis": db.loads(run.pop("analysis_json", None)),
        "vision": db.loads(run.pop("vision_json", None)),
        "extraction": db.loads(run.pop("extraction_json", None)),
    }


def list_runs() -> list[dict]:
    return db.fetch_all("SELECT * FROM agent_runs WHERE retired_sample=0 ORDER BY id DESC")
