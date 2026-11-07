"""Verify saved excerpts against their current source and locate highlights."""
from __future__ import annotations

from ..database import db
from ..schemas.schemas import PassageRequest
from . import document_analysis as extraction
from .document_store import DocumentAccessError, DocumentNotFound, source_file, use_document


def for_evidence(evidence_id: int) -> dict:
    evidence = db.fetch_one("SELECT * FROM evidence WHERE id=?", (evidence_id,))
    if not evidence:
        raise DocumentNotFound("Evidence not found")
    doc_id = evidence.get("document_id")
    if not doc_id:
        job = db.fetch_one("SELECT document_id FROM analysis_jobs WHERE run_id=? LIMIT 1", (evidence["run_id"],))
        doc_id = job["document_id"] if job else None
    if not doc_id:
        raise DocumentAccessError("This older finding has no stored document link. Re-analyze the source to create highlightable evidence.")
    location = db.loads(evidence.get("location_json")) or {}
    return passage(doc_id, PassageRequest(page=evidence["page"] or 1, excerpt=evidence["excerpt"],
                                          char_start=location.get("char_start"), char_end=location.get("char_end")))


def passage(doc_id: int, payload: PassageRequest) -> dict:
    with use_document(doc_id):
        document, path, _ = source_file(doc_id)
        extracted = extraction.extract_document(str(path))
        page = next((p for p in extracted.pages if p.number == payload.page), None)
        if not page:
            raise DocumentAccessError("This source page has no readable text or is no longer available.")
        text, quote = page.text, payload.excerpt
        start, end = payload.char_start, payload.char_end
        if start is None or end is None or text[start:end] != quote:
            start = text.find(quote)
            end = start + len(quote)
        if start < 0 or not quote.strip():
            raise DocumentAccessError("The saved excerpt no longer matches the current source. Re-analyze the document before using this citation.")
        boxes = []
        note = ""
        if page.words:
            boxes = [w.bbox for w in page.words if w.start < end and w.end > start][:500]
        elif path.suffix.lower() == ".pdf":
            try:
                fitz = extraction._load_pdf_renderer()
                with fitz.open(str(path)) as pdf:
                    pdf_page = pdf.load_page(payload.page - 1)
                    rect = pdf_page.rect
                    for found in pdf_page.search_for(quote)[:100]:
                        found = found * pdf_page.rotation_matrix
                        boxes.append({"x": found.x0 / rect.width, "y": found.y0 / rect.height,
                                      "width": found.width / rect.width, "height": found.height / rect.height})
            except Exception:
                note = "The original page could not be located visually. The verified passage is highlighted in the extracted text."
        image = path.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg"}
        begin, finish = max(0, start - 3500), min(len(text), end + 3500)
        return {"document_id": doc_id, "filename": document["filename"], "page": payload.page,
                "page_label": f"Page {payload.page}" if image else f"Text section {payload.page}",
                "text": text[begin:finish], "highlight_start": start - begin, "highlight_end": end - begin,
                "excerpt": quote, "boxes": boxes, "has_image": image, "note": note,
                "truncated": begin > 0 or finish < len(text)}


def page_image(doc_id: int, page_number: int) -> bytes:
    with use_document(doc_id):
        _, path, _ = source_file(doc_id)
        if page_number < 1:
            raise DocumentNotFound("Page not found")
        try:
            if path.suffix.lower() == ".pdf":
                fitz = extraction._load_pdf_renderer()
                with fitz.open(str(path)) as pdf:
                    if page_number > len(pdf):
                        raise DocumentNotFound("Page not found")
                    page = pdf.load_page(page_number - 1)
                    scale = min(1.5, 1600 / max(page.rect.width, page.rect.height))
                    return page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).tobytes("png")
            if path.suffix.lower() in {".png", ".jpg", ".jpeg"} and page_number == 1:
                from io import BytesIO
                from PIL import Image
                with Image.open(path) as image:
                    output = BytesIO()
                    image.thumbnail((1600, 1600))
                    image.convert("RGB").save(output, format="PNG")
                    return output.getvalue()
        except DocumentNotFound:
            raise
        except Exception as exc:
            raise DocumentAccessError("The original page cannot be rendered. Use the highlighted text or download the original.") from exc
        raise DocumentNotFound("An image preview is not available for this source section.")
