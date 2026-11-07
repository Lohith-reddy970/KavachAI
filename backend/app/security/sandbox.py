"""Local Docker execution with fixed isolation policy and no host fallback."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid

from .. import config


class SandboxUnavailable(RuntimeError):
    pass


class SandboxBusy(RuntimeError):
    pass


_slot = threading.BoundedSemaphore(1)
_health_lock = threading.Lock()
_health_cache: tuple[float, tuple, dict] | None = None


def _transport() -> list[str]:
    host = config.SANDBOX_DOCKER_HOST
    if not (host.startswith("unix:///") or host.startswith("npipe:////./pipe/")):
        raise SandboxUnavailable("Sandbox Docker must use a local Unix socket or Windows named pipe.")
    if config.SANDBOX_WSL_DISTRO:
        wsl = shutil.which("wsl.exe")
        if not wsl:
            raise SandboxUnavailable("WSL is unavailable.")
        return [wsl, "--distribution", config.SANDBOX_WSL_DISTRO, "--user", "root", "--exec",
                "/usr/bin/docker", "--host", host]
    docker = shutil.which(config.SANDBOX_DOCKER)
    if not docker:
        raise SandboxUnavailable("Docker is not installed. Follow the sandbox setup instructions.")
    return [docker, "--host", host]


def _environment() -> dict:
    # Do not let inherited Docker context/host settings route confidential code remotely.
    return {k: v for k, v in os.environ.items() if not k.upper().startswith("DOCKER_")}


def _control(command: list[str], args: list[str], timeout: float = 5) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(command + args, capture_output=True, timeout=timeout,
                              env=_environment(), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SandboxUnavailable("The local Docker engine could not be reached.") from exc


def _inspect(command: list[str]) -> str:
    info = _control(command, ["info", "--format", "{{json .}}"])
    if info.returncode:
        raise SandboxUnavailable("Start the local Linux Docker engine to enable execution.")
    try:
        engine = json.loads(info.stdout)
        if engine.get("OSType") != "linux":
            raise SandboxUnavailable("The sandbox requires Linux containers.")
        if not all(engine.get(key) for key in ("MemoryLimit", "PidsLimit", "CpuCfsQuota", "SwapLimit")):
            raise SandboxUnavailable("Docker resource limits are unavailable on this host.")
        if not any("name=seccomp" in item for item in engine.get("SecurityOptions", [])):
            raise SandboxUnavailable("Docker's default seccomp protection must be enabled.")
        image = _control(command, ["image", "inspect", config.SANDBOX_IMAGE])
        if image.returncode:
            raise SandboxUnavailable("Build the local kavach-sandbox image using the setup instructions.")
        metadata = json.loads(image.stdout)[0]
        if metadata.get("Config", {}).get("Labels", {}).get("io.kavach.sandbox.version") != "1":
            raise SandboxUnavailable("The configured image is not a KAVACH Python sandbox image.")
        if metadata.get("Config", {}).get("Volumes"):
            raise SandboxUnavailable("Sandbox images must not declare volumes.")
        image_id = metadata["Id"]
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
            raise SandboxUnavailable("Docker returned an invalid image identifier.")
        return image_id
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        raise SandboxUnavailable("Docker returned invalid runtime metadata.") from exc


def status(*, refresh: bool = False) -> dict:
    global _health_cache
    signature = (config.SANDBOX_ENABLED, config.SANDBOX_IMAGE, config.SANDBOX_WSL_DISTRO,
                 config.SANDBOX_DOCKER, config.SANDBOX_DOCKER_HOST)
    with _health_lock:
        if not refresh and _health_cache and _health_cache[1] == signature and time.monotonic() - _health_cache[0] < 10:
            return dict(_health_cache[2])
        result = {"status": "disabled", "available": False, "runtime": "docker",
                  "network": "none", "reason": "Code execution is disabled by configuration.",
                  "limits": {"timeout_seconds": config.SANDBOX_TIMEOUT_S,
                             "memory_mb": config.SANDBOX_MEMORY_MB,
                             "output_bytes": config.SANDBOX_MAX_OUTPUT_BYTES, "cpus": 1, "pids": 32}}
        if config.SANDBOX_ENABLED:
            try:
                _inspect(_transport())
                result.update(status="ready", available=True, reason="Isolated Python execution is ready.")
            except SandboxUnavailable as exc:
                result.update(status="unavailable", reason=str(exc))
        _health_cache = (time.monotonic(), signature, result)
        return dict(result)


def _run_command(name: str, image_id: str) -> list[str]:
    return [
        "run", "--rm", "--name", name, "--label", "io.kavach.sandbox.job=1", "--pull=never", "--interactive",
        "--network=none", "--read-only", "--cap-drop=ALL",
        # The trusted supervisor uses only these to spawn/terminate a separate non-root worker.
        "--cap-add=SETUID", "--cap-add=SETGID", "--cap-add=KILL",
        "--security-opt=no-new-privileges=true", "--pids-limit=32", "--cpus=1",
        f"--memory={config.SANDBOX_MEMORY_MB}m", f"--memory-swap={config.SANDBOX_MEMORY_MB}m",
        "--ulimit=nofile=64:64", "--ulimit=core=0:0",
        "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=16777216,mode=1777",
        "--log-driver=none", "--user=0:0", "--workdir=/tmp",
        "--entrypoint=/usr/local/bin/python3", image_id, "-I", "-S", "-u", "/opt/kavach/runner.py",
    ]


def execute(code: str, stdin: str = "", timeout_seconds: int | None = None) -> dict:
    if not config.SANDBOX_ENABLED:
        raise SandboxUnavailable("Code execution is disabled by configuration.")
    if not code.strip() or len(code.encode("utf-8")) > config.SANDBOX_MAX_CODE_BYTES:
        raise ValueError("Code must contain 1 to 65536 UTF-8 bytes.")
    if len(stdin.encode("utf-8")) > 16384:
        raise ValueError("Standard input exceeds 16384 UTF-8 bytes.")
    timeout = timeout_seconds or config.SANDBOX_TIMEOUT_S
    if not 1 <= timeout <= config.SANDBOX_TIMEOUT_S:
        raise ValueError(f"Timeout must be between 1 and {config.SANDBOX_TIMEOUT_S} seconds.")
    if not _slot.acquire(blocking=False):
        raise SandboxBusy("Another sandbox job is running. Try again when it finishes.")
    command = None
    name = "kavach-sandbox-" + uuid.uuid4().hex
    started = time.monotonic()
    cleanup_ok = False
    try:
        command = _transport()
        image_id = _inspect(command)
        payload = json.dumps({"code": code, "stdin": stdin, "timeout_seconds": timeout}).encode("utf-8")
        with tempfile.TemporaryFile() as input_file:
            input_file.write(payload)
            input_file.seek(0)
            process = subprocess.Popen(command + _run_command(name, image_id), stdin=input_file,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       env=_environment(), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            # Cap Docker/client output independently of the trusted in-container cap.
            output = [bytearray(), bytearray()]
            overflow = threading.Event()

            def drain(stream, index):
                try:
                    while chunk := os.read(stream.fileno(), 4096):
                        remaining = max(0, 450000 - len(output[index]))
                        output[index].extend(chunk[:remaining])
                        if len(chunk) > remaining:
                            overflow.set()
                            process.kill()
                finally:
                    stream.close()

            readers = [threading.Thread(target=drain, args=(stream, i), daemon=True)
                       for i, stream in enumerate((process.stdout, process.stderr))]
            for reader in readers:
                reader.start()
            outer_timeout = False
            try:
                process.wait(timeout=timeout + 10)
            except subprocess.TimeoutExpired:
                outer_timeout = True
                process.kill()
                process.wait(timeout=5)
            finally:
                for reader in readers:
                    reader.join(timeout=2)
            if outer_timeout:
                result = {"status": "timed_out", "exit_code": None, "stdout": "", "stderr": "Sandbox exceeded its execution deadline.", "output_truncated": False}
            elif overflow.is_set():
                raise SandboxUnavailable("Sandbox runtime output exceeded its protocol limit.")
            elif process.returncode == 137:
                result = {"status": "failed", "exit_code": 137, "stdout": "",
                          "stderr": "Sandbox was terminated by the container runtime (exit 137).",
                          "output_truncated": False}
            elif process.returncode:
                raise SandboxUnavailable("The container could not complete execution. Check the local Docker engine.")
            else:
                try:
                    result = json.loads(output[0])
                    if result.get("status") not in {"completed", "failed", "timed_out", "output_limit"}:
                        raise ValueError("Invalid execution status")
                except (ValueError, TypeError, AttributeError) as exc:
                    raise SandboxUnavailable("The isolated runner did not return a valid result.") from exc
        result.update(job_id=name, runtime="docker", language="python",
                      duration_ms=round((time.monotonic() - started) * 1000),
                      code_sha256=hashlib.sha256(code.encode("utf-8")).hexdigest())
    except OSError as exc:
        raise SandboxUnavailable("The local sandbox runtime could not be started.") from exc
    finally:
        try:
            if command is not None:
                # Name is generated by this process, never supplied by the request.
                removed = _control(command, ["rm", "--force", name])
                cleanup_ok = removed.returncode == 0 or b"No such container" in removed.stderr
        finally:
            _slot.release()
    if not cleanup_ok:
        raise SandboxUnavailable("Sandbox cleanup could not be confirmed. Check the local Docker engine.")
    return result
