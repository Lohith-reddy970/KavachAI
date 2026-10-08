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


def run_pipeline(task_text: str, scenario_name: str = "refinery_inspection",
                 task_id: int | None = None, document: dict | None = None,
                 document_text: str = "", document_note: str = "",
                 profile: str = "industrial", analysis_mode: str = "risk_review") -> dict:
    """Execute the full agent pipeline and persist the trace. Returns run dict."""
    # 1) Create the run row up front so agents (deliverables) can reference it.
    run_id = db.insert("agent_runs", {
        "task_id": task_id,
        "scenario": scenario_name,
        "status": "running",
        "verification_score": 0,
        "evidence_backed": "",
        "started_at": _now(),
    })

    ctx = RunContext(task_text=task_text, scenario=scenario_name)
    ctx.artifacts["run_id"] = run_id
    ctx.artifacts["analysis_profile"] = profile
    ctx.artifacts["analysis_mode"] = analysis_mode
    if document:
        ctx.artifacts["document"] = document
        ctx.artifacts["document_text"] = document_text
        ctx.artifacts["document_note"] = document_note

    # 2) Run agents in order.
    for agent in PIPELINE:
        try:
            agent.run(ctx)
        except Exception as exc:  # noqa: BLE001
            ctx.add_step(agent.name, f"{agent.name} failed", status="error",
                         detail=repr(exc))
            db.execute("UPDATE agent_runs SET status=?, finished_at=? WHERE id=?",
                       ("error", _now(), run_id))
            _persist_steps(run_id, ctx)
            raise

    # 3) Persist steps.
    _persist_steps(run_id, ctx)

    # 4-5) Persist findings, evidence and deliverables.
    _persist_results(run_id, ctx)

    # 6) Finalize run. A document run with flagged findings waits for approval,
    #    like an agentic run; the demo scenario keeps its fixed "completed" status.
    held = document and any(f.get("needs_review") for f in ctx.findings)
    _finalize(run_id, ctx, "awaiting_review" if held else "completed")

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
            "review_status": "pending",
            "created_at": _now(),
        })
        finding_ids.append(fid)
        for ev in f.get("evidence", []):
            db.insert("evidence", {
                "finding_id": fid,
                "run_id": run_id,
                "source": ev["source"],
                "page": ev.get("page"),
                "excerpt": ev.get("excerpt", ""),
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
        "finished_at=? WHERE id=?",
        (status, ctx.verification_score, ctx.evidence_backed, _now(), run_id),
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
        f["evidence"] = db.fetch_all(
            "SELECT * FROM evidence WHERE finding_id=? ORDER BY id", (f["id"],))
    evidence = db.fetch_all("SELECT * FROM evidence WHERE run_id=? ORDER BY id",
                            (run_id,))
    deliverables = db.fetch_all(
        "SELECT * FROM deliverables WHERE run_id=? ORDER BY id", (run_id,))
    return {
        "run": run,
        "steps": steps,
        "findings": findings,
        "evidence": evidence,
        "deliverables": deliverables,
    }


def list_runs() -> list[dict]:
    return db.fetch_all("SELECT * FROM agent_runs ORDER BY id DESC")
