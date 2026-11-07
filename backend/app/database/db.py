"""SQLite persistence layer for KAVACH AI.

Uses the stdlib ``sqlite3`` only (no ORM dependency required) so the backend
starts with zero optional packages. Connections are per-call, row_factory set to
``sqlite3.Row`` for dict-like access. Thread-safe for FastAPI's threadpool via
``check_same_thread=False`` plus short-lived connections.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterable

from ..config import DB_PATH

_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    filename TEXT NOT NULL,
    path TEXT NOT NULL,
    doc_type TEXT,
    size_bytes INTEGER DEFAULT 0,
    pages INTEGER DEFAULT 0,
    extraction_method TEXT DEFAULT '',
    ocr_pages INTEGER DEFAULT 0,
    status TEXT DEFAULT 'ready',
    summary TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    task_type TEXT,
    status TEXT DEFAULT 'created',
    run_id INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    scenario TEXT,
    status TEXT DEFAULT 'running',
    verification_score REAL DEFAULT 0,
    evidence_backed TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS agent_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    seq INTEGER NOT NULL,
    agent TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT DEFAULT 'completed',
    detail TEXT,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    title TEXT NOT NULL,
    description TEXT,
    severity TEXT DEFAULT 'medium',
    confidence REAL DEFAULT 0,
    equipment_id TEXT,
    needs_review INTEGER DEFAULT 0,
    review_reasons_json TEXT,
    review_status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id INTEGER,
    run_id INTEGER,
    source TEXT NOT NULL,
    page INTEGER,
    excerpt TEXT,
    location_json TEXT,
    extraction_method TEXT,
    ocr_confidence REAL,
    confidence REAL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    provider TEXT,
    kind TEXT,
    status TEXT DEFAULT 'online',
    params TEXT,
    routing_rule TEXT,
    vram_gb REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    actor TEXT,
    detail TEXT,
    mode TEXT,
    outcome TEXT DEFAULT 'ok',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deliverables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    name TEXT NOT NULL,
    filename TEXT NOT NULL,
    path TEXT NOT NULL,
    fmt TEXT,
    size_bytes INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id INTEGER NOT NULL,
    decision TEXT NOT NULL,
    reviewer TEXT,
    note TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis_jobs (
    id TEXT PRIMARY KEY,
    document_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    request_json TEXT NOT NULL,
    stages_json TEXT NOT NULL,
    result_json TEXT,
    error TEXT,
    run_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis_batches (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    request_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS analysis_batch_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL,
    document_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    job_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending',
    error TEXT,
    UNIQUE(batch_id, document_id)
);
CREATE INDEX IF NOT EXISTS batch_items_batch ON analysis_batch_items(batch_id);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def db_cursor():
    """Context manager yielding a cursor and committing on exit."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create tables and add provenance columns to databases from older versions."""
    with _LOCK:
        conn = get_connection()
        try:
            conn.executescript(SCHEMA)
            migrations = {
                "documents": {
                    "extraction_method": "TEXT DEFAULT ''",
                    "ocr_pages": "INTEGER DEFAULT 0",
                    "retired_sample": "INTEGER NOT NULL DEFAULT 0",
                },
                "agent_runs": {
                    "retired_sample": "INTEGER NOT NULL DEFAULT 0",
                    "analysis_json": "TEXT",
                    "vision_json": "TEXT",
                    "extraction_json": "TEXT",
                    "analysis_profile": "TEXT",
                    "analysis_mode": "TEXT",
                },
                "evidence": {
                    "document_id": "INTEGER",
                    "location_json": "TEXT",
                    "extraction_method": "TEXT",
                    "ocr_confidence": "REAL",
                },
                "findings": {
                    "review_reasons_json": "TEXT",
                },
            }
            for table, columns in migrations.items():
                existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
                for column, declaration in columns.items():
                    if column not in existing:
                        conn.execute(
                            f"ALTER TABLE {table} ADD COLUMN {column} {declaration}"
                        )
            conn.commit()
        finally:
            conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def rows_to_list(rows: Iterable[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rows]


def insert(table: str, data: dict[str, Any]) -> int:
    cols = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
    with db_cursor() as cur:
        cur.execute(sql, tuple(data.values()))
        return int(cur.lastrowid)


def fetch_one(sql: str, params: tuple = ()) -> dict | None:
    with db_cursor() as cur:
        cur.execute(sql, params)
        return row_to_dict(cur.fetchone())


def fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    with db_cursor() as cur:
        cur.execute(sql, params)
        return rows_to_list(cur.fetchall())


def execute(sql: str, params: tuple = ()) -> None:
    with db_cursor() as cur:
        cur.execute(sql, params)


def count(table: str) -> int:
    with db_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS c FROM {table}")
        return int(cur.fetchone()["c"])


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def loads(text: str | None) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
