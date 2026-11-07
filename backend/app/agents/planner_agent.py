"""Planner agent - chooses the next action for a bounded agentic run.

The planner inspects the shared ``RunContext`` and returns one of a fixed set of
actions. Which actions are *eligible* is decided deterministically from the run
state, so prerequisites cannot be skipped (no reasoning before evidence is
gathered, no finish before verification and the human-review gate).

The local model may select among eligible actions; invalid choices use the
first eligible action. Provider errors remain visible.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .. import config
from ..database import db
from ..models.providers import generate, get_provider
from ..models.router import classify
from . import orchestrator, review_gate
from .base import RunContext
from .security_agent import SecurityAgent
from .deliverable_agent import DeliverableAgent
from .tools import MAX_QUERY_CHARS, REGISTRY, ToolError, ToolRegistry
from .progress import ProgressCallback, complete_stage, publish

FINISH = "finish"
ACTIONS = ("search_knowledge", "inspect_document", "analyze_pid", "reason",
           "verify", "human_review", FINISH)


@dataclass(frozen=True)
class PlannerDecision:
    action: str
    reason: str
    args: dict[str, Any] = field(default_factory=dict)


class PlannerAgent:
    name = "planner_agent"

    def candidates(self, ctx: RunContext) -> list[PlannerDecision]:
        """Eligible next actions for the current state, preferred first."""
        art = ctx.artifacts
        if not art.get("reasoned"):
            gather: list[PlannerDecision] = []
            if "documents" not in art:
                gather.append(PlannerDecision(
                    "inspect_document", "Documents have not been loaded yet."))
            image_input = art.get("document", {}).get("filename", "").lower().endswith((".png", ".jpg", ".jpeg"))
            if "vision_checked" not in art and (classify(ctx.task_text) == "vision" or image_input):
                gather.append(PlannerDecision(
                    "analyze_pid", "Task references an image; visual analysis has not run yet."))
            if "retrieved" not in art:
                gather.append(PlannerDecision(
                    "search_knowledge", "No supporting knowledge retrieved yet.",
                    {"query": ctx.task_text.strip()[:MAX_QUERY_CHARS], "top_k": 4}))
            if gather:
                return gather
            return [PlannerDecision("reason", "Evidence gathered; ready to synthesize findings.")]
        if "verification" not in art:
            return [PlannerDecision("verify", "Findings exist but are not verified.")]
        if art["verification"].get("review_required") and "human_review" not in art:
            return [PlannerDecision(
                "human_review", "High-risk or unsupported findings require human approval.")]
        return [PlannerDecision(FINISH, "All required steps are complete.")]

    def next_action(self, ctx: RunContext) -> PlannerDecision:
        options = self.candidates(ctx)
        if len(options) > 1:
            return self._llm_choice(ctx, options)
        return options[0]

    def _llm_choice(self, ctx: RunContext, options: list[PlannerDecision]) -> PlannerDecision:
        names = [o.action for o in options]
        prompt = (
            "You are a planner for a local document analysis assistant.\n"
            f"Task: {ctx.task_text[:MAX_QUERY_CHARS]}\n"
            f"Choose the single best next action from: {', '.join(names)}.\n"
            "Reply with only the action name."
        )
        result = generate(prompt, role="other")
        reply = result.text.lower()
        picked = [o for o in options if o.action in reply]
        if len(picked) == 1:
            return picked[0]
        return options[0]


def _clamp_steps(max_steps: int | None) -> int:
    return max(1, min(max_steps or config.PLANNER_MAX_STEPS, config.PLANNER_HARD_STEP_CAP))


def run_agentic(task_text: str, max_steps: int | None = None,
                planner: PlannerAgent | None = None,
                registry: ToolRegistry | None = None, *, document: dict | None = None,
                profile: str = "general", analysis_mode: str = "risk_review",
                on_progress: ProgressCallback | None = None) -> dict:
    if not document:
        raise ValueError("A stored document is required for planner runs.")
    from ..services.document_store import use_document
    with use_document(document["id"]):
        return _run_agentic(task_text, max_steps, planner, registry, document=document,
                            profile=profile, analysis_mode=analysis_mode, on_progress=on_progress)


def _run_agentic(task_text: str, max_steps: int | None = None,
                 planner: PlannerAgent | None = None,
                 registry: ToolRegistry | None = None, *, document: dict | None = None,
                 profile: str = "general", analysis_mode: str = "risk_review",
                 on_progress: ProgressCallback | None = None) -> dict:
    """Run the bounded planner loop, persist the trace and return the run dict.

    Stops on ``finish``, on reaching ``max_steps``, when the planner repeats an
    action it already ran (loop protection), or when a tool call is rejected.
    Any stop other than ``finish`` halts the run and escalates all findings to
    human review.
    """
    if not document:
        raise ValueError("A stored document is required for planner runs.")
    from ..services.analysis import prepare_document
    publish(on_progress, "validation", "completed", "Document and planner settings checked",
            document["filename"], profile=profile, mode=analysis_mode)
    document, extraction = prepare_document(document, on_progress)
    planner = planner or PlannerAgent()
    registry = registry or REGISTRY
    limit = _clamp_steps(max_steps)

    run_id = db.insert("agent_runs", {
        "task_id": None,
        "scenario": "agentic",
        "status": "running",
        "verification_score": 0,
        "evidence_backed": "",
        "started_at": orchestrator._now(),
    })
    ctx = RunContext(task_text=task_text, scenario="agentic", on_progress=on_progress)
    if on_progress:
        on_progress({"type": "run", "run_id": run_id})
    ctx.artifacts.update({
        "run_id": run_id, "document": document, "document_text": extraction.text,
        "document_note": extraction.note, "document_pages": extraction.pages,
        "document_extraction": extraction.metadata(), "analysis_profile": profile,
        "analysis_mode": analysis_mode,
    })

    trace: list[dict[str, Any]] = []
    seen: set[str] = set()
    stop_reason = "max_steps_reached"
    current_stage = "routing"
    try:
        publish(on_progress, "routing", "running", "Checking local provider policy")
        SecurityAgent().run(ctx)
        for step_no in range(1, limit + 1):
            current_stage = "routing"
            publish(on_progress, "routing", "running", "Choosing the next permitted action",
                    f"Planner step {step_no} of {limit}")
            decision = planner.next_action(ctx)
            entry = {"step": step_no, "action": decision.action,
                     "reason": decision.reason, "args": decision.args, "status": "completed"}
            trace.append(entry)
            ctx.add_step(planner.name, f"Planner chose: {decision.action}",
                         detail=decision.reason)
            complete_stage(on_progress, "routing", ctx.steps[-1:])
            if decision.action == FINISH:
                stop_reason = "finished"
                break
            signature = decision.action + json.dumps(decision.args, sort_keys=True, default=str)
            if signature in seen:
                entry["status"] = "blocked"
                stop_reason = "loop_detected"
                break
            seen.add(signature)
            current_stage = {"inspect_document": "routing", "analyze_pid": "vision",
                             "search_knowledge": "knowledge", "reason": "reasoning",
                             "verify": "verification", "human_review": "verification"}.get(decision.action, "routing")
            publish(on_progress, current_stage, "running", f"Executing {decision.action}", decision.reason)
            stage_start = len(ctx.steps)
            try:
                registry.execute(decision.action, ctx, decision.args)
                complete_stage(on_progress, current_stage, ctx.steps[stage_start:])
            except ToolError as exc:
                entry["status"] = "rejected"
                entry["error"] = str(exc)
                stop_reason = "tool_rejected"
                break
    except Exception as exc:  # noqa: BLE001
        ctx.add_step(planner.name, "Agentic run failed", status="error", detail=repr(exc))
        orchestrator._persist_steps(run_id, ctx)
        db.execute("UPDATE agent_runs SET status=?, finished_at=? WHERE id=?",
                   ("error", orchestrator._now(), run_id))
        publish(on_progress, current_stage, "error", "Agentic run failed", str(exc))
        raise

    # Final gate, independent of what the planner did: nothing high-risk,
    # unsupported or unverified leaves the loop without a review flag.
    finished = stop_reason == "finished"
    verified = "verification" in ctx.artifacts
    review_required = review_gate.apply(ctx.findings, verified=verified)
    if not finished:
        for f in ctx.findings:
            f["needs_review"] = 1
        ctx.add_step(planner.name, "Run halted - escalated to human review",
                     status="halted", detail=f"stop_reason={stop_reason}; limit={limit} steps.")
        status = "halted"
    elif review_required:
        status = "awaiting_review"
    else:
        status = "completed"

    if finished and verified and ctx.artifacts.get("reasoned"):
        publish(on_progress, "deliverables", "running", "Generating and saving report files")
        try:
            DeliverableAgent().run(ctx)
        except Exception as exc:
            ctx.add_step("deliverable_agent", "Report generation failed", status="error", detail=repr(exc))
            orchestrator._persist_steps(run_id, ctx)
            db.execute("UPDATE agent_runs SET status='error', finished_at=? WHERE id=?",
                       (orchestrator._now(), run_id))
            raise
    orchestrator._persist_steps(run_id, ctx)
    orchestrator._persist_results(run_id, ctx)
    orchestrator._finalize(run_id, ctx, status)
    if ctx.artifacts.get("deliverables"):
        publish(on_progress, "deliverables", "completed", "Reports and run saved")

    run = orchestrator.get_run(run_id) or {}
    run["planner"] = {
        "provider": get_provider().name,
        "max_steps": limit,
        "steps_used": len(trace),
        "stop_reason": stop_reason,
        "trace": trace,
        "requires_human_review": bool(review_required) or not finished,
        "review_required": review_required,
        "allowed_tools": registry.names(),
    }
    return run
