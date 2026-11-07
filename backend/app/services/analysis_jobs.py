"""Bounded local analysis jobs with durable, operation-driven progress."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import threading
import uuid

from ..agents import orchestrator, planner_agent
from ..agents.progress import STAGES
from ..database import db
from ..domains.profiles import get_profile
from ..schemas.schemas import AnalysisJobRequest
from ..security.middleware import write_audit
from . import analysis
from .document_store import use_document

_lock = threading.Lock()
_executor: ThreadPoolExecutor | None = None
_capacity = threading.BoundedSemaphore(4)


class JobCapacityError(RuntimeError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


def _stages():
    return [{"id": key, "label": label, "description": description, "status": "pending",
             "message": "", "detail": "", "started_at": None, "finished_at": None,
             "metadata": {}, "events": []} for key, label, description in STAGES]


def submit(payload: AnalysisJobRequest, *, job_id: str | None = None) -> dict:
    with use_document(payload.document_id):
        return _submit(payload, job_id=job_id)


def _submit(payload: AnalysisJobRequest, *, job_id: str | None = None) -> dict:
    global _executor
    document = db.fetch_one("SELECT * FROM documents WHERE id=? AND retired_sample=0", (payload.document_id,))
    if not document:
        raise analysis.DocumentNotFound("Document not found")
    try:
        get_profile(payload.profile)
    except KeyError:
        raise analysis.InvalidProfile("Unknown analysis profile")
    if not _capacity.acquire(blocking=False):
        raise JobCapacityError("The local analysis queue is full. Try again after a current job finishes.")
    job_id = job_id or uuid.uuid4().hex
    try:
        with _lock:
            if _executor is None:
                _executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="kavach-analysis")
            db.insert("analysis_jobs", {
                "id": job_id, "document_id": payload.document_id, "status": "queued",
                "request_json": db.dumps(payload.model_dump()), "stages_json": db.dumps(_stages()),
                "created_at": _now(), "updated_at": _now(),
            })
            _executor.submit(_work, job_id, payload)
    except Exception:
        _capacity.release()
        raise
    write_audit("analysis.queued", detail=f"job={job_id}; document={payload.document_id}; workflow={payload.workflow}")
    return get(job_id)


def _work(job_id: str, payload: AnalysisJobRequest):
    stages = _stages()
    run_id = None

    def report(event):
        nonlocal run_id
        if event["type"] == "run":
            run_id = event["run_id"]
            db.execute("UPDATE analysis_jobs SET run_id=?, updated_at=? WHERE id=?", (run_id, _now(), job_id))
            return
        stage = next((s for s in stages if s["id"] == event.get("stage")), None)
        if not stage:
            return
        now = _now()
        state = event.get("state", "running")
        if event["type"] == "stage":
            stage["status"] = state
            stage["metadata"].update(event.get("metadata", {}))
            if state == "running":
                if not stage["started_at"]:
                    stage["started_at"] = now
                stage["finished_at"] = None
            else:
                stage["finished_at"] = now
        stage["message"] = event.get("message", "")
        stage["detail"] = event.get("detail", "")
        entry = {"at": now, "status": state, "message": stage["message"], "detail": stage["detail"]}
        stage["events"] = [*stage["events"][-7:], entry]
        db.execute("UPDATE analysis_jobs SET stages_json=?, updated_at=? WHERE id=?", (db.dumps(stages), now, job_id))

    try:
        db.execute("UPDATE analysis_jobs SET status='running', updated_at=? WHERE id=?", (_now(), job_id))
        if payload.workflow == "planner":
            document = db.fetch_one("SELECT * FROM documents WHERE id=?", (payload.document_id,))
            if not document:
                raise analysis.DocumentNotFound("Document not found")
            run = planner_agent.run_agentic(payload.description or payload.title, max_steps=payload.max_steps,
                                            document=document, profile=payload.profile,
                                            analysis_mode=payload.analysis_mode, on_progress=report)
            result = {"document": db.fetch_one("SELECT * FROM documents WHERE id=?", (payload.document_id,)), "run": run}
        else:
            result = analysis.analyze_document(payload.document_id, payload, on_progress=report)
        for stage in stages:
            if stage["status"] == "pending":
                stage.update(status="not_run" if result["run"]["run"]["status"] == "halted" else "skipped",
                             message="Not used by this analysis", finished_at=_now())
        db.execute("UPDATE analysis_jobs SET status='completed', result_json=?, stages_json=?, updated_at=? WHERE id=?",
                   (db.dumps(result), db.dumps(stages), _now(), job_id))
        write_audit("analysis.completed", detail=f"job={job_id}; run={run_id}")
    except Exception as exc:
        for stage in stages:
            if stage["status"] == "running":
                stage.update(status="error", message="Stage failed", detail=str(exc), finished_at=_now())
            elif stage["status"] == "pending":
                stage.update(status="not_run")
        db.execute("UPDATE analysis_jobs SET status='error', error=?, stages_json=?, updated_at=? WHERE id=?",
                   (str(exc), db.dumps(stages), _now(), job_id))
        if run_id:
            db.execute("UPDATE agent_runs SET status='error', finished_at=? WHERE id=? AND status='running'", (_now(), run_id))
            db.execute("UPDATE tasks SET status='error' WHERE status='running' AND "
                       "(run_id=? OR id IN (SELECT task_id FROM agent_runs WHERE id=?))", (run_id, run_id))
        write_audit("analysis.failed", detail=f"job={job_id}; {exc}", outcome="error")
    finally:
        _capacity.release()


def get(job_id: str) -> dict | None:
    row = db.fetch_one("SELECT * FROM analysis_jobs WHERE id=?", (job_id,))
    if not row:
        return None
    row["request"] = db.loads(row.pop("request_json"))
    row["stages"] = db.loads(row.pop("stages_json"))
    row["result"] = db.loads(row.pop("result_json"))
    row["document"] = db.fetch_one("SELECT id, filename FROM documents WHERE id=?", (row["document_id"],))
    # Review decisions can change after the job finished; return current run data.
    if row["result"] and row["run_id"]:
        current = orchestrator.get_run(row["run_id"])
        if current:
            row["result"]["run"].update(current)
    return row


def recover_interrupted():
    """A restarted process cannot resume inference; preserve the trace and mark the interruption."""
    for row in db.fetch_all("SELECT id, stages_json, run_id FROM analysis_jobs WHERE status IN ('queued', 'running')"):
        stages = db.loads(row["stages_json"])
        for stage in stages:
            if stage["status"] == "running":
                stage.update(status="error", message="Backend restarted during this stage", finished_at=_now())
            elif stage["status"] == "pending":
                stage.update(status="not_run")
        db.execute("UPDATE analysis_jobs SET status='error', error=?, stages_json=?, updated_at=? WHERE id=?",
                   ("The backend restarted before this analysis finished. Start a new analysis to retry.",
                    db.dumps(stages), _now(), row["id"]))
        if row["run_id"]:
            db.execute("UPDATE agent_runs SET status='error', finished_at=? WHERE id=? AND status='running'",
                       (_now(), row["run_id"]))
            db.execute("UPDATE tasks SET status='error' WHERE status='running' AND "
                       "(run_id=? OR id IN (SELECT task_id FROM agent_runs WHERE id=?))", (row["run_id"], row["run_id"]))


def shutdown():
    global _executor
    with _lock:
        executor, _executor = _executor, None
    if executor:
        # Finish admitted work so progress and the final result are saved on a normal shutdown.
        executor.shutdown(wait=True)
