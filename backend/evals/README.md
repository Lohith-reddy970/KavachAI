# Local OCR and citation evaluation

Run from `backend/`:

```bash
python -m evals.run
```

The suite always evaluates labeled page-citation cases: citation precision and
recall, page accuracy, and whether every reported character span reproduces its
quoted excerpt from the referenced page. OCR results are scored with character
error rate (CER) and word error rate (WER) against a generated two-page,
image-only PDF.

For the OCR portion, install the Python packages from `requirements.txt`, the
local Tesseract executable (with the configured language data), and PyMuPDF.
Without those local OCR prerequisites, the citation checks still run and the
report marks OCR as `unavailable`. To require OCR in a release/CI run:

```bash
python -m evals.run --require-ocr --max-cer 0.25 --max-wer 0.35
```

Optionally save the machine-readable report:

```bash
python -m evals.run --output generated/evaluation.json
```

The synthetic OCR pages contain no operational data. OCR scores vary slightly
by Tesseract version and trained language data; the tolerances should be kept
loose enough to detect regressions without treating harmless punctuation
differences as a failure.
