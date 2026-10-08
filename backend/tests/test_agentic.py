"""Tests for the planner loop, tool allowlist, review gate and knowledge search."""
from __future__ import annotations

import pytest

from app import config
from app.agents import planner_agent, review_gate
from app.agents.base import RunContext
from app.agents.planner_agent import PlannerAgent, PlannerDecision
from app.agents.tools import REGISTRY, ToolArgumentError, ToolNotAllowed
from app.models.providers import OllamaProvider, get_provider
from app.security.guard import AirgapViolation, assert_local_url

PID_TASK = "Inspect Unit 4 P&ID and inspection report for corrosion"


# --- Existing behaviour ---------------------------------------------------------
def test_deterministic_demo_unchanged(client):
    run = client.post("/api/demo/run").json()
    assert run["run"]["status"] == "completed"
    assert run["run"]["verification_score"] == 94.0
    assert [f["needs_review"] for f in run["findings"]] == [0, 0, 1, 0]
    assert [s["agent"] for s in run["steps"]][:2] == ["security_agent", "router_agent"]
    assert run["deliverables"]


def test_mock_provider_is_selected_for_tests():
    assert get_provider().name == "mock-local"
    assert config.IS_AIRGAPPED


# --- Knowledge search -----------------------------------------------------------
def test_knowledge_search_returns_ranked_chunks(client):
    res = client.post("/api/knowledge/search",
                      json={"query": "corrosion P-101 outlet wall thickness", "top_k": 3})
    assert res.status_code == 200
    body = res.json()
    assert 1 <= len(body["results"]) <= 3
    scores = [r["score"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True)
    assert "P-101" in body["results"][0]["text"]
    assert body["total_chunks"] > 0


@pytest.mark.parametrize("payload", [{"query": ""}, {"query": "   "},
                                     {"query": "x", "top_k": 0},
                                     {"query": "x", "top_k": 99},
                                     {"query": "x" * 501}, {}])
def test_knowledge_search_validates_input(client, payload):
    assert client.post("/api/knowledge/search", json=payload).status_code == 422


# --- Tool registry --------------------------------------------------------------
def test_registry_is_a_fixed_allowlist():
    assert set(REGISTRY.names()) == {"search_knowledge", "inspect_document", "analyze_pid",
                                     "reason", "verify", "human_review"}


@pytest.mark.parametrize("name", ["shell", "run_sql", "read_file", "http_get", "", None])
def test_registry_rejects_unknown_tools(name):
    with pytest.raises(ToolNotAllowed):
        REGISTRY.execute(name, RunContext())


@pytest.mark.parametrize("name,args", [
    ("inspect_document", {"path": "/etc/passwd"}),
    ("search_knowledge", {}),
    ("search_knowledge", {"query": "x", "top_k": 500}),
    ("search_knowledge", {"query": "x", "sql": "DROP TABLE findings"}),
])
def test_registry_rejects_bad_arguments(name, args):
    with pytest.raises(ToolArgumentError):
        REGISTRY.execute(name, RunContext(), args)


# --- Planner --------------------------------------------------------------------
def test_planner_runs_to_finish_and_requires_review(client):
    run = client.post("/api/agent/run", json={"task": PID_TASK}).json()
    plan = run["planner"]
    assert plan["stop_reason"] == "finished"
    assert [t["action"] for t in plan["trace"]] == [
        "inspect_document", "analyze_pid", "search_knowledge", "reason", "verify",
        "human_review", "finish"]
    # The high-severity P-101 finding must be held for approval.
    assert run["run"]["status"] == "awaiting_review"
    assert plan["requires_human_review"] is True
    high = [f for f in run["findings"] if f["severity"] == "high"]
    assert high and all(f["needs_review"] == 1 for f in high)


def test_planner_skips_pid_analysis_for_text_tasks(client):
    run = client.post("/api/agent/run",
                      json={"task": "Summarise corrosion risk for the feed pump"}).json()
    actions = [t["action"] for t in run["planner"]["trace"]]
    assert "analyze_pid" not in actions and actions[-1] == "finish"


def test_max_steps_bounds_the_loop(client):
    run = client.post("/api/agent/run", json={"task": PID_TASK, "max_steps": 2}).json()
    assert run["planner"]["steps_used"] == 2
    assert run["planner"]["stop_reason"] == "max_steps_reached"
    assert run["run"]["status"] == "halted"
    assert client.post("/api/agent/run",
                       json={"task": PID_TASK, "max_steps": 500}).status_code == 422


def test_loop_protection_stops_repeated_action(client):
    class Stuck(PlannerAgent):
        def next_action(self, ctx):
            return PlannerDecision("search_knowledge", "stuck", {"query": "pump", "top_k": 2})

    run = planner_agent.run_agentic(PID_TASK, max_steps=10, planner=Stuck())
    assert run["planner"]["stop_reason"] == "loop_detected"
    assert run["planner"]["steps_used"] == 2
    assert run["run"]["status"] == "halted"


def test_planner_cannot_call_tool_outside_allowlist(client):
    class Rogue(PlannerAgent):
        def next_action(self, ctx):
            return PlannerDecision("shell", "rogue", {"cmd": "rm -rf /"})

    run = planner_agent.run_agentic(PID_TASK, planner=Rogue())
    assert run["planner"]["stop_reason"] == "tool_rejected"
    assert run["run"]["status"] == "halted"


def test_early_finish_cannot_bypass_review_gate(client):
    class Hasty(PlannerAgent):
        def next_action(self, ctx):
            if not ctx.findings:
                return PlannerDecision("reason", "skip straight to findings")
            return PlannerDecision("finish", "done")

    run = planner_agent.run_agentic(PID_TASK, planner=Hasty())
    assert run["run"]["status"] == "awaiting_review"
    assert all(f["needs_review"] == 1 for f in run["findings"])


# --- Review gate ----------------------------------------------------------------
def test_review_gate_reasons():
    sources = {"inspection_report_2026.pdf"}
    ok = {"severity": "low", "confidence": 90,
          "evidence": [{"source": "Inspection_Report_2026.pdf"}]}
    assert review_gate.review_reasons(ok, sources) == []
    assert review_gate.review_reasons({**ok, "severity": "high"}, sources)
    assert review_gate.review_reasons({**ok, "evidence": []}, sources)
    assert review_gate.review_reasons({**ok, "evidence": [{"source": "made_up.pdf"}]}, sources)
    assert review_gate.review_reasons({**ok, "confidence": 40}, sources)
    assert review_gate.review_reasons(ok, sources, verified=False)


def test_approval_completes_held_run(client):
    run = client.post("/api/agent/run", json={"task": PID_TASK}).json()
    flagged = [f for f in run["findings"] if f["needs_review"]]
    for f in flagged[:-1]:
        client.post(f"/api/review/{f['id']}/approve")
    run_id = run["run"]["id"]
    assert client.get(f"/api/agents/runs/{run_id}").json()["run"]["status"] == "awaiting_review"
    client.post(f"/api/review/{flagged[-1]['id']}/approve")
    assert client.get(f"/api/agents/runs/{run_id}").json()["run"]["status"] == "completed"


# --- Air gap --------------------------------------------------------------------
def test_ollama_is_loopback_only_when_airgapped():
    assert_local_url("http://localhost:11434/api/generate")
    with pytest.raises(AirgapViolation):
        assert_local_url("https://api.example.com/v1")
    with pytest.raises(AirgapViolation):
        OllamaProvider(base_url="http://10.0.0.5:11434").generate("hi")
