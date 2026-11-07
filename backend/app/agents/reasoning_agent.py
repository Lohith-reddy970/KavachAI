"""Review, summarize, and extract fields from supplied documents."""
from __future__ import annotations

from .. import config
from ..domains.profiles import get_profile
from ..models.providers import InferenceUnavailable, generate, model_for_role, active_provider_name
from .progress import publish
from ..services import document_analysis
from . import review_gate
from .base import BaseAgent, RunContext


class ReasoningAgent(BaseAgent):
    name = "reasoning_agent"

    def run(self, ctx: RunContext) -> RunContext:
        uploaded = ctx.artifacts.get("document")
        if uploaded:
            return self._run_document(ctx, uploaded["filename"])

        raise ValueError("A stored document is required.")

    def _run_document(self, ctx: RunContext, filename: str) -> RunContext:
        text = ctx.artifacts.get("document_text", "")
        profile = ctx.artifacts.get("analysis_profile", "general")
        mode = ctx.artifacts.get("analysis_mode", "risk_review")
        source_pages = ctx.artifacts.get("document_pages")
        status = "completed"

        if mode == "summary":
            if ctx.artifacts.get("vision_analysis"):
                self._capture_visual_summary(ctx)
            elif text.strip():
                self._capture_analysis(ctx, source_text=text, mode=mode)
            else:
                status = "warning"
            findings = []
        elif mode == "extract_fields":
            findings = document_analysis.extract_fields(
                text, filename, source_pages=source_pages)
            if not text.strip():
                status = "warning"
        else:
            if text.strip():
                try:
                    self._capture_analysis(ctx, source_text=text, mode=mode)
                except InferenceUnavailable as exc:
                    ctx.add_step(self.name, "Advisory model analysis unavailable", status="warning",
                                 detail=str(exc) + " Source-term review continues.")
                findings = document_analysis.find_findings(
                    text, filename, profile, source_pages=source_pages)
            else:
                findings = []
                status = "warning"

        # Same approval rules as agentic runs; the cited source is the document itself.
        for f in findings:
            reasons = review_gate.review_reasons(f, {filename.lower()})
            low_ocr_confidences = [
                float(ev["ocr_confidence"])
                for ev in f.get("evidence", [])
                if ev.get("ocr_confidence") is not None
                and float(ev["ocr_confidence"]) < config.OCR_REVIEW_MIN_CONFIDENCE
            ]
            if low_ocr_confidences:
                reasons.append(
                    f"low OCR confidence ({min(low_ocr_confidences):g}% < "
                    f"{config.OCR_REVIEW_MIN_CONFIDENCE:g}%)"
                )
            if reasons:
                f["needs_review"] = 1
                f["review_reasons"] = reasons
        ctx.findings = findings
        ctx.evidence = [{**ev, "finding_title": f["title"]}
                        for f in findings for ev in f["evidence"]]
        if mode == "risk_review":
            if text.strip():
                extraction = ctx.artifacts.get("document_extraction", {})
                provenance = (f" Local Tesseract OCR supplied {extraction.get('ocr_pages', 0)} page(s)."
                              if extraction.get("ocr_pages") else "")
                detail = (f"profile={profile}; mode={mode}; matched {len(findings)} source sentences. "
                          "Model analysis is advisory and does not override source-matched findings."
                          f"{provenance}")
                message = "Profile-based risk review completed"
            else:
                detail = (f"{ctx.artifacts.get('document_note') or 'No text was extracted.'} "
                          "Image inspection is shown separately; source-cited risk matching requires readable OCR text."
                          if ctx.artifacts.get("vision_analysis") else
                          f"{ctx.artifacts.get('document_note') or 'No text was extracted.'} "
                          "Provide a text-readable document for source-cited risk matching.")
                message = "Image inspected; no OCR text for risk matching" if ctx.artifacts.get("vision_analysis") else "Risk review requires extracted text"
        elif mode == "summary":
            detail = (f"profile={profile}; mode={mode}; summary output is available in "
                      "the analysis trace and generated report." if ctx.artifacts.get("reasoning_analysis")
                      else ctx.artifacts.get("document_note") or "No text or image content was available to summarize.")
            message = "Document summary completed" if ctx.artifacts.get("reasoning_analysis") else "No summary content available"
            if not ctx.artifacts.get("reasoning_analysis"):
                status = "warning"
        else:
            detail = (f"profile={profile}; mode={mode}; extracted {len(findings)} "
                      "literal fields with source excerpts." if text.strip()
                      else ctx.artifacts.get("document_note") or "No text was extracted.")
            message = "Field extraction completed" if text.strip() else "Field extraction requires extracted text"
        ctx.add_step(self.name, message, status=status, detail=detail)
        return ctx

    def _capture_visual_summary(self, ctx: RunContext) -> None:
        text = ctx.artifacts["vision_analysis"]
        model = ctx.artifacts.get("vision_model", "vision model")
        provider = ctx.artifacts.get("vision_provider", "unknown")
        ctx.artifacts["reasoning_analysis"] = {
            "model": model,
            "provider": provider,
            "text": text,
            "meta": {"source": "vision"},
        }
        excerpt = " ".join(text.split())[:1200]
        ctx.add_step(
            self.name,
            "Visual summary captured",
            detail=f"model={model}; provider={provider}; advisory output: {excerpt}",
        )

    def _capture_analysis(self, ctx: RunContext, source_text: str = "",
                          mode: str = "risk_review") -> None:
        profile = get_profile(ctx.artifacts.get("analysis_profile", "general"))
        retrieved = ctx.artifacts.get("retrieved", [])
        excerpts = [
            f"[{item.get('source')} p.{item.get('page')}] {item.get('text', '')}"
            for item in retrieved[:8]
        ]
        vision = ctx.artifacts.get("vision_analysis", "")
        if mode == "summary":
            instruction = (
                "Summarize the document's purpose, key points, dates, decisions, and "
                "open questions using only the supplied text. Keep the summary concise "
                "and state when information is unclear. Do not invent facts."
            )
        else:
            instruction = (
                "Analyze the document for potential risks using only the supplied material. "
                "Return a concise rationale and clearly state uncertainty. Do not invent "
                "measurements, equipment tags, or evidence. This is advisory analysis, "
                "not an approval."
            )
        prompt = (
            f"{instruction}\n\n"
            f"Domain profile: {profile.name}. {profile.description}\n\n"
            f"Task: {ctx.task_text[:2000]}\n\n"
            f"Document text (truncated): {source_text[:6000]}\n\n"
            f"Visual analysis: {str(vision)[:2000]}\n\n"
            "Retrieved evidence:\n" + ("\n".join(excerpts) or "(none)")
        )
        publish(ctx.on_progress, "reasoning", "running", "Generating local model analysis",
                "The configured local model is processing the source and retrieved passages.",
                model=model_for_role("reasoning"), provider=active_provider_name())
        result = generate(prompt, role="reasoning")
        ctx.artifacts["reasoning_analysis"] = {
            "model": result.model,
            "provider": result.provider,
            "text": result.text,
            "meta": result.meta,
        }
        excerpt = " ".join(result.text.split())[:1200 if mode == "summary" else 360]
        ctx.add_step(
            self.name,
            "Document summary generated" if mode == "summary" else "Reasoning analysis captured",
            detail=f"mode={mode}; model={result.model}; provider={result.provider}; "
                   f"advisory output (not independently verified): {excerpt}",
        )
