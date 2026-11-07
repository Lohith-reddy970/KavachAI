"""Document agent - loads and locally extracts the documents a run will use."""
from __future__ import annotations

from .base import BaseAgent, RunContext


class DocumentAgent(BaseAgent):
    name = "document_agent"

    def run(self, ctx: RunContext) -> RunContext:
        uploaded = ctx.artifacts.get("document")
        if uploaded:
            text = ctx.artifacts.get("document_text", "")
            extraction = ctx.artifacts.get("document_extraction", {})
            ctx.artifacts["documents"] = [uploaded["filename"]]
            ctx.add_step(self.name, "Uploaded document loaded",
                         detail=(f"Loaded {uploaded['filename']} ({extraction.get('page_count', 0)} page(s), "
                                 f"{len(text)} extracted characters; method={extraction.get('method', 'unknown')})."))
            attempted = int(extraction.get("ocr_attempted_pages", 0))
            ocr_pages = int(extraction.get("ocr_pages", 0))
            if attempted:
                ctx.add_step(
                    self.name,
                    "OCR completed" if ocr_pages else "OCR found no readable text",
                    status="completed" if ocr_pages else "warning",
                    detail=(f"Local Tesseract OCR returned text on {ocr_pages} of "
                            f"{attempted} attempted page(s)."),
                )
            note = ctx.artifacts.get("document_note", "")
            if text.strip():
                detail = ("Locally extracted text and page provenance are available "
                          "to downstream agents; no external upload performed.")
                if note:
                    detail += f" Extraction note: {note}"
                ctx.add_step(self.name, "Document analysis prepared",
                             detail=detail)
            else:
                ctx.add_step(self.name, "No text extracted", status="warning",
                             detail=f"Nothing to analyse: {note or 'the document is empty'}.")
            return ctx

        raise ValueError("A stored document is required.")
