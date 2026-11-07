"""Deterministic model router for KAVACH AI.

Maps free-text task descriptions to a ``task_type`` and selects the most
appropriate local model, returning a human-readable reason. The classification is
keyword-driven and deterministic.

Model catalog:
    * qwen3:8b            - general reasoning / evidence synthesis
    * llava:7b            - image and P&ID visual analysis
    * llama3.2:3b         - code, classification, extraction, and other text tasks
"""
from __future__ import annotations

from dataclasses import dataclass

from .. import config

# task_type -> model name
_TYPE_TO_MODEL = {
    "vision": config.OLLAMA_VISION_MODEL,
    "code": config.OLLAMA_OTHER_MODEL,
    "classification": config.OLLAMA_OTHER_MODEL,
    "extraction": config.OLLAMA_OTHER_MODEL,
    "reasoning": config.OLLAMA_REASONING_MODEL,
}


def _model_for_type(task_type: str) -> str:
    if config.INFERENCE_PROVIDER == "transformers":
        if task_type == "vision":
            return "unsupported (text-only Transformers provider)"
        return config.TRANSFORMERS_MODEL_PATH or "Transformers model not configured"
    return _TYPE_TO_MODEL.get(task_type, config.OLLAMA_REASONING_MODEL)

# Keyword signals for classification (checked in priority order).
_SIGNALS: list[tuple[str, tuple[str, ...]]] = [
    ("vision", ("p&id", "pid", "image", "png", "jpg", "jpeg", "schematic",
                "diagram", "drawing", "ocr", "photo", "scan", "vision")),
    ("code", ("code", ".py", "python", "script", "function", "vulnerab",
              "sast", "lint", "repository", "source")),
    ("extraction", ("extract", "parse", "field", "table", "form", "csv",
                    "metadata")),
    ("classification", ("classify", "categor", "label", "tag", "triage",
                        "route")),
]


@dataclass
class RoutingDecision:
    task_type: str
    model: str
    reason: str
    confidence: float


def classify(task_text: str) -> str:
    """Return a deterministic task_type for the given text."""
    text = (task_text or "").lower()
    for task_type, keywords in _SIGNALS:
        if any(k in text for k in keywords):
            return task_type
    return "reasoning"


def route(task_text: str) -> RoutingDecision:
    """Classify the task and select the target model with a reason string."""
    task_type = classify(task_text)
    model = _model_for_type(task_type)
    reasons = {
        "vision": f"Detected visual/P&ID content; routing to {model}.",
        "code": f"Detected source-code intent; routing to {model}.",
        "extraction": f"Detected structured extraction; routing to {model}.",
        "classification": f"Detected classification/triage; routing to {model}.",
        "reasoning": f"General analytical task; routing to {model}.",
    }
    # Deterministic confidence banding by type.
    confidence = {
        "vision": 0.93, "code": 0.9, "extraction": 0.88,
        "classification": 0.86, "reasoning": 0.91,
    }[task_type]
    return RoutingDecision(
        task_type=task_type,
        model=model,
        reason=reasons[task_type],
        confidence=confidence,
    )


def routing_rules() -> list[dict]:
    """Describe the configured local model routing for the /api/models endpoint."""
    if config.INFERENCE_PROVIDER == "transformers":
        text_model = config.TRANSFORMERS_MODEL_PATH or "Transformers model not configured"
        return [
            {"task_type": "reasoning", "model": text_model,
             "when": "Local Transformers text analysis and summaries"},
            {"task_type": "vision", "model": "unsupported (text-only Transformers provider)",
             "when": "Images need a vision-capable provider"},
            {"task_type": "code", "model": text_model,
             "when": "Source-code review and vulnerability scanning"},
            {"task_type": "extraction", "model": text_model,
             "when": "Field/table extraction from documents"},
            {"task_type": "classification", "model": text_model,
             "when": "Fast classification and task triage"},
        ]
    return [
        {"task_type": "reasoning", "model": config.OLLAMA_REASONING_MODEL,
         "when": "General text analysis, findings, report reasoning"},
        {"task_type": "vision", "model": config.OLLAMA_VISION_MODEL,
         "when": "Images and P&ID visual analysis"},
        {"task_type": "code", "model": config.OLLAMA_OTHER_MODEL,
         "when": "Source-code review and vulnerability scanning"},
        {"task_type": "extraction", "model": config.OLLAMA_OTHER_MODEL,
         "when": "Field/table extraction from documents"},
        {"task_type": "classification", "model": config.OLLAMA_OTHER_MODEL,
         "when": "Fast classification and task triage"},
    ]
