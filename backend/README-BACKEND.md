# KAVACH AI - Backend

Sovereign On-Premise Agentic AI Workbench - Python/FastAPI backend for the
KAVACH AI local-first document intelligence project.

**Runs locally with no cloud AI APIs.** Host-based development defaults to Ollama
with role-specific local models; set `KAVACH_INFERENCE_PROVIDER=mock` for
deterministic model-free runs. Default mode is `airgapped`.

The agents, the agentic planner loop and what is real versus mocked are
explained in the [top-level README](../README.md).

---

## 1. Install

From the `backend/` directory:

```bash
# Core (required) — the app starts with just these:
pip install fastapi "uvicorn[standard]" python-multipart pydantic

# Recommended optional (pure-python-ish, offline friendly):
pip install fpdf2 Pillow

# Optional richer deliverables (guarded; skip if offline install fails):
pip install python-docx openpyxl reportlab pypdf

# --- or everything at once (optional heavy deps commented out in file): ---
pip install -r requirements.txt
```

Every optional dependency is wrapped in `try/except`. If any are missing the app
still starts and degrades gracefully (e.g. PDFs/DOCX/XLSX are skipped, RAG falls
back from Ollama embeddings to Sentence Transformers or a pure-Python hash embedding).

## 2. Generate the sample assets (once)

From the **repo root**:

```bash
python demo-data/generate_demo_data.py
```

Produces under `demo-data/`: `inspection_report.pdf`, `equipment_manual.pdf`,
`engineering_calculation.pdf` (or `.txt` fallbacks if fpdf2 is absent),
`plant_pid.png` (or `.txt` if Pillow is absent), and `sample_internal_code.py`.
All facility and inspection content is **fictional sample data**.

## 3. Run the server

From the `backend/` directory:

```bash
python -m uvicorn app.main:app --reload --port 8000
```

The SQLite DB (`backend/kavach.db`) is auto-created and seeded on first startup.
API docs at http://localhost:8000/docs. CORS is enabled for
`http://localhost:3000` and `http://localhost:3001`.

## 4. Configuration

Copy `.env.example` and adjust as needed. Key variables:

| Variable              | Default      | Purpose                              |
|-----------------------|--------------|--------------------------------------|
| `KAVACH_MODE`         | `airgapped`  | `airgapped` blocks external providers|
| `KAVACH_DB`           | `./kavach.db`| SQLite path                          |
| `KAVACH_MAX_UPLOAD_MB`| `25`         | Upload size cap                      |
| `KAVACH_INFERENCE_PROVIDER` | `ollama` | `ollama` or `mock` (loopback only when airgapped) |
| `OLLAMA_REASONING_MODEL` | `qwen3:8b` | Reasoning model |
| `OLLAMA_VISION_MODEL` | `llava:7b` | Image/P&ID model |
| `OLLAMA_OTHER_MODEL` | `llama3.2:3b` | Other text tasks and planner choices |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text:latest` | Local RAG embeddings |
| `OLLAMA_TIMEOUT_S` | `120` | Per-request Ollama timeout |
| `KAVACH_PLANNER_MAX_STEPS` | `10`    | Default planner step budget (hard cap 20) |
| `KAVACH_REVIEW_MIN_CONFIDENCE` | `75` | Findings below this need human approval |

Tests: `pip install -r requirements-dev.txt && python -m pytest tests -q`.

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET  | `/api/health` | status/mode/version |
| GET  | `/api/system/status` | live GPU/CPU/RAM (labelled fallback) + models/vector-db/ocr/sandbox/network |
| POST | `/api/documents/upload` | multipart upload (validated, path-safe) |
| GET  | `/api/documents` | list documents |
| GET  | `/api/documents/{id}` | document detail |
| POST | `/api/documents/{id}/analyze` | analyze with a selected profile and mode |
| POST | `/api/tasks` | create task + run agent pipeline |
| GET  | `/api/tasks/{task_id}` | task + run |
| POST | `/api/demo/run` | run the fixed sample inspection scenario |
| GET  | `/api/demo/stream` | SSE stream of pipeline steps |
| GET  | `/api/agents/runs` | list runs |
| GET  | `/api/agents/runs/{run_id}` | full trace (steps/findings/evidence) |
| GET  | `/api/models` | models + routing rules + providers |
| GET  | `/api/profiles` | document profiles + analysis modes |
| GET  | `/api/knowledge` | KB stats + sources + sample chunks |
| POST | `/api/knowledge/search` | RAG search (`query`, `top_k` 1-10) |
| GET  | `/api/agent/tools` | planner tool allowlist |
| POST | `/api/agent/run` | bounded agentic planner run (`task`, `max_steps`) |
| GET  | `/api/audit-logs` | audit entries |
| POST | `/api/review/{finding_id}/approve` | approve a finding |
| POST | `/api/review/{finding_id}/reject` | reject a finding |
| GET  | `/api/deliverables` | list generated deliverables |
| GET  | `/api/deliverables/{id}/download` | download a deliverable file |

---

## Architecture

```
app/
  main.py            FastAPI app, CORS, middleware, lifespan (init+seed)
  config.py          env-driven config, paths, policies
  api/routes.py      all HTTP routes
  agents/            security, router, document, vision, knowledge, reasoning,
                     verification, deliverable, planner + orchestrator,
                     tools (planner allowlist), review_gate (human approval)
  domains/           general and industrial analysis profiles
  models/            provider abstraction (Mock/Ollama/vLLM) + role-aware router
  rag/               chunk + embed (Ollama Nomic / Sentence Transformers / hash fallback)
  security/          airgap guard, upload validation, mock sandbox, middleware
  services/          scenario content, knowledge KB, document analysis,
                     deliverables, seed, system status
  database/          sqlite3 layer + schema
  schemas/           pydantic request/response models
```

**Fixed pipeline:** Security -> Router -> Document -> Vision -> Knowledge ->
Reasoning -> Verification -> Deliverable. Each step is persisted with timestamps
and a human-readable message. For an uploaded document, each analysis mode is
driven by extracted source text and source excerpts are re-checked against it.

Uploaded-document analysis accepts `profile` (`general` or `industrial`) and
`analysis_mode` (`risk_review`, `summary`, or `extract_fields`). Risk review
matches the selected profile's vocabulary and verifies source excerpts. Summary
uses the local reasoning model and is advisory. Field extraction returns literal
dates, equipment identifiers, and measurements with source citations. The
general profile is the default; the sample refinery workflow uses the industrial
profile.

**Agentic planner (`/api/agent/run`):** the Planner agent picks the next action
from run state, one allowlisted tool call per step, bounded by a step limit,
loop detection and the human-review gate.

**Model router (deterministic):** task text -> task_type -> configured role model
(`qwen3:8b` reasoning / `llava:7b` vision / `llama3.2:3b` other text tasks).
Knowledge-base embeddings use `nomic-embed-text:latest` when Ollama is active.

The reasoning agent records Qwen3 output as advisory analysis, but the sample
scenario findings remain fixture data. In risk-review mode, uploaded-text findings
remain profile-term extracted. LLaVA responses are recorded for image inputs;
sample P&ID bounding boxes remain fixed fixture coordinates.

**Security:** airgapped mode blocks external cloud providers; uploads are
extension-allowlisted (`pdf,png,jpg,jpeg,txt,docx,csv,py`), size-capped (25 MB)
and filename-sanitized (path-traversal safe, no werkzeug). Every mutating action
is written to `audit_logs`. A mock sandbox returns `ISOLATED` (no real exec).

**Deliverables** are written to `../generated/`. `.txt` and `.md` are always
produced; `.docx`/`.xlsx`/`.pdf` are added when the relevant library is present.
