# Five tests for the mentor review

This suite runs **three successful workflow scenarios and two expected failure scenarios** against a separate local API process. It uses real Ollama text and vision models, real OCR, actual storage, and real API responses. No model responses are mocked, and no records are added to your normal Document Vault.

The completed execution on **2026-11-05** produced **3 successful workflows, 2 expected rejections, and 5/5 passing test verdicts**. Open the [executed HTML report](results/20261105-180018-0713fb/report.html), [five-row CSV](results/20261105-180018-0713fb/results.csv), or [Markdown report](results/20261105-180018-0713fb/report.md). The report includes the exact inputs, expected and actual outcomes, measured durations, and saved HTTP evidence.

## Run the five cases

Keep Ollama running with the configured reasoning, vision, and planner models installed. Install the backend requirements and local Tesseract as described in the root README, then run from the repository root:

```powershell
python backend/evals/mentor.py
```

The command prints the location of a new timestamped result folder under `mentor-testing/results/`. Open `report.html` in a browser. The same folder includes `report.md`, a five-row `results.csv`, full `results.json`, input files with hashes, the isolated API log, and raw HTTP evidence for each case. Previous executions are retained.

## Exactly five scenarios

| Case | Category | What you demonstrate | Expected application outcome |
|---|---|---|---|
| S1 | Successful | PDF extraction, real reasoning, source citation, high-risk review gate, reviewer decision, report download | Real analysis and a completed run after the test reviewer approves the held result |
| S2 | Successful | PNG inspection in Extract fields mode, OCR, local vision output, known date/amount extraction | Vision completes and supported literal fields appear with citations |
| S3 | Successful | Bounded planner, allowlisted actions, step budget, verified fields, reports | Planner finishes within ten steps |
| F1 | Expected failure | Attempt to upload a harmless plain-text fixture named `.exe` | HTTP 400; no document is created |
| F2 | Expected failure | Analyze a document ID that does not exist | HTTP 404; no run is created |

## Explain success versus failure correctly

Tell your mentor: “I tested three valid workflows and two invalid-input workflows. The valid inputs completed successfully. The invalid inputs produced the expected failure responses. All five test assertions should pass when the system behaves correctly.”

The **scenario outcome** and **test verdict** are different columns. F1 and F2 are failed application requests, but they are passing negative tests when the rejection is correct. Do not describe them as two software defects. If your mentor requires two observed implementation defects or model-accuracy limitations, these rejection cases do not establish that; use separately observed, documented defects instead.

## Present each result

1. Show the input file and the objective.
2. State the expected result before opening the evidence.
3. Show the actual HTTP status, saved job/run details, and assertions from `report.html`.
4. Explain why the observed behavior is correct or incorrect. S1's initial human-review hold is correct behavior. S2's visual observations remain advisory; the known OCR fields are checked separately.
5. For F1 and F2, show the error response and unchanged record counts.

The runner never changes a failed result to force the requested 3/2 split. Missing models, OCR errors, timeouts, and assertion mismatches remain visible as **FAIL**, and the process exits with a nonzero status. These five controlled cases demonstrate selected functional behavior; they do not establish a general model-accuracy percentage or certify production readiness.
