"""Planner agent - chooses the next action for a bounded agentic run.

The planner inspects the shared ``RunContext`` and returns one of a fixed set of
actions. Which actions are *eligible* is decided deterministically from the run
state, so prerequisites cannot be skipped (no reasoning before evidence is
gathered, no finish before verification and the human-review gate).

With the default ``MockLocalModelProvider`` the choice is fully deterministic.
When a local LLM (Ollama) is enabled it may only pick among the eligible
actions; anything else falls back to the deterministic choice.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .. import config
from ..database import db
from ..models.providers import DEFAULT_PROVIDER, generate_with_fallback, get_provider
from ..models.router import classify
from . import orchestrator, review_gate
from .base import RunContext
from .security_agent import SecurityAgent
from .tools import MAX_QUERY_CHARS, REGISTRY, ToolError, ToolRegistry

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
        if not ctx.findings:
            gather: list[PlannerDecision] = []
            if "documents" not in art:
                gather.append(PlannerDecision(
                    "inspect_document", "Documents have not been loaded yet."))
            if "pid_regions" not in art and classify(ctx.task_text) == "vision":
                gather.append(PlannerDecision(
                    "analyze_pid", "Task references a P&ID/diagram; regions not analysed yet."))
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
        if len(options) > 1 and get_provider().name != DEFAULT_PROVIDER:
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
        result = generate_with_fallback(prompt, role="other")
        if result.provider != DEFAULT_PROVIDER:
            reply = result.text.lower()
            picked = [o for o in options if o.action in reply]
            # Accept only an unambiguous choice among the eligible actions.
            if len(picked) == 1:
                return picked[0]
        return options[0]


def _clamp_steps(max_steps: int | None) -> int:
    return max(1, min(max_steps or config.PLANNER_MAX_STEPS, config.PLANNER_HARD_STEP_CAP))


def run_agentic(task_text: str, max_steps: int | None = None,
                planner: PlannerAgent | None = None,
                registry: ToolRegistry | None = None) -> dict:
    """Run the bounded planner loop, persist the trace and return the run dict.

    Stops on ``finish``, on reaching ``max_steps``, when the planner repeats an
    action it already ran (loop protection), or when a tool call is rejected.
    Any stop other than ``finish`` halts the run and escalates all findings to
    human review.
    """
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
    ctx = RunContext(task_text=task_text, scenario="agentic")
    ctx.artifacts["run_id"] = run_id

    trace: list[dict[str, Any]] = []
    seen: set[str] = set()
    stop_reason = "max_steps_reached"
    try:
        SecurityAgent().run(ctx)
        for step_no in range(1, limit + 1):
            decision = planner.next_action(ctx)
            entry = {"step": step_no, "action": decision.action,
                     "reason": decision.reason, "args": decision.args, "status": "completed"}
            trace.append(entry)
            ctx.add_step(planner.name, f"Planner chose: {decision.action}",
                         detail=decision.reason)
            if decision.action == FINISH:
                stop_reason = "finished"
                break
            signature = decision.action + json.dumps(decision.args, sort_keys=True, default=str)
            if signature in seen:
                entry["status"] = "blocked"
                stop_reason = "loop_detected"
                break
            seen.add(signature)
            try:
                registry.execute(decision.action, ctx, decision.args)
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

    orchestrator._persist_steps(run_id, ctx)
    orchestrator._persist_results(run_id, ctx)
    orchestrator._finalize(run_id, ctx, status)

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
