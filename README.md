<div align="center">

# 🛡️ KAVACH AI

### Local-First Document Intelligence Workbench

**A self-hosted, air-gapped workbench that analyzes confidential documents with local AI agents, cites its evidence, and routes risky findings to human review.**

</div>

---

KAVACH AI runs entirely on your machine. You upload documents, choose a domain profile and an analysis task, and a team of small single-purpose agents reads the files, retrieves supporting passages, produces findings with source citations, verifies every quoted excerpt, and holds high-risk findings for human approval.

Nothing is sent to a cloud service. Host development defaults to local [Ollama](https://ollama.com) models; a deterministic mock provider keeps the app usable without a GPU or any models installed.

> **What is real vs. illustrative**
> The agent architecture, planner loop, tool allowlist, human-approval gate, document upload, audit log, domain profiles, and Ollama integration are implemented and tested. Uploaded-text findings use profile vocabulary with source excerpts (not LLM-authored findings); summaries are model-generated and advisory; field extraction is literal. The bundled inspection scenario is a fixed, **fictional** dataset ("KAVACH DEMO REFINERY").

---

## Contents

1. [Features](#features)
2. [Quickstart](#quickstart)
3. [The console](#the-console)
4. [How it works](#how-it-works)
5. [Document profiles and analysis modes](#document-profiles-and-analysis-modes)
6. [The agentic planner](#the-agentic-planner)
7. [Configuration](#configuration)
8. [API reference](#api-reference)
9. [Project structure](#project-structure)
10. [Security](#security)
11. [Tests](#tests)
12. [Limitations](#limitations)

---

## Features

- **Nine agents** — security, router, document, vision, knowledge, reasoning, verification, deliverable, and a planner, all sharing one run context and emitting a complete, auditable trace.
- **Domain profiles** — swap the review vocabulary per document type: *General documents* or *Industrial engineering*.
- **Analysis modes** — **Risk review** (profile-term extraction with verified source excerpts), **Summary** (model-generated, advisory; also describes images via the vision model), and **Extract fields** (literal dates, equipment IDs, and measurements with citations).
- **Human-in-the-loop** — high-risk, low-confidence, unsupported, or unverified findings are held until a reviewer approves or rejects them.
- **Bounded agentic planner** — the planner chooses its own next step from a fixed tool allowlist, with a step limit, loop detection, and a review gate that always runs last.
- **Local inference routing** — reasoning, vision, and other text tasks are routed to separate local models (Ollama); the RAG index uses local embeddings.
- **Live system metrics** — the System page reads real GPU telemetry via `nvidia-smi` and CPU/RAM via `psutil`, and clearly labels any simulated fallback.
- **Local-only storage** — documents, the vector index, runs, and reports stay on the host filesystem and in SQLite.
- **Audit log** — uploads, analyses, runs, searches, reviews, and downloads are recorded locally and shown in the Security Center.

---

## Quickstart

### Option A — local development (recommended)

**Prerequisites:** Python 3.10+, Node 18+, and optionally [Ollama](https://ollama.com) with the models below.

```bash
ollama pull qwen3:8b          # reasoning
ollama pull llava:7b          # vision / image description
ollama pull llama3.2:3b       # other text tasks and planner choices
ollama pull nomic-embed-text  # RAG embeddings
```

**Backend** (from the repository root):

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000     # → http://localhost:8000/docs
```

**Frontend** (second terminal):

```bash
cd frontend
npm install
npm run dev                                     # → http://localhost:3000
```

The backend defaults to Ollama on the host. To run fully deterministic with no models:

```bash
# macOS/Linux
KAVACH_INFERENCE_PROVIDER=mock python -m uvicorn app.main:app --port 8000
# Windows PowerShell
$env:KAVACH_INFERENCE_PROVIDER="mock"; python -m uvicorn app.main:app --port 8000
```

The frontend also runs **on its own** — with the backend offline it shows bundled sample data and disables live features.

### Option B — Docker

```bash
docker compose up --build
# frontend → http://localhost:3000
# backend  → http://localhost:8000/api/health
```

Docker Compose runs the backend with the mock provider (Ollama is not part of the compose stack), so the demo works without a GPU.

---

## The console

| Page | What it does |
|---|---|
| **Overview** | Data-boundary diagram, pipeline summary, bundled metrics |
| **Workbench** | Document analysis (profile + task + source) and the sample workflow |
| **Document Vault** | Upload, list, and analyze stored documents |
| **Knowledge Base** | Search the local RAG index |
| **Agent Runs** | Backend runs with traces, evidence, and approve/reject buttons |
| **Model Router** | Configured model assignments and routing rules |
| **Security Center** | Controls overview and the live audit log |
| **Deliverables** | Generated reports with download links |
| **System** | Live GPU/CPU/RAM metrics and service status |

---

## How it works

```
 USER (document analysis request)
              │
      ┌───────▼────────┐
      │ SECURITY AGENT │  mode + provider check
      └───────┬────────┘
      ┌───────▼────────┐
      │  ROUTER AGENT  │  task type → local model
      └───────┬────────┘
  ┌───────────┼────────────┐
┌─▼────────┐ ┌▼──────────┐ ┌▼───────────────┐
│ DOCUMENT │ │  VISION   │ │   KNOWLEDGE    │
│ extract  │ │  images   │ │  RAG retrieval │
└─┬────────┘ └┬──────────┘ └┬───────────────┘
  └───────────┼────────────┘
      ┌───────▼────────┐
      │   REASONING    │  evidence → findings
      └───────┬────────┘
      ┌───────▼────────┐
      │  VERIFICATION  │  findings vs. source
      └───────┬────────┘
      ┌───────▼────────┐
      │  HUMAN REVIEW  │  approve / reject
      └───────┬────────┘
      ┌───────▼────────┐
      │  DELIVERABLE   │  TXT / MD / DOCX / XLSX / PDF
      └────────────────┘
```

- The **fixed pipeline** (`POST /api/demo/run`, `POST /api/documents/{id}/analyze`) walks this order every time.
- The **agentic planner** (`POST /api/agent/run`) lets the planner choose which step runs next, under hard guardrails.

**Local model routing**

| Role | Default model |
|---|---|
| Reasoning | `qwen3:8b` |
| Vision | `llava:7b` |
| Other text tasks and planner choices | `llama3.2:3b` |
| RAG embeddings | `nomic-embed-text` |

In `airgapped` mode the Ollama URL must be loopback (`localhost` / `127.0.0.1`). If a model or server is unavailable, generation falls back to the deterministic mock provider.

---

## Document profiles and analysis modes

| Profile | Intended content | Review vocabulary |
|---|---|---|
| **General documents** | Reports, policies, correspondence, records | Issues, delays, missing items, exceptions, risks |
| **Industrial engineering** | Equipment integrity, maintenance, process safety | Corrosion, leaks, vibration, fouling, equipment terms |

| Mode | Behavior |
|---|---|
| **Risk review** | Finds sentences matching the profile vocabulary and verifies every quoted excerpt against the source |
| **Summary** | Model-generated, advisory; for images it uses the vision model to describe visible content |
| **Extract fields** | Literal extraction of dates, equipment identifiers, and measurements, each with its source excerpt |

Profiles and modes are included in the generated report. The vocabulary lives in `backend/app/domains/profiles.py` and is easy to extend.

---

## The agentic planner

`POST /api/agent/run` runs an observe → decide → act loop. The planner may only choose among eligible actions, each backed by one allowlisted tool:

| Action | Eligible when |
|---|---|
| `inspect_document` | Documents not loaded yet |
| `analyze_pid` | Task mentions a diagram and regions not analyzed |
| `search_knowledge` | Nothing retrieved yet |
| `reason` | Evidence gathered, no findings yet |
| `verify` | Findings exist but are unverified |
| `human_review` | Verification requires approval |
| `finish` | Everything complete |

**Guardrails** (enforced in code, covered by tests):

1. Bounded steps — `max_steps` default 10, hard cap 20.
2. Loop detection — repeating an action with identical arguments halts the run.
3. Tool allowlist — no shell, SQL, filesystem, or network tools; unknown tools halt the run.
4. Prerequisites cannot be skipped.
5. The review gate always runs last, independent of the planner.
6. Any stop other than `finish` halts the run and escalates every finding to human review.

---

## Configuration

All settings are environment-driven with safe local defaults — see [`.env.example`](.env.example).

| Variable | Default | Purpose |
|---|---|---|
| `KAVACH_MODE` | `airgapped` | `airgapped` blocks external providers and non-loopback URLs |
| `KAVACH_INFERENCE_PROVIDER` | `ollama` | `ollama` or `mock` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Must be loopback when airgapped |
| `OLLAMA_REASONING_MODEL` | `qwen3:8b` | Reasoning model |
| `OLLAMA_VISION_MODEL` | `llava:7b` | Image model |
| `OLLAMA_OTHER_MODEL` | `llama3.2:3b` | Other text tasks and planner choices |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | RAG embeddings |
| `OLLAMA_TIMEOUT_S` | `120` | Per-request Ollama timeout |
| `KAVACH_PLANNER_MAX_STEPS` | `10` | Planner step budget (hard cap 20) |
| `KAVACH_REVIEW_MIN_CONFIDENCE` | `75` | Findings below this need approval |
| `KAVACH_MAX_UPLOAD_MB` | `25` | Upload size cap |
| `KAVACH_DB` | `backend/kavach.db` | SQLite path |

---

## API reference

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Status, mode, version |
| GET | `/api/system/status` | Live GPU/CPU/RAM when detectable (labelled fallback), models, vector DB, sandbox, network |
| GET | `/api/profiles` | Document profiles and analysis modes |
| POST | `/api/documents/upload` | Upload a file (allowlist, 25 MB cap, sanitized name) |
| GET | `/api/documents` · `/api/documents/{id}` | List / fetch documents |
| POST | `/api/documents/{id}/analyze` | Analyze with `profile` and `analysis_mode` |
| POST | `/api/tasks` | Create a task and run the sample pipeline |
| POST | `/api/demo/run` · GET `/api/demo/stream` | Fixed sample scenario (and SSE stream) |
| GET | `/api/agent/tools` | Planner tool allowlist |
| POST | `/api/agent/run` | Bounded agentic planner run (`task`, optional `max_steps`) |
| GET | `/api/agents/runs` · `/api/agents/runs/{id}` | Run list / full trace |
| POST | `/api/review/{finding_id}/approve` · `/reject` | Human review decision |
| GET | `/api/models` | Model catalogue, routing rules, providers |
| GET | `/api/knowledge` · POST `/api/knowledge/search` | KB stats / RAG search |
| GET | `/api/audit-logs` | Audit entries |
| GET | `/api/deliverables` · `/api/deliverables/{id}/download` | List / download reports |

Interactive docs: `http://localhost:8000/docs`.

---

## Project structure

```
KAVACH-AI/
├── frontend/                  Next.js console (9 sections)
│   ├── app/                   overview, workbench, vault, knowledge, runs,
│   │                          router, security, deliverables, system
│   ├── components/            shell · UI primitives · visualizations
│   └── lib/                   API client, live data layer, bundled sample data
├── backend/
│   ├── app/
│   │   ├── agents/            9 agents · orchestrator · tools · review gate
│   │   ├── domains/           general and industrial analysis profiles
│   │   ├── models/            provider abstraction (Ollama/mock/vLLM stub) · router
│   │   ├── rag/               chunking · embeddings · in-memory index
│   │   ├── security/          airgap guard · upload validation · audit middleware
│   │   ├── services/          document analysis · deliverables · system status
│   │   ├── api/               HTTP routes
│   │   ├── database/          SQLite layer
│   │   └── schemas/           request/response models
│   └── tests/                 pytest suite (49 tests)
├── demo-data/                 fictional sample documents + generator script
├── generated/                 sample generated reports
├── docker/                    backend + frontend Dockerfiles
└── docker-compose.yml
```

**Tech stack:** Next.js 14 · React 18 · TypeScript · Tailwind CSS · Recharts · zustand — FastAPI · Python 3.10+ · SQLite · Ollama.

---

## Security

**Implemented**

- Airgapped mode (`KAVACH_MODE=airgapped`, the default) rejects external providers and non-loopback inference URLs.
- No cloud AI SDKs; Ollama requests are loopback-restricted.
- Upload controls: extension allowlist, 25 MB cap, path-traversal-safe filenames, no overwrites.
- Uploaded code is never executed (the sandbox component is a stub).
- Planner guardrails and the mandatory review gate.
- Local audit log for uploads, analyses, runs, searches, reviews, and downloads.

**Not implemented (prototype scope)**

- No authentication or RBAC; the API is open to anything that can reach the port.
- No encryption at rest.
- The audit log is an ordinary table, not tamper-evident.
- Docker Compose does not isolate the container network.
- The frontend fetches fonts at build time; the running app makes no external requests.

---

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest tests -q          # 49 tests
```

Coverage includes the planner loop and its guardrails, the tool allowlist, the review gate and approval flow, model routing, document profiles and modes, Ollama request formatting, knowledge search, the airgap guard, and uploaded-document analysis (extraction, verification, unreadable files, duplicate filenames).

Frontend checks:

```bash
cd frontend
npx tsc --noEmit && npm run build
```

---

## Limitations

- **Risk review is profile-term extraction** — it can miss risks phrased without those terms, and its "confidence" is match strength, not a probability.
- **Model output does not authoritatively create findings yet** — summaries and advisory analysis are recorded in the run trace; findings come from profile-term extraction or literal field extraction.
- **No OCR pipeline** — images have no extracted text; use **Summary** for a vision-model description. Scanned PDFs yield no text.
- **Sample scenario** — the bundled inspection run uses fixed fictional findings; the Workbench animation is client-side sample data.
- **Initial profile set is intentionally small** — General and Industrial are configurable vocabularies, not comprehensive domain expertise. Multi-document comparison is not implemented.
- Ollama model calls require the local service and listed model tags; automated tests mock those calls.

---

<div align="center">
<sub>KAVACH AI · Local-first document intelligence</sub>
</div>
