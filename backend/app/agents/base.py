"""Base primitives for KAVACH AI agents.

Every agent is a small deterministic unit that reads/writes a shared
``RunContext``. Agents append ``StepResult`` records describing what they did,
matching the required demo vibe (e.g. "Documents loaded", "OCR completed").
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


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
    scenario: str = "refinery_inspection"
    steps: list[StepResult] = field(default_factory=list)
    findings: list[dict] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
    routing: dict[str, Any] = field(default_factory=dict)
    verification_score: float | None = 0.0
    evidence_backed: str = ""

    def add_step(self, agent: str, message: str, status: str = "completed",
                 detail: str = "") -> StepResult:
        started = utcnow()
        # Tiny deterministic-ish pause for realistic timestamps (kept minimal).
        time.sleep(0.01)
        step = StepResult(
            agent=agent,
            message=message,
            status=status,
            detail=detail,
            started_at=started,
            finished_at=utcnow(),
        )
        self.steps.append(step)
        return step


class BaseAgent:
    """Common interface for all agents."""

    name: str = "base_agent"

    def run(self, ctx: RunContext) -> RunContext:  # pragma: no cover - overridden
        raise NotImplementedError
