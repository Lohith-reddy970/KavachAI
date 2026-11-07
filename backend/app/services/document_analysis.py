"""Local document extraction, page-aware citations, and deterministic analysis.

Text-first PDFs use their embedded text. Sparse/scanned PDF pages and raster
images fall back to local Tesseract OCR when its Python wrapper and executable
are installed. Findings retain page-local character spans and, for OCR, a
normalized bounding box so a reviewer can locate the cited source passage.
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import config
from ..domains.profiles import get_profile
from ..agents.progress import ProgressCallback, publish

# Separates pages in the legacy text interface. Page-aware callers should pass
# ``PageText`` records as well so OCR tokens and extraction metadata are retained.
PAGE_BREAK = "\f"
MAX_FINDINGS = 8
MAX_FIELDS = 30
MAX_EXCERPT_CHARS = 400

_SEVERITY_ORDER = ("high", "medium", "low")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_TAG_RE = re.compile(r"\b[A-Z]{1,8}[-/]\d{2,6}(?:[-/][A-Z0-9]{1,8})*[A-Z]?\b")
_DATE_RE = re.compile(
    r"\b(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|"
    r"\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4})\b",
    re.IGNORECASE,
)
_AMOUNT_RE = re.compile(
    r"(?:[$€£₹]\s*|\b(?:USD|EUR|GBP|INR|Rs\.?)\s*)\d[\d,]*(?:\.\d{1,2})?"
    r"|\b\d[\d,]*(?:\.\d{1,2})?\s*(?:USD|EUR|GBP|INR)\b", re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_OWNER_RE = re.compile(
    r"^\s*(?:owner|assigned to|prepared by|approver|responsible person)\s*:\s*(?P<value>[^\n;]+)",
    re.IGNORECASE,
)
_MEASUREMENT_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s?(?:mm|cm|km|m|kg|g|mg|bar|psi|kpa|mpa|°c|%|"
    r"days?|hours?|years?)(?=\s|[,.;:)]|$)",
    re.IGNORECASE,
)
_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class OCRWord:
    """A Tesseract word with a page-local text span and normalized page box."""

    text: str
    start: int
    end: int
    bbox: dict[str, float]
    confidence: float


@dataclass
class PageText:
    """Extracted text and provenance for one source page."""

    number: int
    text: str
    method: str
    ocr_confidence: float | None = None
    words: list[OCRWord] = field(default_factory=list)
    ocr_attempted: bool = False


@dataclass
class ExtractedDocument:
    """All extracted pages plus a user-readable status note."""

    pages: list[PageText]
    note: str = ""

    @property
    def text(self) -> str:
        return PAGE_BREAK.join(page.text for page in self.pages)

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def ocr_pages(self) -> int:
        return sum(page.method == "tesseract" and bool(page.text.strip())
                   for page in self.pages)

    @property
    def ocr_attempted_pages(self) -> int:
        return sum(page.ocr_attempted for page in self.pages)

    @property
    def method(self) -> str:
        methods = {page.method for page in self.pages
                   if page.text.strip() and page.method != "unavailable"}
        if not methods:
            return "unavailable"
        return next(iter(methods)) if len(methods) == 1 else "mixed"

    @property
    def status(self) -> str:
        if self.text.strip():
            return "ready"
        if "OCR is not enabled" in self.note or "needs the optional" in self.note:
            return "needs_ocr"
        return "unreadable"

    def metadata(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "method": self.method,
            "page_count": self.page_count,
            "ocr_pages": self.ocr_pages,
            "ocr_attempted_pages": self.ocr_attempted_pages,
            "note": self.note,
        }


def ocr_status() -> dict[str, Any]:
    """Describe local OCR availability without making a network request."""
    try:
        import PIL.Image  # noqa: F401
    except Exception:  # noqa: BLE001 - optional dependency
        return {
            "status": "unavailable",
            "engine": "Tesseract",
            "reason": "Pillow is not installed",
            "pdf_renderer_available": False,
        }

    try:
        import pytesseract  # noqa: F401
    except Exception:  # noqa: BLE001 - optional dependency
        return {
            "status": "unavailable",
            "engine": "Tesseract",
            "reason": "the optional pytesseract package is not installed",
            "pdf_renderer_available": _pdf_renderer_available(),
        }

    executable = _tesseract_executable()
    if not executable:
        return {
            "status": "unavailable",
            "engine": "Tesseract",
            "reason": "the Tesseract executable was not found on PATH or at KAVACH_TESSERACT_CMD",
            "pdf_renderer_available": _pdf_renderer_available(),
        }
    return {
        "status": "available",
        "engine": "Tesseract",
        "reason": "",
        "pdf_renderer_available": _pdf_renderer_available(),
    }


def _pdf_renderer_available() -> bool:
    try:
        _load_pdf_renderer()
    except Exception:  # noqa: BLE001 - optional dependency
        return False
    return True


def _load_pdf_renderer() -> Any:
    """Load PyMuPDF through its current package name, with the legacy alias fallback."""
    try:
        import pymupdf

        return pymupdf
    except ImportError:
        import fitz

        return fitz


def _tesseract_executable() -> str | None:
    configured = str(config.OCR_TESSERACT_CMD or "").strip()
    if configured:
        return shutil.which(configured) or (configured if Path(configured).is_file() else None)
    return shutil.which("tesseract")


def _tesseract_data(image: Any) -> dict[str, Any]:
    import pytesseract  # type: ignore

    executable = _tesseract_executable()
    if not executable:
        raise RuntimeError("Tesseract executable is unavailable")
    pytesseract.pytesseract.tesseract_cmd = executable
    return pytesseract.image_to_data(
        image,
        lang=config.OCR_LANGUAGE,
        config=config.OCR_TESSERACT_CONFIG,
        output_type=pytesseract.Output.DICT,
    )


def _ocr_image(image: Any, page_number: int = 1) -> tuple[PageText | None, str]:
    """Run Tesseract locally and map returned word boxes back to text spans."""
    capabilities = ocr_status()
    if capabilities["status"] != "available":
        return None, f"OCR is not enabled: {capabilities['reason']}."

    try:
        data = _tesseract_data(image)
        image_width, image_height = image.size
        if not image_width or not image_height:
            raise ValueError("image has zero width or height")
        words: list[OCRWord] = []
        text_parts: list[str] = []
        cursor = 0
        previous_line: tuple[Any, ...] | None = None
        confidences: list[float] = []
        count = len(data.get("text", []))

        for index in range(count):
            token = str(data["text"][index]).strip()
            if not token:
                continue
            try:
                confidence = float(data.get("conf", [0] * count)[index])
            except (TypeError, ValueError, IndexError):
                confidence = 0.0
            if confidence < 0:
                continue

            line = tuple(data.get(key, [0] * count)[index]
                         for key in ("block_num", "par_num", "line_num"))
            if text_parts:
                separator = "\n" if line != previous_line else " "
                text_parts.append(separator)
                cursor += len(separator)
            start = cursor
            text_parts.append(token)
            cursor += len(token)
            previous_line = line

            def integer(key: str) -> int:
                try:
                    return int(float(data.get(key, [0] * count)[index]))
                except (TypeError, ValueError, IndexError):
                    return 0

            left = max(0, min(image_width, integer("left")))
            top = max(0, min(image_height, integer("top")))
            right = max(left, min(image_width, left + max(0, integer("width"))))
            bottom = max(top, min(image_height, top + max(0, integer("height"))))
            bbox = {
                "x": round(left / image_width, 6),
                "y": round(top / image_height, 6),
                "width": round((right - left) / image_width, 6),
                "height": round((bottom - top) / image_height, 6),
                "coordinate_space": "normalized",
            }
            words.append(OCRWord(token, start, cursor, bbox, confidence))
            confidences.append(confidence)

        text = "".join(text_parts).strip()
        if not text:
            return PageText(page_number, "", "tesseract", None, [], True), \
                "Tesseract OCR completed but found no readable text."
        return PageText(
            number=page_number,
            text=text,
            method="tesseract",
            ocr_confidence=round(sum(confidences) / len(confidences), 1) if confidences else None,
            words=words,
            ocr_attempted=True,
        ), ""
    except Exception as exc:  # noqa: BLE001 - optional OCR must not crash analysis
        return PageText(page_number, "", "tesseract", None, [], True), \
            f"Tesseract OCR failed ({type(exc).__name__})."


def _read_pdf_pages(path: Path) -> list[str]:
    from pypdf import PdfReader  # type: ignore

    return [page.extract_text() or "" for page in PdfReader(str(path)).pages]


def _render_pdf_page(path: Path, page_index: int) -> Any:
    """Render a PDF page to a local PIL image using the optional PyMuPDF package."""
    from PIL import Image

    fitz = _load_pdf_renderer()
    with fitz.open(str(path)) as pdf:
        page = pdf.load_page(page_index)
        pixmap = page.get_pixmap(dpi=config.OCR_DPI, alpha=False)
        return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)


def _is_sparse_pdf_text(text: str) -> bool:
    return len(re.sub(r"\W", "", text or "")) < config.OCR_MIN_PDF_TEXT_CHARS


def _extract_pdf(path: Path, on_progress: ProgressCallback | None = None) -> ExtractedDocument:
    try:
        raw_pages = _read_pdf_pages(path)
    except ImportError:
        return ExtractedDocument([], "PDF text extraction needs the optional pypdf package")
    except Exception as exc:  # noqa: BLE001 - corrupt PDFs should not 500 a run
        return ExtractedDocument([], f"could not read pdf file ({type(exc).__name__})")

    sparse_indices = [index for index, text in enumerate(raw_pages)
                      if _is_sparse_pdf_text(text)]
    sparse_index_set = set(sparse_indices)
    capabilities = ocr_status() if sparse_indices else None
    pages: list[PageText] = []
    notes: list[str] = []

    for index, raw_text in enumerate(raw_pages):
        page_number = index + 1
        operation = ("Running local OCR" if index in sparse_index_set
                     and capabilities and capabilities["status"] == "available"
                     and capabilities["pdf_renderer_available"] else "Reading embedded text")
        publish(on_progress, "extraction", "running", f"Page {page_number} of {len(raw_pages)}",
                operation, page=page_number, total_pages=len(raw_pages), pages_read=index)
        if index not in sparse_index_set:
            pages.append(PageText(page_number, raw_text, "pdf-text"))
            continue

        if capabilities and capabilities["status"] != "available":
            notes.append(f"OCR is not enabled: {capabilities['reason']}.")
            pages.append(PageText(page_number, raw_text,
                                  "pdf-text" if raw_text.strip() else "unavailable"))
            continue
        if capabilities and not capabilities["pdf_renderer_available"]:
            notes.append("PDF OCR needs the optional PyMuPDF package to render scanned pages.")
            pages.append(PageText(page_number, raw_text,
                                  "pdf-text" if raw_text.strip() else "unavailable"))
            continue

        try:
            image = _render_pdf_page(path, index)
        except Exception as exc:  # noqa: BLE001 - preserve any embedded text
            notes.append(f"Could not render PDF page {page_number} for OCR ({type(exc).__name__}).")
            pages.append(PageText(page_number, raw_text,
                                  "pdf-text" if raw_text.strip() else "unavailable"))
            continue

        try:
            ocr_page, note = _ocr_image(image, page_number)
        finally:
            close = getattr(image, "close", None)
            if close:
                close()
        if ocr_page and ocr_page.text.strip():
            pages.append(ocr_page)
        elif ocr_page:
            pages.append(PageText(
                number=page_number,
                text=raw_text,
                method="pdf-text" if raw_text.strip() else "tesseract",
                ocr_confidence=ocr_page.ocr_confidence,
                words=ocr_page.words,
                ocr_attempted=True,
            ))
            if note:
                notes.append(f"Page {page_number}: {note}")
        else:
            pages.append(PageText(page_number, raw_text,
                                  "pdf-text" if raw_text.strip() else "unavailable"))
            if note:
                notes.append(f"Page {page_number}: {note}")

    result = ExtractedDocument(pages, _join_notes(notes))
    if not result.text.strip() and not result.note:
        result.note = "The PDF contains no extractable text."
    return result


def _extract_image(path: Path) -> ExtractedDocument:
    try:
        from PIL import Image

        with Image.open(path) as source_image:
            image = source_image.convert("RGB")
    except Exception as exc:  # noqa: BLE001 - invalid image upload must not crash
        return ExtractedDocument([], f"could not read image file ({type(exc).__name__})")

    try:
        page, note = _ocr_image(image, 1)
    finally:
        image.close()
    if page is None:
        return ExtractedDocument([PageText(1, "", "unavailable")], note)
    if not page.text.strip() and not note:
        note = "Local OCR found no readable text in the image."
    return ExtractedDocument([page], note)


def _join_notes(notes: list[str]) -> str:
    unique = list(dict.fromkeys(note for note in notes if note))
    if len(unique) > 4:
        return "; ".join(unique[:4]) + f"; and {len(unique) - 4} more extraction note(s)"
    return "; ".join(unique)


def _text_pages(text: str, method: str) -> list[PageText]:
    pages = text.split(PAGE_BREAK)
    return [PageText(number=index + 1, text=page, method=method)
            for index, page in enumerate(pages)]


def extract_document(path: str, on_progress: ProgressCallback | None = None) -> ExtractedDocument:
    """Extract text page by page, using local OCR as a sparse-page fallback."""
    source = Path(path)
    if not source.is_file():
        return ExtractedDocument([], "file is missing on disk")

    doc_type = source.suffix.lstrip(".").lower()
    try:
        if doc_type in {"txt", "csv", "py"}:
            text = source.read_text(encoding="utf-8", errors="replace")
            note = "" if text.strip() else "The file contains no text."
            return ExtractedDocument(_text_pages(text, "text"), note)
        if doc_type == "docx":
            try:
                from docx import Document  # type: ignore
            except ImportError:
                return ExtractedDocument([], "DOCX text extraction needs the optional python-docx package")
            document = Document(str(source))
            blocks: list[str] = []
            for block in document.iter_inner_content():
                if hasattr(block, "rows"):
                    blocks.extend("\t".join(cell.text for cell in row.cells) for row in block.rows)
                else:
                    blocks.append(block.text)
            text = "\n".join(blocks)
            note = "" if text.strip() else "The DOCX contains no readable paragraph or table text."
            return ExtractedDocument(_text_pages(text, "docx"), note)
        if doc_type == "pdf":
            return _extract_pdf(source, on_progress)
        if doc_type in {"png", "jpg", "jpeg"}:
            return _extract_image(source)
    except Exception as exc:  # noqa: BLE001 - a corrupt upload must not 500 a run
        return ExtractedDocument([], f"could not read {doc_type} file ({type(exc).__name__})")
    return ExtractedDocument(
        [],
        f"no text extractor for .{doc_type} files; local OCR is enabled for PDFs and raster images.",
    )


def extract_text(path: str) -> tuple[str, str]:
    """Compatibility wrapper returning the page-separated text and a note."""
    extracted = extract_document(path)
    return extracted.text, extracted.note


def _normalize(text: str) -> str:
    return _SPACE_RE.sub(" ", text).strip().lower()


def _source_pages(text: str, source_pages: list[PageText] | None) -> list[PageText]:
    if source_pages:
        return source_pages
    return _text_pages(text, "text")


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = 0
    for boundary in _SENTENCE_RE.finditer(text):
        left, right = cursor, boundary.start()
        while left < right and text[left].isspace():
            left += 1
        while right > left and text[right - 1].isspace():
            right -= 1
        if right > left:
            spans.append((left, right))
        cursor = boundary.end()
    left, right = cursor, len(text)
    while left < right and text[left].isspace():
        left += 1
    while right > left and text[right - 1].isspace():
        right -= 1
    if right > left:
        spans.append((left, right))
    return spans


def _excerpt_span(text: str, start: int, end: int,
                  focus: int | None = None) -> tuple[str, int, int]:
    if end - start > MAX_EXCERPT_CHARS:
        if focus is None:
            end = start + MAX_EXCERPT_CHARS
        else:
            start = max(start, min(focus - MAX_EXCERPT_CHARS // 2,
                                   end - MAX_EXCERPT_CHARS))
            end = min(end, start + MAX_EXCERPT_CHARS)
        # Avoid ending in the middle of a word where possible.
        split_at = text.rfind(" ", start, end)
        if split_at > start + MAX_EXCERPT_CHARS // 2:
            end = split_at
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    excerpt = _SPACE_RE.sub(" ", text[start:end]).strip()
    return excerpt, start, end


def _span_location(page: PageText, start: int, end: int) -> tuple[dict[str, Any], float | None]:
    location: dict[str, Any] = {"char_start": start, "char_end": end}
    matching_words = [word for word in page.words
                      if word.start < end and word.end > start]
    if not matching_words:
        return location, None

    boxes = [word.bbox for word in matching_words]
    x0 = min(box["x"] for box in boxes)
    y0 = min(box["y"] for box in boxes)
    x1 = max(box["x"] + box["width"] for box in boxes)
    y1 = max(box["y"] + box["height"] for box in boxes)
    location["bbox"] = {
        "x": round(x0, 6),
        "y": round(y0, 6),
        "width": round(x1 - x0, 6),
        "height": round(y1 - y0, 6),
        "coordinate_space": "normalized",
    }
    confidences = [word.confidence for word in matching_words]
    ocr_confidence = round(sum(confidences) / len(confidences), 1) if confidences else None
    return location, ocr_confidence


def _citation(page: PageText, source: str, excerpt: str,
              start: int, end: int) -> dict[str, Any]:
    location, ocr_confidence = _span_location(page, start, end)
    return {
        "source": source,
        "page": page.number,
        "excerpt": excerpt,
        "confidence": 0.0,
        "location": location,
        "extraction_method": page.method,
        "ocr_confidence": ocr_confidence,
    }


def _signals(sentence: str, profile_id: str) -> tuple[str, list[str]]:
    """Return (severity, matched stems) for a sentence; severity '' if no match."""
    low = sentence.lower()
    lexicon = get_profile(profile_id).risk_terms
    hits: dict[str, list[str]] = {}
    for severity, stems in lexicon.items():
        found = [stem for stem in stems if re.search(rf"\b{re.escape(stem)}", low)]
        if found:
            hits[severity] = found
    for severity in _SEVERITY_ORDER:
        if severity in hits:
            return severity, [stem for level in _SEVERITY_ORDER for stem in hits.get(level, [])]
    return "", []


def find_findings(text: str, source: str, profile_id: str = "general", *,
                  source_pages: list[PageText] | None = None) -> list[dict]:
    """Extract profile-term findings and attach exact page-local source spans."""
    candidates: list[tuple[int, int, dict]] = []
    order = 0
    for page in _source_pages(text, source_pages):
        for start, end in _sentence_spans(page.text):
            raw_sentence = page.text[start:end]
            sentence = _SPACE_RE.sub(" ", raw_sentence).strip()
            if len(sentence) < 25:
                continue
            severity, stems = _signals(sentence, profile_id)
            if not severity:
                continue

            excerpt, excerpt_start, excerpt_end = _excerpt_span(page.text, start, end)
            # Lexical match strength, not a model probability.
            confidence = float(min(95, 60 + 10 * len(stems)))
            tags = sorted(set(_TAG_RE.findall(sentence)))
            title = excerpt if len(excerpt) <= 90 else excerpt[:87].rstrip() + "..."
            citation = _citation(page, source, excerpt, excerpt_start, excerpt_end)
            citation["confidence"] = confidence
            candidates.append((
                _SEVERITY_ORDER.index(severity),
                order,
                {
                    "title": title,
                    "description": f"Matched risk terms: {', '.join(stems)}. {excerpt}",
                    "severity": severity,
                    "confidence": confidence,
                    "equipment_id": ", ".join(tags),
                    "needs_review": 0,
                    "evidence": [citation],
                },
            ))
            order += 1
    candidates.sort(key=lambda candidate: (candidate[0], candidate[1]))
    return [candidate[2] for candidate in candidates[:MAX_FINDINGS]]


def extract_fields(text: str, source: str, *,
                   source_pages: list[PageText] | None = None) -> list[dict]:
    """Extract useful literal fields across everyday and industrial documents."""
    patterns = (
        ("reference identifier", _TAG_RE),
        ("date", _DATE_RE),
        ("amount", _AMOUNT_RE),
        ("email", _EMAIL_RE),
        ("owner / approver", _OWNER_RE),
        ("measurement", _MEASUREMENT_RE),
    )
    findings: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for page in _source_pages(text, source_pages):
        for sentence_start, sentence_end in _sentence_spans(page.text):
            raw_sentence = page.text[sentence_start:sentence_end]
            sentence = _SPACE_RE.sub(" ", raw_sentence).strip()
            if not sentence:
                continue
            for field_name, pattern in patterns:
                for match in pattern.finditer(raw_sentence):
                    value = (match.groupdict().get("value") or match.group(0)).strip()
                    key = (field_name, value.lower())
                    if key in seen:
                        continue
                    seen.add(key)

                    focus = sentence_start + match.start()
                    excerpt, excerpt_start, excerpt_end = _excerpt_span(
                        page.text, sentence_start, sentence_end, focus)
                    citation = _citation(page, source, excerpt, excerpt_start, excerpt_end)
                    citation["confidence"] = 100.0
                    findings.append({
                        "title": f"Extracted {field_name}: {value}",
                        "description": f"Literal {field_name} extracted from the source text.",
                        "severity": "info",
                        "confidence": 100.0,
                        "equipment_id": value if field_name == "reference identifier" else "",
                        "needs_review": 0,
                        "evidence": [citation],
                    })
                    if len(findings) >= MAX_FIELDS:
                        return findings
    return findings


def verify_findings(findings: list[dict], text: str, *,
                    source_pages: list[PageText] | None = None) -> dict:
    """Verify excerpts against the cited page and validate any supplied text span."""
    pages = {page.number: page.text for page in _source_pages(text, source_pages)}
    total = confirmed = backed = 0
    pages_confirmed = locations_total = locations_confirmed = 0
    unsupported: list[str] = []

    for finding in findings:
        evidence = finding.get("evidence") or []
        citation_results: list[bool] = []
        for citation in evidence:
            page_text = pages.get(citation.get("page"))
            excerpt = _normalize(str(citation.get("excerpt") or ""))
            page_ok = bool(page_text and excerpt and excerpt in _normalize(page_text))
            pages_confirmed += int(page_ok)
            location = citation.get("location") or {}
            start, end = location.get("char_start"), location.get("char_end")
            if isinstance(start, int) and isinstance(end, int):
                locations_total += 1
                span_ok = bool(
                    page_text is not None
                    and 0 <= start < end <= len(page_text)
                    and _normalize(page_text[start:end]) == excerpt
                )
                locations_confirmed += int(span_ok)
                citation_results.append(page_ok and span_ok)
            else:
                citation_results.append(page_ok)

        total += len(citation_results)
        confirmed += sum(citation_results)
        if citation_results and all(citation_results):
            backed += 1
        else:
            unsupported.append(finding.get("title", ""))

    score = round(100.0 * confirmed / total, 1) if total else 0.0
    page_accuracy = round(100.0 * pages_confirmed / total, 1) if total else 0.0
    location_accuracy = (round(100.0 * locations_confirmed / locations_total, 1)
                         if locations_total else None)
    return {
        "score": score,
        "evidence_backed": f"{backed}/{len(findings)}",
        "total_evidence_citations": total,
        "findings_backed": backed,
        "page_citations_verified": pages_confirmed,
        "page_citation_accuracy": page_accuracy,
        "locations_verified": locations_confirmed,
        "total_source_locations": locations_total,
        "location_accuracy": location_accuracy,
        "unsupported": unsupported,
    }
