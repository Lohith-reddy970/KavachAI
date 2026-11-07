# Five acceptance test results

Executed: 2026-11-05T18:01:10.809371+00:00

Three valid workflow cases and two expected failure cases. A correct rejection is a passing negative test, not an application defect.

| Case | Scenario | Actual outcome | Test verdict | Duration |
|---|---|---|---|---|
| S1 | PDF review, citations, and human approval | successful | PASS | 23.75s |
| S2 | PNG inspection, OCR, and literal fields | successful | PASS | 17.30s |
| S3 | Bounded planner execution | successful | PASS | 8.23s |
| F1 | Unsupported file rejected | expected rejection | PASS | 0.07s |
| F2 | Missing source document rejected | expected rejection | PASS | 0.02s |

## Interpretation

These are controlled acceptance checks on an isolated database with real local model calls. They do not estimate general model accuracy or prove production readiness.

## S1 - PDF review, citations, and human approval

**Input:** [inputs/S1_inspection.pdf](inputs/S1_inspection.pdf)

**Expected:** Analysis finishes with a source-cited high-severity match, initially held for review. The reviewer decision completes the run and a report downloads.

**Observed:** {"document_id": 1, "job_id": "0eee4b33833e479ba31b68bc14e480ea", "job_status": "completed", "run_id": 1, "stage_statuses": {"validation": "completed", "extraction": "completed", "routing": "completed", "vision": "skipped", "knowledge": "completed", "reasoning": "completed", "verification": "completed", "deliverables": "completed"}, "run_status": "awaiting_review", "fields_or_matches": 1, "verification_score": 100.0, "evidence_backed": "1/1", "report_formats": ["txt", "md", "docx", "xlsx", "pdf"], "reasoning_model": "qwen3:8b", "run_status_after_review": "completed"}

**Explain to the mentor:** The successful behavior includes the human-review hold. A critical finding must not be silently cleared. Citation verification checks the excerpt against the supplied PDF; it does not prove the inspection claim is true.

Checks:

- PASS: Upload succeeds
- PASS: Job accepted
- PASS: Analysis finishes
- PASS: Real local reasoning output is recorded
- PASS: PDF text extracted
- PASS: Critical source match found
- PASS: Citations independently match the supplied PDF
- PASS: High-risk result is held for review
- PASS: Review decision stored for finding 1
- PASS: All required decisions complete the run
- PASS: Actual report downloads

Raw evidence:

- [evidence/S1/001_post.json](evidence/S1/001_post.json)
- [evidence/S1/002_post.json](evidence/S1/002_post.json)
- [evidence/S1/003_get.json](evidence/S1/003_get.json)
- [evidence/S1/004_get.json](evidence/S1/004_get.json)
- [evidence/S1/005_get.json](evidence/S1/005_get.json)
- [evidence/S1/006_get.json](evidence/S1/006_get.json)
- [evidence/S1/007_get.json](evidence/S1/007_get.json)
- [evidence/S1/008_get.json](evidence/S1/008_get.json)
- [evidence/S1/009_get.json](evidence/S1/009_get.json)
- [evidence/S1/010_get.json](evidence/S1/010_get.json)
- [evidence/S1/011_get.json](evidence/S1/011_get.json)
- [evidence/S1/012_get.json](evidence/S1/012_get.json)
- [evidence/S1/013_get.json](evidence/S1/013_get.json)
- [evidence/S1/014_get.json](evidence/S1/014_get.json)
- [evidence/S1/015_get.json](evidence/S1/015_get.json)
- [evidence/S1/016_get.json](evidence/S1/016_get.json)
- [evidence/S1/017_get.json](evidence/S1/017_get.json)
- [evidence/S1/018_get.json](evidence/S1/018_get.json)
- [evidence/S1/019_get.json](evidence/S1/019_get.json)
- [evidence/S1/020_get.json](evidence/S1/020_get.json)
- [evidence/S1/021_get.json](evidence/S1/021_get.json)
- [evidence/S1/022_get.json](evidence/S1/022_get.json)
- [evidence/S1/023_get.json](evidence/S1/023_get.json)
- [evidence/S1/024_get.json](evidence/S1/024_get.json)
- [evidence/S1/025_get.json](evidence/S1/025_get.json)
- [evidence/S1/026_get.json](evidence/S1/026_get.json)
- [evidence/S1/027_post.json](evidence/S1/027_post.json)
- [evidence/S1/028_get.json](evidence/S1/028_get.json)
- [evidence/S1/029_get.json](evidence/S1/029_get.json)

## S2 - PNG inspection, OCR, and literal fields

**Input:** [inputs/S2_invoice.png](inputs/S2_invoice.png)

**Expected:** Image inspection completes, OCR reads the page, and the known date and amount appear as literal fields with citations. Visual observations are shown separately.

**Observed:** {"document_id": 2, "job_id": "783f7fffaeb24ad6be02144ef16d9d1d", "job_status": "completed", "run_id": 2, "stage_statuses": {"validation": "completed", "extraction": "completed", "routing": "completed", "vision": "completed", "knowledge": "completed", "reasoning": "completed", "verification": "completed", "deliverables": "completed"}, "run_status": "completed", "fields_or_matches": 5, "verification_score": 100.0, "evidence_backed": "5/5", "report_formats": ["txt", "md", "docx", "xlsx", "pdf"], "vision_model": "llava:7b", "vision_output": "The image shows a document with the following visible content:\n\n```\nCONTROLLED ACCEPTANCE TEST INPUT\nTEST INVOICE - NOT A REAL PAYMENT\n\nInvoice: INV-2026-005\nDate: 2026-11-05\nTotal: INR 2500\n\nOwner: Test Coordinator\nContact: quality@example.org\n```\n\nThe document appears to be a structured form with fields for an invoice, date, total amount, owner, and contact information. The \"Total\" field is in Indian Rupees (INR). The \"Owner\" field is filled with \"Test Coordinator,\" and the \"Contact\" field is filled with an email address. The \"Invoice\" and \"Date\" fields are also filled with specific values. The \"Total\" field is the only one that is filled in, while the \"Invoice\" and \"Date\" fields are partially visible. The \"Owner\" and \"Contact\" fields are fully visible. The \"Invoice\" field is a combination of letters and numbers, and the \"Date\" field is in the format of year-month-day. The \"Total\" field is in the format of currency followed by the amount. The \"Invoice\" and \"Date\" fields are aligned to the left, while the \"Total\" field is aligned to the right. The \"Owner\" and \"Contact\" fields are aligned to the left. The document has a plain background and is presented in a portrait orientation.", "ocr_pages": 1, "extracted_fields": ["Extracted reference identifier: INV-2026-005", "Extracted date: 2026-11-05", "Extracted amount: INR 2500", "Extracted owner / approver: Test Coordinator", "Extracted email: quality@example.org"]}

**Explain to the mentor:** This checks the PNG regression: field extraction must not skip vision. The field assertions compare known input values with actual output. A nonempty model description proves the path ran, not that every visual statement is accurate.

Checks:

- PASS: Upload succeeds
- PASS: Job accepted
- PASS: Analysis finishes
- PASS: Image inspection ran
- PASS: Real vision output is saved separately
- PASS: Local OCR processed the page
- PASS: Known date is extracted
- PASS: Known amount is extracted
- PASS: Literal field citations verify

Raw evidence:

- [evidence/S2/030_post.json](evidence/S2/030_post.json)
- [evidence/S2/031_post.json](evidence/S2/031_post.json)
- [evidence/S2/032_get.json](evidence/S2/032_get.json)
- [evidence/S2/033_get.json](evidence/S2/033_get.json)
- [evidence/S2/034_get.json](evidence/S2/034_get.json)
- [evidence/S2/035_get.json](evidence/S2/035_get.json)
- [evidence/S2/036_get.json](evidence/S2/036_get.json)
- [evidence/S2/037_get.json](evidence/S2/037_get.json)
- [evidence/S2/038_get.json](evidence/S2/038_get.json)
- [evidence/S2/039_get.json](evidence/S2/039_get.json)
- [evidence/S2/040_get.json](evidence/S2/040_get.json)
- [evidence/S2/041_get.json](evidence/S2/041_get.json)
- [evidence/S2/042_get.json](evidence/S2/042_get.json)
- [evidence/S2/043_get.json](evidence/S2/043_get.json)
- [evidence/S2/044_get.json](evidence/S2/044_get.json)
- [evidence/S2/045_get.json](evidence/S2/045_get.json)
- [evidence/S2/046_get.json](evidence/S2/046_get.json)
- [evidence/S2/047_get.json](evidence/S2/047_get.json)
- [evidence/S2/048_get.json](evidence/S2/048_get.json)
- [evidence/S2/049_get.json](evidence/S2/049_get.json)

## S3 - Bounded planner execution

**Input:** [inputs/S3_project_record.txt](inputs/S3_project_record.txt)

**Expected:** Planner stops with finished within 10 steps, uses permitted actions, extracts the known date/amount, and saves reports.

**Observed:** {"document_id": 3, "job_id": "99a598ffa146409ba34886f40b5f1765", "job_status": "completed", "run_id": 3, "stage_statuses": {"validation": "completed", "extraction": "completed", "routing": "completed", "vision": "skipped", "knowledge": "completed", "reasoning": "completed", "verification": "completed", "deliverables": "completed"}, "run_status": "completed", "fields_or_matches": 5, "verification_score": 100.0, "evidence_backed": "5/5", "report_formats": ["txt", "md", "docx", "xlsx", "pdf"], "planner": {"provider": "ollama", "max_steps": 10, "steps_used": 5, "stop_reason": "finished", "trace": [{"step": 1, "action": "inspect_document", "reason": "Documents have not been loaded yet.", "args": {}, "status": "completed"}, {"step": 2, "action": "search_knowledge", "reason": "No supporting knowledge retrieved yet.", "args": {"query": "Analyze the selected controlled test input using only its content.", "top_k": 4}, "status": "completed"}, {"step": 3, "action": "reason", "reason": "Evidence gathered; ready to synthesize findings.", "args": {}, "status": "completed"}, {"step": 4, "action": "verify", "reason": "Findings exist but are not verified.", "args": {}, "status": "completed"}, {"step": 5, "action": "finish", "reason": "All required steps are complete.", "args": {}, "status": "completed"}], "requires_human_review": false, "review_required": [], "allowed_tools": ["search_knowledge", "inspect_document", "analyze_pid", "reason", "verify", "human_review"]}, "extracted_fields": ["Extracted reference identifier: PRJ-2026-103", "Extracted date: 2026-11-06", "Extracted amount: INR 4800", "Extracted owner / approver: Test Coordinator", "Extracted email: planner@example.org"]}

**Explain to the mentor:** This is the agentic path rather than the fixed pipeline. The trace shows which allowed action was selected at each step. Awaiting human review is an acceptable completed-analysis outcome.

Checks:

- PASS: Upload succeeds
- PASS: Job accepted
- PASS: Analysis finishes
- PASS: Planner finishes normally
- PASS: Step budget respected
- PASS: Only specified permitted actions used
- PASS: Planner returns known literal values
- PASS: Planner saves reports and verifies citations

Raw evidence:

- [evidence/S3/050_post.json](evidence/S3/050_post.json)
- [evidence/S3/051_post.json](evidence/S3/051_post.json)
- [evidence/S3/052_get.json](evidence/S3/052_get.json)
- [evidence/S3/053_get.json](evidence/S3/053_get.json)
- [evidence/S3/054_get.json](evidence/S3/054_get.json)
- [evidence/S3/055_get.json](evidence/S3/055_get.json)
- [evidence/S3/056_get.json](evidence/S3/056_get.json)
- [evidence/S3/057_get.json](evidence/S3/057_get.json)
- [evidence/S3/058_get.json](evidence/S3/058_get.json)
- [evidence/S3/059_get.json](evidence/S3/059_get.json)
- [evidence/S3/060_get.json](evidence/S3/060_get.json)

## F1 - Unsupported file rejected

**Input:** [inputs/F1_disallowed.exe](inputs/F1_disallowed.exe)

**Expected:** HTTP 400 states that the file type is not allowed. No document record is created.

**Observed:** {"http_status": 400, "error_response": {"detail": "File type '.exe' not allowed. Allowed: csv, docx, jpeg, jpg, pdf, png, py, txt."}, "documents_before": 3, "documents_after": 3}

**Explain to the mentor:** The upload operation is expected to fail. The test passes only if the application rejects it correctly. The .exe fixture is plain test text and is never executed.

Checks:

- PASS: Disallowed extension is rejected with HTTP 400
- PASS: Clear policy error is returned
- PASS: Rejected upload creates no document

Raw evidence:

- [evidence/F1/061_get.json](evidence/F1/061_get.json)
- [evidence/F1/062_post.json](evidence/F1/062_post.json)
- [evidence/F1/063_get.json](evidence/F1/063_get.json)

## F2 - Missing source document rejected

**Input:** [inputs/F2_missing_document_request.json](inputs/F2_missing_document_request.json)

**Expected:** HTTP 404 states Document not found. No analysis run is created.

**Observed:** {"http_status": 404, "error_response": {"detail": "Document not found"}, "runs_before": 3, "runs_after": 3}

**Explain to the mentor:** The analysis request is expected to fail because its source does not exist. Correct rejection is a passing negative test; a server error or fabricated result would fail the test.

Checks:

- PASS: Missing source is rejected with HTTP 404
- PASS: Clear missing-document error is returned
- PASS: Rejected request creates no run

Raw evidence:

- [evidence/F2/064_get.json](evidence/F2/064_get.json)
- [evidence/F2/065_post.json](evidence/F2/065_post.json)
- [evidence/F2/066_get.json](evidence/F2/066_get.json)
