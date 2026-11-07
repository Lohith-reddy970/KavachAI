# Validation record

Date: 2026-11-05

## Completed during cleanup

| Check | Result |
|---|---|
| Backend regression suite | 77 tests passed; includes extraction, citations, planner bounds, review rules, empty installation, upload-backed indexing, inference errors, cleanup preservation, and unavailable telemetry |
| TypeScript | `npx.cmd tsc --noEmit` passed |
| Frontend production build | `npm.cmd run build` passed; all routes compiled and generated |
| Legacy content cleanup | Removed seeded documents, prepared runtime scenarios/replays, bundled example assets, and their generated reports; retained actual audit history |

Backend test command: `python -m pytest -q --basetemp=E:\miniproject\KAVACH-AI\.test-tmp-final -p no:cacheprovider`. The first run could not access an existing Windows pytest temporary directory; the project-local rerun passed. Two dependency deprecation warnings remain in Starlette's test client integration.

## Still requires target-host validation

Real Ollama and Transformers inference, OCR quality, browser interaction, report rendering, Docker execution, GPU behavior, concurrency/load, backup recovery, and deployment access/network controls have not been certified by these unit tests. Follow [CHECKLIST.md](CHECKLIST.md). Inference responses used in unit tests are test-only doubles; the application has no substitute inference provider.

The final production build passed after granting access for Next.js Google Fonts downloads. Initial builds require network access or a separately provisioned local-font setup. Docker was not installed in this environment, so container execution remains a checklist item.

## Sandbox implementation and live verification

The earlier Docker limitation above was resolved for the sandbox: Docker Engine was installed inside the existing Ubuntu-24.04 WSL distribution, and `kavach-sandbox:1` was built from `docker/sandbox/`. The native backend now starts with `backend/.env.sandbox`. Native Windows Docker and the full Compose application stack were not exercised.

| Check | Result |
|---|---|
| Updated backend unit/regression suite | 106 passed; 8 opt-in integration tests skipped in this run |
| Real-container integration suite | All 8 passed against the local WSL Docker engine |
| Real Python/stdin and worker identity | Executed Python and read stdin; worker UID 65534 verified |
| Isolation | Outbound network connection blocked, host mounts/socket absent, root filesystem write rejected, effective capabilities zero, no-new-privileges active |
| Runtime limits | Real timeout, output-flood limit, and memory-limit failure verified |
| Lifecycle | Temporary file absent in the next job; no sandbox job containers left after tests |
| API/request guards | Tests reject remote peers, untrusted Origin/Host, missing execution header, invalid input, and caller-supplied image options; cleanup/protocol failures do not report success |
| Live API execution | `POST /api/sandbox/execute` executed `print(sum([10, 20, 12]))`, returned stdout `42`, exit 0, and an actual Docker job ID |
| Audit | Live execution recorded its code SHA-256 and outcome without storing submitted source/output in the audit entry |
| Live readiness/UI route | `/api/sandbox/status` and System report ready; `/sandbox` returns HTTP 200 |
| Frontend | TypeScript check and production build passed with the new Sandbox route |

Combined coverage: 114 passing distinct backend tests across the regression and real-container runs. Existing Starlette test-client deprecation warnings remain. Browser interaction, adversarial kernel-escape review, larger load, and the full Compose stack remain deployment acceptance work.

## Workbench progress and inline results

- Full regression suite: 113 passed, with the 8 existing real-container tests skipped in this run. The sandbox implementation was unchanged by the Workbench update.
- Seven new tests cover visible progress before model completion, complete summaries and extraction metadata saved on runs, error-stage handling, current reviewer decisions after reload, planner jobs, queue limits/invalid requests, per-page OCR events, and restart recovery.
- TypeScript checking and the production build passed. The backend and frontend were restarted with the updated code.
- Live job `fe34f92b0a064da4bae477631ae903e8` processed stored document 13 into run 19: 56 pages, 3 OCR pages, 1,224 model-response characters, and 5 generated reports. Polling observed page 7/8/9 extraction, local reasoning, and report saving before receiving the final result. The OCR note and skipped image/summary-verification stages remained visible in the final snapshot.
- Native Windows browser verification was stopped because the computer-use tool does not support URL-policy enforcement for the current browser. No browser interaction was performed. Visual layout and interactive browser acceptance checks remain in CHECKLIST.md; API behavior, persistence, stage events, and compiled UI contracts were verified.

## PNG inspection correction

- Root cause: uploaded image document 15 was analyzed with `extract_fields`; the old vision agent only inspected images in Summary mode. The literal extractor correctly found zero supported fields, but the image itself had been skipped.
- PNG/JPG/JPEG inputs now invoke the configured local vision model in every mode and in the bounded planner. Full visual observations are persisted separately, shown directly in results, and included in report exports. Image summaries prefer visual output even when OCR text is available. Empty-field messages identify which field types were searched; visual observations are advisory and do not receive a source-verification score.
- Full regression suite: **121 passed, 8 optional sandbox integration tests skipped**. TypeScript checking and the production build passed. Eight new image cases cover all three modes through both workflows, image summaries with OCR present, and explicit vision-provider failures.
- Live job `266a78a060b743a9834ec9d158fd6fc0` reprocessed the actual uploaded PNG in Extract fields mode, producing run **23**. The `vision` stage completed with **llava:7b / Ollama**, returned a nonempty image description, retained zero literal fields, used no verification score for visual observations, and generated all five report formats.
- Model-generated visual descriptions can contain transcription mistakes. They are displayed as advisory observations rather than verified facts or invented source findings. Browser visual verification remains subject to the Windows automation limitation recorded above.

## Mentor demonstration: five executed acceptance cases

Executed on 2026-11-05 at 18:00:21-18:01:10 UTC (23:30-23:31 IST), using `python backend/evals/mentor.py`. The runner created a separate loopback API process and isolated storage, used actual local Ollama/OCR execution, and stopped its own API process afterward. The normal Document Vault was not used.

| Case | Actual application result | Test verdict | Measured duration |
|---|---|---|---|
| S1: PDF review and approval | Extracted one PDF page; qwen3:8b reasoning; independently matched the source citation; held a high-risk finding for review; completed after approval; downloaded the report | PASS | 23.748 s |
| S2: PNG OCR and image inspection | Tesseract processed one page; llava:7b image inspection completed; extracted the known date and INR 2500 with five supported fields | PASS | 17.305 s |
| S3: Bounded planner | Finished in five permitted actions within the ten-step budget; returned the known date and INR 4800; saved reports | PASS | 8.228 s |
| F1: Unsupported upload | HTTP 400 with a file-type error; document count stayed at three | PASS: expected failure | 0.066 s |
| F2: Missing document | HTTP 404 with `Document not found`; run count stayed at three | PASS: expected failure | 0.016 s |

Result: **three successful workflow scenarios and two expected application failures; all five test verdicts passed**. The two rejected requests demonstrate validation behavior, not two implementation defects. These controlled cases do not establish a general model-accuracy score.

Evidence: [HTML report](../mentor-testing/results/20261105-180018-0713fb/report.html), [CSV](../mentor-testing/results/20261105-180018-0713fb/results.csv), [full JSON](../mentor-testing/results/20261105-180018-0713fb/results.json), and [rerun/presentation instructions](../mentor-testing/README.md). All input SHA-256 hashes, raw HTTP evidence, CSV row counts, and local HTML links were checked. The isolated API was confirmed stopped. The evaluator's four automated tests also passed; two existing dependency deprecation warnings remain.

## Vault viewing and deletion

Date: 2026-11-06 (IST).

- Added local in-page PDF/image previews, literal text/CSV/Python display, and DOCX paragraph/table previews. Original downloads preserve uploaded bytes. Long text previews stop at 200,000 characters. Source paths are constrained to the configured upload directory; explicit MIME types and `nosniff` prevent text/code uploads being treated as HTML.
- Delete requires an in-app confirmation. It removes the source file and Vault record, and the next knowledge lookup rebuilds without that document. Historical findings, reviews, analysis jobs, and report exports remain. Queued/running jobs and synchronous pipeline/planner analyses prevent deletion, including during extraction before a run exists. File-removal failures preserve the record and return a useful error.
- Full backend regression: **142 passed, 8 optional container tests skipped**, including 17 new Vault cases covering every upload type, exact downloads, PDF byte ranges, bounded previews, path containment, missing files, removal failures, historical reports, index refresh, and concurrent analysis. Two existing Starlette dependency deprecation warnings remain.
- TypeScript checking and the production build passed. The backend and frontend were restarted with the update, and the live frontend was confirmed to serve the new preview/delete bundle.
- [Live acceptance evidence](evidence/vault-20261106.json): all 16 checks passed against the running app. Temporary PDF and PNG uploads opened, downloaded with exact bytes, supported PDF range requests, and were deleted successfully. Both temporary source records were removed and all pre-existing Vault records were retained.
- Interactive browser/visual checks remain in [CHECKLIST.md](CHECKLIST.md), under the Windows browser-tool limitation recorded earlier. API/file behavior, generated UI bundle, type checking, and production compilation were verified.
