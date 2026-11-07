"""Durable batches feed the existing bounded analysis queue without bypassing it."""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
import logging
import threading
import uuid

from ..database import db
from ..domains.profiles import get_profile
from ..schemas.schemas import AnalysisJobRequest, BatchAnalysisRequest
from ..security.middleware import write_audit
from . import analysis_jobs
from .document_store import DocumentBusy, DocumentNotFound, use_document

_lock = threading.Lock()
_stop = threading.Event()
_thread: threading.Thread | None = None
_logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc).isoformat()


def submit(payload: BatchAnalysisRequest) -> dict:
    ids = payload.document_ids
    if any(i < 1 for i in ids) or len(ids) != len(set(ids)) or not payload.description.strip():
        raise ValueError("Choose distinct stored documents and a non-empty analysis request.")
    try:
        get_profile(payload.profile)
    except KeyError as exc:
        raise ValueError("Unknown analysis profile") from exc
    batch_id = payload.request_id or uuid.uuid4().hex
    request = payload.model_dump(exclude={"request_id"})
    # Pin every source through durable batch admission; deletion checks the items afterwards.
    with ExitStack() as sources:
        documents = [sources.enter_context(use_document(i)) for i in ids]
        with db.db_cursor() as cur:
            cur.execute("BEGIN IMMEDIATE")
            cur.execute("SELECT request_json FROM analysis_batches WHERE id=?", (batch_id,))
            existing = cur.fetchone()
            if existing:
                if db.loads(existing["request_json"]) != request:
                    raise DocumentBusy("This request identifier was already used for a different batch.")
            else:
                cur.execute("SELECT COUNT(*) AS n FROM analysis_batches WHERE status IN ('queued', 'running')")
                if cur.fetchone()["n"] >= 3:
                    raise analysis_jobs.JobCapacityError("Three batches are already active. Wait for a batch to finish.")
                cur.execute("INSERT INTO analysis_batches VALUES (?, 'queued', ?, ?, ?)",
                            (batch_id, db.dumps(request), _now(), _now()))
                cur.executemany("INSERT INTO analysis_batch_items (batch_id, document_id, filename, job_id) VALUES (?, ?, ?, ?)",
                                [(batch_id, d["id"], d["filename"], uuid.uuid4().hex) for d in documents])
    start()
    write_audit("batch.queued", detail=f"batch={batch_id}; documents={len(ids)}")
    return get(batch_id)


def get(batch_id: str) -> dict | None:
    row = db.fetch_one("SELECT * FROM analysis_batches WHERE id=?", (batch_id,))
    if not row:
        return None
    row["request"] = db.loads(row.pop("request_json"))
    row["items"] = db.fetch_all(
        "SELECT i.id, i.batch_id, i.document_id, i.filename, i.job_id, j.run_id, "
        "COALESCE(j.status, i.status) AS status, COALESCE(j.error, i.error) AS error "
        "FROM analysis_batch_items i LEFT JOIN analysis_jobs j ON j.id=i.job_id WHERE batch_id=? ORDER BY i.id", (batch_id,))
    counts = {key: sum(item["status"] == key for item in row["items"])
              for key in ("pending", "queued", "running", "completed", "error")}
    row["counts"] = {**counts, "total": len(row["items"])}
    return row


def recent() -> list[dict]:
    return [get(row["id"]) for row in db.fetch_all("SELECT id FROM analysis_batches ORDER BY created_at DESC LIMIT 20")]


def tick():
    for batch in db.fetch_all("SELECT * FROM analysis_batches WHERE status IN ('queued', 'running') ORDER BY created_at"):
        request = db.loads(batch["request_json"])
        for item in db.fetch_all("SELECT * FROM analysis_batch_items WHERE batch_id=? ORDER BY id", (batch["id"],)):
            if _stop.is_set():
                return
            job = db.fetch_one("SELECT status, error FROM analysis_jobs WHERE id=?", (item["job_id"],))
            if job:
                db.execute("UPDATE analysis_batch_items SET status=?, error=? WHERE id=?", (job["status"], job["error"], item["id"]))
            elif item["status"] == "pending":
                try:
                    analysis_jobs.submit(AnalysisJobRequest(
                        document_id=item["document_id"], profile=request["profile"], analysis_mode=request["analysis_mode"],
                        title=f"Batch analysis: {item['filename']}"[:300], description=request["description"]), job_id=item["job_id"])
                    db.execute("UPDATE analysis_batch_items SET status='queued' WHERE id=?", (item["id"],))
                except analysis_jobs.JobCapacityError:
                    break
                except (DocumentNotFound, ValueError) as exc:
                    db.execute("UPDATE analysis_batch_items SET status='error', error=? WHERE id=?", (str(exc), item["id"]))
        items = db.fetch_all("SELECT status FROM analysis_batch_items WHERE batch_id=?", (batch["id"],))
        done = all(i["status"] in {"completed", "error"} for i in items)
        status = ("completed_with_errors" if any(i["status"] == "error" for i in items) else "completed") if done else "running"
        db.execute("UPDATE analysis_batches SET status=?, updated_at=? WHERE id=?", (status, _now(), batch["id"]))


def _loop():
    while not _stop.is_set():
        try:
            tick()
        except Exception:
            _logger.exception("Batch scheduling failed; durable items remain available for the next attempt")
        _stop.wait(0.5)


def start():
    global _thread
    with _lock:
        if _thread and _thread.is_alive():
            return
        _stop.clear()
        _thread = threading.Thread(target=_loop, name="kavach-batches", daemon=True)
        _thread.start()


def shutdown():
    global _thread
    with _lock:
        _stop.set()
        thread, _thread = _thread, None
    if thread:
        thread.join()
