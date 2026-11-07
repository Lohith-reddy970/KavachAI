"""Base primitives for KAVACH AI agents.

Every agent is a small deterministic unit that reads/writes a shared
``RunContext``. Agents append ``StepResult`` records describing what they did,
recording the operations performed on the supplied document.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from .progress import AGENT_STAGES, ProgressCallback


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class StepResult:
    agent: str
    message: str
    status: str = "completed"
    detail: str = ""
    started_at: str = ""
    finished_at: str = ""


@dataclass
class RunContext:
    """Mutable state threaded through the orchestration."""

    task_text: str = ""
    scenario: str = "document"
    steps: list[StepResult] = field(default_factory=list)
    findings: list[dict] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
    routing: dict[str, Any] = field(default_factory=dict)
    verification_score: float | None = 0.0
    evidence_backed: str = ""
    on_progress: ProgressCallback | None = None

    def add_step(self, agent: str, message: str, status: str = "completed",
                 detail: str = "") -> StepResult:
        started = utcnow()
        step = StepResult(
            agent=agent,
            message=message,
            status=status,
            detail=detail,
            started_at=started,
            finished_at=utcnow(),
        )
        self.steps.append(step)
        if self.on_progress:
            self.on_progress({"type": "log", "stage": AGENT_STAGES.get(agent, "routing"),
                              "state": status, "message": message, "detail": detail})
        return step


class BaseAgent:
    """Common interface for all agents."""

    name: str = "base_agent"

    def run(self, ctx: RunContext) -> RunContext:  # pragma: no cover - overridden
        raise NotImplementedError
