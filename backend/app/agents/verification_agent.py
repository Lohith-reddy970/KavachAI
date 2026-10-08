"""Verification agent - cross-checks findings against cited evidence.

For an uploaded document every cited excerpt is re-checked against the document
text and the score is computed from that. For the demo scenario the score is the
fixed value defined in the scenario.
"""
from __future__ import annotations

from ..services import document_analysis, scenario
from .base import BaseAgent, RunContext


class VerificationAgent(BaseAgent):
    name = "verification_agent"

    def run(self, ctx: RunContext) -> RunContext:
        if ctx.artifacts.get("document"):
            if ctx.artifacts.get("analysis_mode") == "summary":
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
                    detail="Summary mode does not generate findings to verify.",
                )
                return ctx
            return self._run_document(ctx)

        total_evidence = sum(len(f.get("evidence", [])) for f in ctx.findings)
        backed = sum(1 for f in ctx.findings if f.get("evidence"))
        needs_review = [f for f in ctx.findings if f.get("needs_review")]

        ctx.verification_score = scenario.VERIFICATION_SCORE
        ctx.evidence_backed = scenario.EVIDENCE_BACKED
        ctx.artifacts["verification"] = {
            "score": scenario.VERIFICATION_SCORE,
            "evidence_backed": scenario.EVIDENCE_BACKED,
            "total_evidence_citations": total_evidence,
            "findings_backed": backed,
            "needs_human_review": [f["title"] for f in needs_review],
        }
        ctx.add_step(self.name, "Evidence cross-check completed",
                     detail=f"Verification score {scenario.VERIFICATION_SCORE}%; "
                            f"{scenario.EVIDENCE_BACKED} evidence-backed; "
                            f"{len(needs_review)} finding(s) flagged for human review.")
        return ctx

    def _run_document(self, ctx: RunContext) -> RunContext:
        result = document_analysis.verify_findings(
            ctx.findings, ctx.artifacts.get("document_text", ""))
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
                            f"document text (score {result['score']}%); "
                            f"{len(needs_review)} flagged for human review.")
        return ctx
