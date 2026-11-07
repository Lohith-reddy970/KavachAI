"""Reproducible offline OCR and page-citation evaluation.

Run from ``backend/`` with ``python -m evals.run``. Citation checks always run.
The OCR check creates a two-page image-only PDF and measures Tesseract CER/WER;
it is marked unavailable unless local Tesseract and PDF rendering are installed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

from app.services.document_analysis import (
    PAGE_BREAK,
    ExtractedDocument,
    PageText,
    _normalize,
    extract_document,
    find_findings,
    ocr_status,
)

_CASES_PATH = Path(__file__).with_name("citation_cases.json")


def _load_cases() -> list[dict[str, Any]]:
    return json.loads(_CASES_PATH.read_text(encoding="utf-8"))


def evaluate_citations(cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Measure expected citation coverage, page accuracy, precision, and spans."""
    cases = cases if cases is not None else _load_cases()
    expected_total = matched_total = correct_page_total = 0
    predicted_total = correct_prediction_total = 0
    location_total = location_correct = 0
    case_results: list[dict[str, Any]] = []

    for case in cases:
        pages = [PageText(index + 1, content, "evaluation-fixture")
                 for index, content in enumerate(case["pages"])]
        text = PAGE_BREAK.join(page.text for page in pages)
        source = f"eval://{case['name']}"
        findings = find_findings(
            text,
            source,
            case["profile"],
            source_pages=pages,
        )
        predictions = [citation for finding in findings
                       for citation in finding.get("evidence", [])]
        predicted_total += len(predictions)

        matched = correct_page = 0
        failed: list[str] = []
        for expected in case["expected_citations"]:
            expected_total += 1
            phrase = _normalize(expected["contains"])
            same_phrase = [citation for citation in predictions
                           if phrase in _normalize(citation.get("excerpt", ""))]
            if same_phrase:
                matched += 1
                matched_total += 1
                if any(citation.get("page") == expected["page"] for citation in same_phrase):
                    correct_page += 1
                    correct_page_total += 1
                else:
                    failed.append(
                        f"{expected['contains']!r} expected on page {expected['page']}"
                    )
            else:
                failed.append(f"missing expected citation {expected['contains']!r}")

        case_correct_predictions = case_location_correct = 0
        for citation in predictions:
            page_number = citation.get("page")
            source_page = (
                pages[page_number - 1]
                if isinstance(page_number, int) and 1 <= page_number <= len(pages)
                else None
            )
            location = citation.get("location") or {}
            start, end = location.get("char_start"), location.get("char_end")
            span_valid = bool(
                source_page is not None
                and isinstance(start, int)
                and isinstance(end, int)
                and 0 <= start < end <= len(source_page.text)
                and _normalize(source_page.text[start:end]) == _normalize(citation.get("excerpt", ""))
            )
            location_total += 1
            location_correct += int(span_valid)
            case_location_correct += int(span_valid)
            if not span_valid:
                failed.append(f"invalid source span for citation on page {page_number}")

            is_correct = any(
                citation.get("page") == expected["page"]
                and _normalize(expected["contains"]) in _normalize(citation.get("excerpt", ""))
                for expected in case["expected_citations"]
            )
            case_correct_predictions += int(is_correct)
            correct_prediction_total += int(is_correct)
            if not is_correct:
                failed.append(f"unexpected citation on page {page_number}")

        case_results.append({
            "name": case["name"],
            "expected": len(case["expected_citations"]),
            "predicted": len(predictions),
            "matched": matched,
            "correct_page": correct_page,
            "correct_predictions": case_correct_predictions,
            "valid_source_locations": case_location_correct,
            "failures": failed,
        })

    citation_precision = (correct_prediction_total / predicted_total) if predicted_total else 1.0
    citation_recall = (correct_page_total / expected_total) if expected_total else 1.0
    page_accuracy = (correct_page_total / matched_total) if matched_total else 0.0
    location_accuracy = (location_correct / location_total) if location_total else 1.0
    return {
        "status": "passed" if not any(case["failures"] for case in case_results)
        and location_correct == location_total
        and correct_prediction_total == predicted_total else "failed",
        "case_count": len(cases),
        "expected_citations": expected_total,
        "predicted_citations": predicted_total,
        "citation_precision": round(citation_precision, 4),
        "citation_recall": round(citation_recall, 4),
        "page_accuracy": round(page_accuracy, 4),
        "source_location_accuracy": round(location_accuracy, 4),
        "source_locations_verified": location_correct,
        "source_locations_total": location_total,
        "cases": case_results,
    }


def _edit_distance(left: Sequence[Any], right: Sequence[Any]) -> int:
    previous = list(range(len(right) + 1))
    for i, left_item in enumerate(left, start=1):
        current = [i]
        for j, right_item in enumerate(right, start=1):
            current.append(min(
                current[-1] + 1,
                previous[j] + 1,
                previous[j - 1] + (left_item != right_item),
            ))
        previous = current
    return previous[-1]


def _error_rate(reference: Sequence[Any], actual: Sequence[Any]) -> float:
    if not reference:
        return 0.0 if not actual else 1.0
    return _edit_distance(reference, actual) / len(reference)


def character_error_rate(reference: str, actual: str) -> float:
    """Return normalized character error rate (CER)."""
    normalize = lambda value: re.sub(r"\s+", " ", value).strip().lower()
    return _error_rate(list(normalize(reference)), list(normalize(actual)))


def word_error_rate(reference: str, actual: str) -> float:
    """Return normalized word error rate (WER)."""
    normalize = lambda value: re.sub(r"\s+", " ", value).strip().lower()
    return _error_rate(normalize(reference).split(), normalize(actual).split())


def _create_scanned_pdf(path: Path) -> list[str]:
    """Create deterministic image-only PDF pages for the local OCR benchmark."""
    from PIL import Image, ImageDraw, ImageFont

    expected = [
        "KAVACH OCR evaluation. Corrosion on pump P-101 requires repair.",
        "Page two OCR evaluation. Vibration on compressor K-220; monitor weekly.",
    ]
    images = []
    font = ImageFont.load_default(size=44)
    for line in expected:
        image = Image.new("RGB", (2400, 360), "white")
        ImageDraw.Draw(image).text((70, 115), line, fill="black", font=font)
        images.append(image)
    images[0].save(
        path,
        format="PDF",
        resolution=200.0,
        save_all=True,
        append_images=images[1:],
    )
    for image in images:
        image.close()
    return expected


def evaluate_ocr() -> dict[str, Any]:
    """OCR a generated two-page scanned PDF and report CER/WER by page."""
    capabilities = ocr_status()
    if capabilities["status"] != "available":
        return {
            "status": "unavailable",
            "engine": capabilities["engine"],
            "reason": capabilities["reason"],
            "pdf_renderer_available": capabilities["pdf_renderer_available"],
        }
    if not capabilities["pdf_renderer_available"]:
        return {
            "status": "unavailable",
            "engine": capabilities["engine"],
            "reason": "PyMuPDF is required to render scanned PDF pages",
            "pdf_renderer_available": False,
        }

    try:
        with tempfile.TemporaryDirectory(prefix="kavach-ocr-eval-") as directory:
            pdf_path = Path(directory) / "synthetic-scan.pdf"
            expected = _create_scanned_pdf(pdf_path)
            extracted: ExtractedDocument = extract_document(str(pdf_path))
    except Exception as exc:  # noqa: BLE001 - report benchmark setup failures clearly
        return {
            "status": "error",
            "engine": capabilities["engine"],
            "reason": f"OCR benchmark setup failed ({type(exc).__name__})",
        }

    page_results: list[dict[str, Any]] = []
    for index, reference in enumerate(expected):
        actual = extracted.pages[index].text if index < len(extracted.pages) else ""
        page_results.append({
            "page": index + 1,
            "ocr_method": extracted.pages[index].method if index < len(extracted.pages) else "missing",
            "ocr_confidence": (extracted.pages[index].ocr_confidence
                               if index < len(extracted.pages) else None),
            "cer": round(character_error_rate(reference, actual), 4),
            "wer": round(word_error_rate(reference, actual), 4),
            "expected": reference,
            "actual": actual,
        })
    return {
        "status": "completed",
        "engine": capabilities["engine"],
        "expected_pages": len(expected),
        "extracted_pages": extracted.page_count,
        "ocr_pages": extracted.ocr_pages,
        "cer": round(sum(page["cer"] for page in page_results) / len(page_results), 4),
        "wer": round(sum(page["wer"] for page in page_results) / len(page_results), 4),
        "note": extracted.note,
        "pages": page_results,
    }


def run_suite() -> dict[str, Any]:
    citations = evaluate_citations()
    return {
        "suite": "KAVACH AI local OCR and citation evaluation",
        "version": 1,
        "citations": citations,
        "ocr": evaluate_ocr(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        help="optionally write the full JSON report to this path")
    parser.add_argument("--require-ocr", action="store_true",
                        help="exit non-zero if the local OCR engine cannot run")
    parser.add_argument("--max-cer", type=float, default=0.25,
                        help="maximum accepted character error rate (default: 0.25)")
    parser.add_argument("--max-wer", type=float, default=0.35,
                        help="maximum accepted word error rate (default: 0.35)")
    args = parser.parse_args(argv)

    report = run_suite()
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")

    if report["citations"]["status"] != "passed":
        return 1
    ocr = report["ocr"]
    if args.require_ocr and ocr["status"] != "completed":
        return 2
    if ocr["status"] == "completed" and (
        ocr["cer"] > args.max_cer or ocr["wer"] > args.max_wer
        or ocr["extracted_pages"] != ocr["expected_pages"]
    ):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
