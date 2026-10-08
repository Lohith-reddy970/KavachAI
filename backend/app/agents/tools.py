"""Safe, allowlisted tool registry for the agentic planner.

The planner can only invoke the tools defined in this module. There is no
dynamic registration, and no tool exposes a shell, SQL, the filesystem or any
network/cloud API - each one wraps an existing deterministic agent or the local
RAG index. Unknown tool names and unexpected arguments are rejected.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Mapping

from ..services import knowledge as knowledge_service
from . import review_gate
from .base import RunContext
from .document_agent import DocumentAgent
from .reasoning_agent import ReasoningAgent
from .verification_agent import VerificationAgent
from .vision_agent import VisionAgent

MAX_QUERY_CHARS = 500
MAX_TOP_K = 10


class ToolError(Exception):
    """Base class for tool-registry rejections."""


class ToolNotAllowed(ToolError):
    """Raised when a tool outside the allowlist is requested."""


class ToolArgumentError(ToolError):
    """Raised when a tool is called with invalid or unexpected arguments."""


ToolHandler = Callable[[RunContext, dict[str, Any]], None]
ArgValidator = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    handler: ToolHandler
    validate: ArgValidator


def _no_args(args: dict[str, Any]) -> dict[str, Any]:
    if args:
        raise ToolArgumentError(f"Unexpected arguments: {', '.join(sorted(args))}.")
    return {}


def _search_args(args: dict[str, Any]) -> dict[str, Any]:
    extra = set(args) - {"query", "top_k"}
    if extra:
        raise ToolArgumentError(f"Unexpected arguments: {', '.join(sorted(extra))}.")
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ToolArgumentError("'query' must be a non-empty string.")
    if len(query) > MAX_QUERY_CHARS:
        raise ToolArgumentError(f"'query' exceeds {MAX_QUERY_CHARS} characters.")
    top_k = args.get("top_k", 4)
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= MAX_TOP_K:
        raise ToolArgumentError(f"'top_k' must be an integer between 1 and {MAX_TOP_K}.")
    return {"query": query.strip(), "top_k": top_k}


def _search_knowledge(ctx: RunContext, args: dict[str, Any]) -> None:
    hits = knowledge_service.get_kb().search(args["query"], top_k=args["top_k"])
    ctx.artifacts["retrieved"] = hits
    ctx.add_step("knowledge_agent", "Knowledge retrieved",
                 detail=f"Retrieved {len(hits)} chunks from the local vector DB "
                        f"for query '{args['query'][:80]}'.")


def _inspect_document(ctx: RunContext, args: dict[str, Any]) -> None:
    DocumentAgent().run(ctx)


def _analyze_pid(ctx: RunContext, args: dict[str, Any]) -> None:
    VisionAgent().run(ctx)


def _reason(ctx: RunContext, args: dict[str, Any]) -> None:
    ReasoningAgent().run(ctx)


def _verify(ctx: RunContext, args: dict[str, Any]) -> None:
    VerificationAgent().run(ctx)
    required = review_gate.apply(ctx.findings)
    ctx.artifacts["verification"]["review_required"] = required


def _human_review(ctx: RunContext, args: dict[str, Any]) -> None:
    required = review_gate.apply(ctx.findings, verified="verification" in ctx.artifacts)
    ctx.artifacts["human_review"] = {"required": required}
    ctx.add_step(
        "human_review", "Human approval requested", status="awaiting_review",
        detail=f"{len(required)} finding(s) held for human review: "
               + "; ".join(f"{r['title']} ({', '.join(r['reasons'])})" for r in required))


_TOOLS: Mapping[str, ToolSpec] = MappingProxyType({
    spec.name: spec for spec in (
        ToolSpec("search_knowledge", "Search the local RAG knowledge base.",
                 _search_knowledge, _search_args),
        ToolSpec("inspect_document", "Load and OCR the scenario document set.",
                 _inspect_document, _no_args),
        ToolSpec("analyze_pid", "Detect equipment regions on the P&ID.",
                 _analyze_pid, _no_args),
        ToolSpec("reason", "Synthesize findings from gathered evidence.",
                 _reason, _no_args),
        ToolSpec("verify", "Cross-check findings against cited evidence.",
                 _verify, _no_args),
        ToolSpec("human_review", "Hold high-risk or unsupported findings for approval.",
                 _human_review, _no_args),
    )
})


class ToolRegistry:
    """Read-only view over the fixed tool allowlist."""

    def names(self) -> list[str]:
        return list(_TOOLS)

    def describe(self) -> list[dict[str, str]]:
        return [{"name": t.name, "description": t.description} for t in _TOOLS.values()]

    def execute(self, name: str, ctx: RunContext, args: dict[str, Any] | None = None) -> None:
        spec = _TOOLS.get(name) if isinstance(name, str) else None
        if spec is None:
            raise ToolNotAllowed(f"Tool '{name}' is not in the allowlist.")
        spec.handler(ctx, spec.validate(dict(args or {})))


REGISTRY = ToolRegistry()
