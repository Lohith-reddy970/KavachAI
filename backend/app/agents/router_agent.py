"""Router agent - classifies the task and selects the local model.

Delegates to the deterministic model router and records the routing decision,
then performs lightweight planning (the plan follows the selected document analysis mode).
"""
from __future__ import annotations

from ..models.router import route
from .base import BaseAgent, RunContext


class RouterAgent(BaseAgent):
    name = "router_agent"

    def run(self, ctx: RunContext) -> RunContext:
        decision = route(ctx.task_text or "review the document for issues and source evidence")
        ctx.routing = {
            "task_type": decision.task_type,
            "model": decision.model,
            "reason": decision.reason,
            "confidence": decision.confidence,
        }
        ctx.add_step(
            self.name,
            f"Task routed to {decision.model}",
            detail=f"task_type={decision.task_type}; {decision.reason}",
        )
        # Planner sub-step (fixed multi-step document plan).
        profile = ctx.artifacts.get("analysis_profile", "general")
        mode = ctx.artifacts.get("analysis_mode", "risk_review")
        document = ctx.artifacts.get("document")
        plan = ["Parse source text and retain page provenance; OCR sparse pages if needed"]
        if document and document["filename"].lower().endswith((".png", ".jpg", ".jpeg")):
            plan.append("Inspect the supplied image with the local vision model; retain OCR fields separately")
        else:
            plan.append("Bypass vision: the selected analysis uses extracted text")
        plan.extend([
            "Chunk source text and retrieve local context using embeddings and cosine similarity",
            "Generate an advisory summary" if mode == "summary" else
            "Extract literal fields with source citations" if mode == "extract_fields" else
            "Assemble source-backed findings; retain model reasoning as advisory output",
            "Cross-check cited excerpts; apply severity, confidence, and explicit-review gates",
            "Generate local deliverables and persist the auditable run trace",
        ])
        ctx.artifacts["plan"] = plan
        ctx.add_step(self.name, "Execution plan created",
                     detail="; ".join(f"{i+1}. {p}" for i, p in enumerate(plan)))
        return ctx
