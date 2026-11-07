# KAVACH AI backend

FastAPI, SQLite, local extraction/OCR, Ollama or local Transformers inference, and source-verified document workflows. See the root [README](../README.md) for setup and configuration.

## API

| Method | Endpoint | Behavior |
|---|---|---|
| GET | `/api/health` | Application status and mode |
| GET | `/api/system/status` | Measured hardware readings or null, configured models, local service status |
| GET | `/api/sandbox/status` | Actual local container runtime, image readiness, and execution limits |
| POST | `/api/sandbox/execute` | Explicit isolated Python execution; requires local client and `X-Kavach-Sandbox: execute` |
| GET | `/api/profiles` | Domain profiles and analysis modes |
| POST | `/api/documents/upload` | Validate and store a user file |
| GET | `/api/documents`, `/api/documents/{id}` | Stored document metadata |
| GET | `/api/documents/{id}/preview` | Local viewer metadata or bounded text/DOCX preview; does not start inference |
| GET | `/api/documents/{id}/content` | Original local source, inline with explicit MIME type and PDF byte-range support; `?download=true` downloads it |
| DELETE | `/api/documents/{id}` | Remove source and Vault record; preserve historical runs/reports; HTTP 409 while analysis is queued/running or source removal is blocked |
| POST | `/api/documents/{id}/analyze` | Analyze the selected source using profile and mode |
| POST | `/api/analysis/jobs` | Queue pipeline/planner work; HTTP 202 includes the saved job ID and progress snapshot |
| GET | `/api/analysis/jobs/{id}` | Current real stages, page/OCR updates, activity, error, and final inline result |
| POST | `/api/tasks` | Requires `document_id` and `title`; runs the document pipeline |
| GET | `/api/tasks/{id}` | Task and associated run |
| GET | `/api/agent/tools` | Planner tool allowlist |
| POST | `/api/agent/run` | Requires `document_id` and `task`; optional profile, mode, step limit |
| GET | `/api/agents/runs`, `/api/agents/runs/{id}` | Stored runs and full evidence/trace |
| POST | `/api/review/{id}/approve`, `/api/review/{id}/reject` | Persist a reviewer decision |
| GET | `/api/models` | Configured assignments and provider capabilities |
| GET | `/api/knowledge` | Index built exclusively from stored document text |
| POST | `/api/knowledge/search` | Ranked real passages; empty on an empty index |
| GET | `/api/audit-logs` | Actual local audit events |
| GET | `/api/deliverables`, `/api/deliverables/{id}/download` | Generated reports and files |

`/api/demo/run` and `/api/demo/stream` have been removed. No scenario content is seeded. Invalid providers fail configuration validation. Generation failures become HTTP 503; source-based risk review can continue with a visible advisory-model warning. Unsupported Transformers image requests fail explicitly.

## Runtime data

Database migrations remain additive. `retired_sample` is retained for compatibility with old databases, not as a content source. Use `scripts/remove_legacy_examples.py` once for an existing installation; preview is the default. Actual uploads and audit history are preserved.

The knowledge index is in memory and rebuilds from stored files. Hash retrieval is real lexical matching, not semantic model inference. Select `KAVACH_EMBEDDING_BACKEND=provider` for learned local vectors. Encoder failures never mix vector spaces by switching backends mid-index.

Analysis jobs use a bounded local thread pool (two workers, four admitted jobs), with durable SQLite progress. Workbench polls the same job ID and can reconnect after refresh. Stage transitions come from extraction and agent operations; they use no replay timers or estimated completion percentages. Full model output and extraction metadata are persisted on new runs, rather than being available only as truncated trace text. Use one backend process for this local queue; process restarts mark interrupted jobs as errors while preserving their stage history.

The Python sandbox uses the fixed image under `docker/sandbox/`. It never runs submitted code in the backend's Python process or host shell. Docker/WSL transport settings are operator-controlled; image, mounts, networking, and privilege options cannot be supplied through the API. See the root README for provisioning and real-container tests. Missing engine/image/required kernel controls result in unavailable status and HTTP 503. Concurrency is limited to one job per backend process; additional jobs return HTTP 429. Use one backend worker for this workstation deployment.

## Tests

`python -m pytest -q` covers extraction, OCR provenance, citation checks, review rules, planner bounds, provider behavior, empty installations, persistence, and cleanup. Inference doubles exist only under tests. Real model, browser, Docker, load, and deployment validation are listed in [the acceptance checklist](../post-optimization-testing/CHECKLIST.md).
