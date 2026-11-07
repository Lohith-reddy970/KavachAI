"""Progress events emitted by actual document operations."""
from __future__ import annotations

from typing import Callable

ProgressCallback = Callable[[dict], None]

STAGES = (
    ("validation", "Check document", "Validate the stored source and analysis settings."),
    ("extraction", "Extract text / OCR", "Read source pages and use local OCR where needed."),
    ("routing", "Plan analysis", "Check provider policy, select models, and prepare the document."),
    ("vision", "Inspect images", "Describe visual input when the selected task needs it."),
    ("knowledge", "Retrieve context", "Build local retrieval vectors and find relevant passages."),
    ("reasoning", "Analyze content", "Generate a summary, match review terms, or extract literal fields."),
    ("verification", "Verify sources", "Check citations and decide which findings need human review."),
    ("deliverables", "Save results", "Save the run, findings, and downloadable report files."),
)

AGENT_STAGES = {
    "security_agent": "routing", "router_agent": "routing", "document_agent": "routing",
    "planner_agent": "routing", "vision_agent": "vision", "knowledge_agent": "knowledge",
    "reasoning_agent": "reasoning", "verification_agent": "verification",
    "human_review": "verification", "deliverable_agent": "deliverables",
}


def publish(callback: ProgressCallback | None, stage: str, state: str,
            message: str = "", detail: str = "", **metadata) -> None:
    if callback:
        callback({"type": "stage", "stage": stage, "state": state,
                  "message": message, "detail": detail, "metadata": metadata})


def complete_stage(callback: ProgressCallback | None, stage: str, steps: list) -> None:
    states = [step.status for step in steps]
    state = ("error" if "error" in states else "warning" if "warning" in states
             else "skipped" if states and all(s == "skipped" for s in states) else "completed")
    last = steps[-1] if steps else None
    publish(callback, stage, state, last.message if last else "Stage completed",
            last.detail if last else "")
