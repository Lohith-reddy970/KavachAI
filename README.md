# KAVACH AI

Private document analysis using local extraction, OCR, model inference, source citations, human review, and report generation.

## Run locally

Use Python 3.10+, Node.js 18+, and a local Ollama runtime. Install the Tesseract executable for scanned PDFs and images. Provision the configured models before requesting summaries or planner choices:

```sh
ollama pull qwen3:8b
ollama pull llava:7b
ollama pull llama3.2:3b
```

From `backend/`:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

From `frontend/`, in a second terminal:

```sh
npm ci
npm run dev
```

Open http://localhost:3000. Upload a document in **Document Vault**, then choose a profile and analysis mode in **Workbench**. **Agent Runs** shows source excerpts, traces, and review decisions; **Deliverables** lists actual generated files. **Knowledge Base** indexes readable text from stored user documents and refreshes after changes.

**Highlighted evidence:** select **View highlighted source** beside a finding or a chat citation. The viewer verifies the excerpt against the current source, highlights the extracted text, and overlays available text/OCR locations on rendered PDF or image pages. Word and plain-text sources use extracted text sections. Deleted or changed sources return an explicit error; older findings without a stored document link need a new analysis.

**Batch processing:** select up to 50 files in the Vault upload control. Each file has its own upload result; successful files are selected for analysis. Choose the shared profile and mode, then click **Analyze selected**. A batch feeds the existing four-slot, two-worker analysis queue and records a separate run and reports for every document. Three batches can be active at once. Progress and failures survive browser refreshes; pending items resume on backend restart, while admitted analyses interrupted by the restart are marked as errors. Sources belonging to unfinished batches cannot be deleted.

**Document Chat:** open the sidebar entry, select up to 20 stored documents, and ask a question or follow-up. Retrieval is restricted to the selected documents and generation uses the configured local reasoning model. Each displayed answer paragraph must include known source markers; missing or invalid markers produce an insufficient-evidence response. Citation presence is not factual verification: review the source before acting. Chat reads extracted text, requires local OCR for scans, admits one generation at a time, and keeps conversation history only in the current browser tab. Changing sources starts a new conversation. An unavailable model produces an explicit error.

To check all three features against the actual local reasoning model with isolated test documents and storage, run `python backend/scripts/verify_document_features.py`. It preserves its results under `tmp/document-features-*` and never reads the user Vault.

In **Document Vault**, click a filename or **Open** to view a local PDF, image, or text preview and download the original. DOCX previews include paragraphs and tables; use the original for formatting and embedded images. **Delete** opens a confirmation before removing the uploaded source and excluding it from future knowledge searches. Existing analysis history and reports are retained. Deletion is blocked while that document has a queued or running analysis.

Workbench shows an operation-driven flow while analysis runs: document checks, text/OCR extraction, planning, image handling, retrieval, reasoning, source verification, and report saving. Select a stage to inspect its real activity. When finished, full model output, source matches/fields, review controls, and downloads appear directly below the flow. Browser refreshes reconnect to the saved job rather than starting another analysis.

Analysis jobs and progress are persisted in SQLite. Two local workers process up to four admitted jobs; a full queue returns HTTP 429. Run a single backend process for this local workstation setup. Normal shutdown finishes admitted jobs; an interrupted process is reported clearly after restart, and the unfinished analysis can be retried explicitly.

Configuration is documented in [.env.example](.env.example). Settings are read from the process environment. To load a copied environment file, start uvicorn with `--env-file ../.env` from `backend/`. Set `NEXT_PUBLIC_API_BASE` before building the frontend.

## Processing behavior

- **Risk review:** matches profile vocabulary in the supplied text and verifies cited excerpts. Model reasoning is advisory; if unavailable, a warning is recorded and source-based review continues.
- **Summary:** uses the configured local text or vision model. Failed inference returns HTTP 503 and an error run, without a substitute result.
- **Extract fields:** extracts literal dates, amounts, contacts, owners, identifiers, and measurements with source locations.
- **Images in every mode:** PNG/JPG/JPEG inputs always pass through the local vision model, including field extraction and planner runs. Full visual observations are saved and displayed separately from OCR-derived fields and source-term matches. Image summaries use the visual output even when OCR text exists. Zero supported OCR fields does not mean the image was not inspected; visual observations are advisory and are not assigned a source-verification score.
- **Bounded planner:** requires a stored `document_id`, uses allowlisted tools, enforces step and loop limits, and holds risky or unsupported findings for human review. A document with no findings can finish normally.
- **Retrieval:** `KAVACH_EMBEDDING_BACKEND=hash` computes real local lexical vectors without model dependencies. Choose `provider` to use Ollama or a configured Transformers encoder; encoder failures surface as errors. No automatic embedding backend switching occurs.
- **Monitoring:** hardware metrics are measured locally when available. Missing readings are null/unavailable. Model assignments say configured rather than claiming a successful health probe. Sandbox readiness checks the actual local engine and runner image.

New installations contain no documents, findings, runs, reports, sample charts, or sample search results. Backend outages produce explicit unavailable states. Test fixtures and provider doubles are confined to tests and evaluation code and excluded from Docker images.

## Local Transformers

Install `backend/requirements-transformers.txt`, set `KAVACH_INFERENCE_PROVIDER=transformers`, and point `KAVACH_TRANSFORMERS_MODEL_PATH` at a local directory containing `config.json` and safetensors weights. Remote model IDs and model downloads are disabled. For learned embeddings, also configure `KAVACH_TRANSFORMERS_EMBED_MODEL_PATH` and select the `provider` embedding backend. This adapter is text-only; image analysis requires Ollama with a vision-capable model.

## Storage and existing installations

Defaults are `data/uploads/`, `generated/`, and `backend/kavach.db`; all are local runtime state. Startup creates the schema and refreshes configured model assignments without loading content. The in-memory search index rebuilds from stored files after restart.

For an older installation, stop its backend and preview the one-time cleanup:

```sh
python backend/scripts/remove_legacy_examples.py
python backend/scripts/remove_legacy_examples.py --apply
```

The script removes records and report files traceable to legacy bundled examples and preserves uploaded files. Ambiguous runs sharing source filenames with user uploads are retained for manual provenance review. Use `--database PATH` for another database. Real audit events are retained as history. Existing uploads under `demo-data/uploads/` remain accessible through their stored paths; do not delete that directory without checking its contents.

## Docker

```sh
docker compose up --build -d
docker compose exec inference ollama pull qwen3:8b
docker compose exec inference ollama pull llava:7b
docker compose exec inference ollama pull llama3.2:3b
```

The stack uses real Ollama inference and persistent model/data volumes. Backend and inference share a network namespace to retain the loopback provider restriction. Browser ports bind to localhost. Models must be provisioned before an offline deployment; add GPU support according to the target host. `NEXT_PUBLIC_API_BASE` defaults to `http://localhost:8000` at frontend build time.

## Python sandbox

Open **Python Sandbox** in the sidebar to submit Python code and optional standard input. Each explicit run uses a fresh Linux container and returns real stdout, stderr, exit status, and timing. Document uploads and planner runs never execute code automatically.

On Windows with an existing Ubuntu WSL distribution, provision the runtime from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-sandbox.ps1 -InstallEngine
cd backend
python -m uvicorn app.main:app --env-file .env.sandbox --host 127.0.0.1 --port 8000
```

`-InstallEngine` installs Docker Engine inside `Ubuntu-24.04`; choose another installed distribution with `-Distribution`. Omit the switch if the engine is already installed. The script builds the restricted runner image and writes local backend settings. After a WSL restart, start its Docker service again before using the sandbox.

With Docker Engine or Docker Desktop already available directly:

```sh
docker build -t kavach-sandbox:1 docker/sandbox
```

Then start the backend normally. Docker Desktop must use Linux containers. Rootless Linux engines can be selected with `KAVACH_SANDBOX_DOCKER_HOST=unix:///run/user/UID/docker.sock`. Remote TCP/SSH engines are rejected. Set `KAVACH_SANDBOX_ENABLED=false` to disable execution explicitly.

The fixed runner policy disables networking, exposes no host mounts or daemon socket to code, makes the root filesystem read-only, and supplies a disposable 16 MB `/tmp`. The untrusted Python worker runs as UID/GID 65534 with no effective capabilities. A small trusted supervisor uses only SETUID, SETGID, and KILL capabilities to start and terminate that worker. The container uses Docker's default seccomp policy and no-new-privileges. Default limits are one CPU, 128 MB RAM with no swap, 32 processes, 10 seconds, and 64 KB combined output. No packages are installed during execution, and images are never pulled by an execution request. Jobs clean up on success, failure, or timeout; an internal supervisor also enforces the deadline if the backend disconnects.

Sandbox endpoints accept only loopback clients and local Host headers, reject untrusted browser origins, and require an explicit execution header. The UI sends this header automatically; CLI callers must set `X-Kavach-Sandbox: execute`. Only code hashes and outcome metadata enter the audit log. Docker isolation shares its engine's Linux kernel; deploy this trusted-workstation feature on a maintained dedicated runtime. The regular Compose backend intentionally has no Docker socket mount: use the native local backend for sandbox execution rather than granting the whole web container daemon access.

Run real-container tests after provisioning:

```powershell
$env:KAVACH_RUN_SANDBOX_INTEGRATION='1'
$env:KAVACH_SANDBOX_WSL_DISTRO='Ubuntu-24.04' # Windows WSL only
$env:KAVACH_SANDBOX_DOCKER_HOST='unix:///var/run/docker.sock' # WSL/Linux
cd backend
python -m pytest tests/test_sandbox_integration.py -q
```

## Verification and deployment scope

```sh
cd backend
pip install -r requirements-dev.txt
python -m pytest -q
# From frontend/:
npx tsc --noEmit
npm run build
```

See [post-optimization-testing/CHECKLIST.md](post-optimization-testing/CHECKLIST.md) for manual acceptance items and [VALIDATION.md](post-optimization-testing/VALIDATION.md) for checks actually run.

For a mentor demonstration of exactly three successful workflows and two expected failure cases, run `python backend/evals/mentor.py` from the repository root. It starts a separate local API with isolated storage, uses the real local models and OCR, and exports a printable HTML report, Markdown, CSV, JSON, and raw API evidence. See [mentor-testing/README.md](mentor-testing/README.md) for the five scenarios and how to explain the difference between a failed application request and a passing negative test.

This is a local, trusted-workstation application. Network-level egress blocking, authentication, transport security, disk encryption, backups, and multi-user isolation require deployment controls before wider exposure. Confidence and source verification describe extraction heuristics and citation support; they do not establish factual correctness. Workbench uses persistent background jobs; older document/task endpoints remain synchronous for API compatibility. Model summaries are advisory.
