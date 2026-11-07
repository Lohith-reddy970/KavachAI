"""Runner policy, lifecycle, request boundaries, and failure regressions."""
from __future__ import annotations

import json
import os
import subprocess

import pytest
from fastapi.testclient import TestClient

from app import config
from app.database import db
from app.main import app
from app.security import sandbox

IMAGE_ID = "sha256:" + "a" * 64


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(config, "SANDBOX_ENABLED", True)
    monkeypatch.setattr(config, "SANDBOX_WSL_DISTRO", "")
    monkeypatch.setattr(config, "SANDBOX_DOCKER_HOST", "unix:///var/run/docker.sock")
    monkeypatch.setattr(sandbox, "_health_cache", None)


@pytest.fixture
def local_client():
    with TestClient(app, base_url="http://localhost", client=("127.0.0.1", 50000)) as client:
        yield client


def result(**changes):
    return {"status": "completed", "exit_code": 0, "stdout": "42\n", "stderr": "",
            "output_truncated": False, **changes}


def fake_runtime(monkeypatch, response=None, timeout=False, cleanup_error=False):
    calls = []
    monkeypatch.setattr(sandbox, "_transport", lambda: ["docker"])
    monkeypatch.setattr(sandbox, "_inspect", lambda command: IMAGE_ID)

    def control(command, args, timeout=5):
        calls.append(args)
        return subprocess.CompletedProcess(args, 1 if cleanup_error else 0, b"", b"failed" if cleanup_error else b"")

    class Process:
        def __init__(self, command, **kwargs):
            calls.append(command)
            self.returncode = 0
            self.killed = False
            self.first_wait = True
            self.payload = json.loads(kwargs["stdin"].read())
            calls.append(self.payload)
            self.stdout = stream(json.dumps(response or result()).encode())
            self.stderr = stream(b"")

        def wait(self, timeout=None):
            if self.first_wait and timeout is not None and should_timeout:
                self.first_wait = False
                raise subprocess.TimeoutExpired("docker", timeout)
            return self.returncode

        def kill(self):
            self.killed = True

    def stream(data):
        read_fd, write_fd = os.pipe()
        os.write(write_fd, data)
        os.close(write_fd)
        return os.fdopen(read_fd, "rb", buffering=0)

    should_timeout = timeout
    monkeypatch.setattr(sandbox, "_control", control)
    monkeypatch.setattr(sandbox.subprocess, "Popen", Process)
    return calls


def test_execution_applies_policy_and_cleans_its_container(enabled, monkeypatch):
    calls = fake_runtime(monkeypatch)
    code = "print(6 * 7)"
    response = sandbox.execute(code, "user input", 2)
    assert response["stdout"] == "42\n" and response["status"] == "completed"
    command = calls[0]
    for flag in ("--rm", "--pull=never", "--network=none", "--read-only", "--cap-drop=ALL",
                 "--security-opt=no-new-privileges=true", "--pids-limit=32", "--cpus=1",
                 "--memory=128m", "--memory-swap=128m", "--log-driver=none"):
        assert flag in command
    assert IMAGE_ID in command and config.SANDBOX_IMAGE not in command
    assert not any(arg in {"--privileged", "--volume", "-v", "--mount", "--publish"} for arg in command)
    assert code not in command
    assert calls[1] == {"code": code, "stdin": "user input", "timeout_seconds": 2}
    assert calls[-1] == ["rm", "--force", response["job_id"]]


def test_outer_deadline_kills_client_and_removes_container(enabled, monkeypatch):
    calls = fake_runtime(monkeypatch, timeout=True)
    response = sandbox.execute("while True: pass", timeout_seconds=1)
    assert response["status"] == "timed_out"
    assert calls[-1] == ["rm", "--force", response["job_id"]]


def test_invalid_supervisor_result_fails_closed_and_cleans_up(enabled, monkeypatch):
    calls = fake_runtime(monkeypatch, response={"supervisor_error": "RuntimeError"})
    with pytest.raises(sandbox.SandboxUnavailable, match="valid result"):
        sandbox.execute("print(1)")
    assert calls[-1][0:2] == ["rm", "--force"]


def test_cleanup_failure_does_not_report_success(enabled, monkeypatch):
    fake_runtime(monkeypatch, cleanup_error=True)
    with pytest.raises(sandbox.SandboxUnavailable, match="cleanup"):
        sandbox.execute("print(1)")


def test_concurrent_jobs_are_rejected_without_starting_containers(enabled):
    assert sandbox._slot.acquire(blocking=False)
    try:
        with pytest.raises(sandbox.SandboxBusy):
            sandbox.execute("print(1)")
    finally:
        sandbox._slot.release()


def test_remote_docker_transport_is_rejected(enabled, monkeypatch):
    monkeypatch.setattr(config, "SANDBOX_DOCKER_HOST", "tcp://example.org:2375")
    with pytest.raises(sandbox.SandboxUnavailable, match="local Unix socket"):
        sandbox._transport()


def test_missing_runtime_is_reported_and_never_runs_code_on_host(enabled, monkeypatch):
    monkeypatch.setattr(sandbox.shutil, "which", lambda executable: None)
    status = sandbox.status(refresh=True)
    assert status["status"] == "unavailable" and status["available"] is False
    with pytest.raises(sandbox.SandboxUnavailable, match="not installed"):
        sandbox.execute("print(1)")


@pytest.mark.parametrize("change", [{"OSType": "windows"}, {"MemoryLimit": False},
                                    {"PidsLimit": False}, {"CpuCfsQuota": False},
                                    {"SwapLimit": False}, {"SecurityOptions": []}])
def test_engine_without_required_isolation_is_rejected(enabled, monkeypatch, change):
    engine = {"OSType": "linux", "MemoryLimit": True, "PidsLimit": True, "CpuCfsQuota": True,
              "SwapLimit": True, "SecurityOptions": ["name=seccomp,profile=builtin"], **change}
    monkeypatch.setattr(sandbox, "_control", lambda *args: subprocess.CompletedProcess([], 0, json.dumps(engine).encode(), b""))
    with pytest.raises(sandbox.SandboxUnavailable):
        sandbox._inspect(["docker"])


def test_disabled_status_does_not_probe_docker(monkeypatch):
    monkeypatch.setattr(config, "SANDBOX_ENABLED", False)
    monkeypatch.setattr(sandbox, "_transport", lambda: pytest.fail("Disabled execution must not probe Docker"))
    assert sandbox.status(refresh=True)["status"] == "disabled"
    with pytest.raises(sandbox.SandboxUnavailable, match="disabled"):
        sandbox.execute("print(1)")


def test_docker_context_secrets_cannot_override_local_transport(monkeypatch):
    monkeypatch.setenv("DOCKER_CONTEXT", "remote")
    monkeypatch.setenv("DOCKER_HOST", "ssh://remote")
    assert not any(key.upper().startswith("DOCKER_") for key in sandbox._environment())


def test_api_runs_explicit_code_and_audits_hash_not_content(enabled, local_client, monkeypatch):
    fake_runtime(monkeypatch)
    code = "print('a private literal')"
    response = local_client.post("/api/sandbox/execute", json={"code": code},
                                 headers={"X-Kavach-Sandbox": "execute", "Origin": "http://localhost:3000"})
    assert response.status_code == 200
    assert response.json()["stdout"] == "42\n"
    audit = db.fetch_one("SELECT * FROM audit_logs WHERE action='sandbox.execute' ORDER BY id DESC")
    assert "sha256=" in audit["detail"] and code not in audit["detail"]


def test_api_rejects_remote_clients(enabled):
    with TestClient(app, base_url="http://localhost", client=("192.0.2.10", 50000)) as client:
        response = client.post("/api/sandbox/execute", json={"code": "print(1)"}, headers={"X-Kavach-Sandbox": "execute"})
        assert response.status_code == 403


@pytest.mark.parametrize("headers", [{}, {"Origin": "https://evil.example", "X-Kavach-Sandbox": "execute"},
                                     {"Host": "evil.example", "X-Kavach-Sandbox": "execute"}])
def test_api_rejects_cross_site_or_unmarked_execution(local_client, headers):
    assert local_client.post("/api/sandbox/execute", json={"code": "print(1)"}, headers=headers).status_code == 403


@pytest.mark.parametrize("payload", [{"code": ""}, {"code": "print(1)", "image": "arbitrary"},
                                     {"code": "print(1)", "timeout_seconds": True},
                                     {"code": "print(1)", "timeout_seconds": 31}])
def test_api_rejects_invalid_inputs(local_client, payload):
    assert local_client.post("/api/sandbox/execute", json=payload, headers={"X-Kavach-Sandbox": "execute"}).status_code == 422


@pytest.mark.parametrize("code,stdin,timeout", [("   ", "", 1), ("x" * 65537, "", 1),
                                               ("print(1)", "x" * 16385, 1), ("print(1)", "", 31)],
                         ids=["blank", "code-too-large", "input-too-large", "timeout-too-large"])
def test_byte_and_time_budgets_are_enforced_before_runtime(enabled, code, stdin, timeout):
    with pytest.raises(ValueError):
        sandbox.execute(code, stdin, timeout)


def test_runtime_unavailable_returns_503(enabled, local_client, monkeypatch):
    monkeypatch.setattr(sandbox.shutil, "which", lambda executable: None)
    response = local_client.post("/api/sandbox/execute", json={"code": "print(1)"}, headers={"X-Kavach-Sandbox": "execute"})
    assert response.status_code == 503
