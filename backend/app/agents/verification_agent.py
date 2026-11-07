"""Cross-check every finding against the supplied source pages."""
from __future__ import annotations

from ..services import document_analysis
from .base import BaseAgent, RunContext


class VerificationAgent(BaseAgent):
    name = "verification_agent"

    def run(self, ctx: RunContext) -> RunContext:
        if ctx.artifacts.get("document"):
            summary_mode = ctx.artifacts.get("analysis_mode") == "summary"
            visual_only = bool(ctx.artifacts.get("vision_result")) and not ctx.findings
            if summary_mode or visual_only:
                ctx.verification_score = None
                ctx.evidence_backed = "n/a"
                ctx.artifacts["verification"] = {
                    "score": None,
                    "evidence_backed": "n/a",
                    "total_evidence_citations": 0,
                    "findings_backed": 0,
                    "needs_human_review": [],
                }
                ctx.add_step(
                    self.name,
                    "Verification not applicable",
                    status="skipped",
                    detail=("Summary mode does not generate findings to verify." if summary_mode
                            else "No source-cited fields or term matches were produced. Visual model observations are advisory and have not been verified against source text."),
                )
                return ctx
            return self._run_document(ctx)

        raise ValueError("A stored document is required.")

    def _run_document(self, ctx: RunContext) -> RunContext:
        result = document_analysis.verify_findings(
            ctx.findings,
            ctx.artifacts.get("document_text", ""),
            source_pages=ctx.artifacts.get("document_pages"),
        )
        unsupported = set(result.pop("unsupported"))
        for f in ctx.findings:
            if f.get("title") in unsupported:
                f["needs_review"] = 1
        needs_review = [f["title"] for f in ctx.findings if f.get("needs_review")]
        ctx.verification_score = result["score"]
        ctx.evidence_backed = result["evidence_backed"]
        ctx.artifacts["verification"] = {**result, "needs_human_review": needs_review}
        ctx.add_step(self.name, "Evidence cross-check completed",
                     detail=f"{result['evidence_backed']} finding(s) confirmed against the "
                            f"cited source pages (score {result['score']}%); "
                            f"{len(needs_review)} flagged for human review.")
        return ctx
