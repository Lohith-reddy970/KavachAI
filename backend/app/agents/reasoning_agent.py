"""Reasoning agent - synthesizes findings from documents, vision and knowledge.

For the sample scenario it emits the canonical, deterministic finding set defined
in the scenario. Uploaded documents support profile-aware risk review, summary,
and literal field extraction.
"""
from __future__ import annotations

from ..domains.profiles import get_profile
from ..models.providers import generate_with_fallback
from ..services import document_analysis, scenario
from . import review_gate
from .base import BaseAgent, RunContext


class ReasoningAgent(BaseAgent):
    name = "reasoning_agent"

    def run(self, ctx: RunContext) -> RunContext:
        uploaded = ctx.artifacts.get("document")
        if uploaded:
            return self._run_document(ctx, uploaded["filename"])

        # Capture a grounded model analysis. The sample-scenario findings remain the
        # canonical fictional fixture, rather than being replaced by free-form output.
        self._capture_analysis(ctx)

        findings: list[dict] = []
        evidence: list[dict] = []
        for f in scenario.FINDINGS:
            finding = {
                "title": f["title"],
                "description": f["description"],
                "severity": f["severity"],
                "confidence": f["confidence"],
                "equipment_id": f["equipment_id"],
                "needs_review": f["needs_review"],
                "evidence": f["evidence"],
            }
            findings.append(finding)
            for ev in f["evidence"]:
                evidence.append({**ev, "finding_title": f["title"]})

        ctx.findings = findings
        ctx.evidence = evidence
        ctx.add_step(self.name, "Findings generated",
                     detail=f"Generated {len(findings)} findings with "
                            f"{len(evidence)} evidence citations.")
        return ctx

    def _run_document(self, ctx: RunContext, filename: str) -> RunContext:
        text = ctx.artifacts.get("document_text", "")
        profile = ctx.artifacts.get("analysis_profile", "general")
        mode = ctx.artifacts.get("analysis_mode", "risk_review")
        status = "completed"

        if mode == "summary":
            if text.strip():
                self._capture_analysis(ctx, source_text=text, mode=mode)
            elif ctx.artifacts.get("vision_analysis"):
                self._capture_visual_summary(ctx)
            else:
                status = "warning"
            findings = []
        elif mode == "extract_fields":
            findings = document_analysis.extract_fields(text, filename)
            if not text.strip():
                status = "warning"
        else:
            if text.strip():
                self._capture_analysis(ctx, source_text=text, mode=mode)
                findings = document_analysis.find_findings(text, filename, profile)
            else:
                findings = []
                status = "warning"

        # Same approval rules as agentic runs; the cited source is the document itself.
        for f in findings:
            reasons = review_gate.review_reasons(f, {filename.lower()})
            if reasons:
                f["needs_review"] = 1
                f["review_reasons"] = reasons
        ctx.findings = findings
        ctx.evidence = [{**ev, "finding_title": f["title"]}
                        for f in findings for ev in f["evidence"]]
        if mode == "risk_review":
            if text.strip():
                detail = (f"profile={profile}; mode={mode}; matched {len(findings)} source sentences. "
                          "Model analysis is advisory and does not override source-matched findings.")
                message = "Profile-based risk review completed"
            else:
                detail = (f"{ctx.artifacts.get('document_note') or 'No text was extracted.'} "
                          "Choose Summary for an image description or provide a text-readable document.")
                message = "Risk review requires extracted text"
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
        result = generate_with_fallback(prompt, role="reasoning")
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
