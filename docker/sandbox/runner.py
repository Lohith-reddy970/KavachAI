"""Trusted container supervisor. Never import or execute submitted code here.

The child runs under a separate unprivileged UID, with isolated Python settings.
Only the supervisor can write the result envelope to the Docker stdout stream.
"""
from __future__ import annotations

import json
import math
import os
import resource
import signal
import subprocess
import sys
import threading
import time

MAX_OUTPUT = 65536


def execute(payload: dict) -> dict:
    code = payload["code"]
    user_input = payload.get("stdin", "").encode("utf-8")
    timeout = max(1, min(30, int(payload["timeout_seconds"])))
    if not isinstance(code, str) or len(code.encode("utf-8")) > 65536 or len(user_input) > 16384:
        raise ValueError("Input exceeds sandbox limits")
    # Hard limits are inherited by the child; it cannot raise them without privileges.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024, 8 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_CPU, (math.ceil(timeout) + 1, math.ceil(timeout) + 1))
    started = time.monotonic()
    process = subprocess.Popen(
        [sys.executable, "-I", "-S", "-u", "-c", code],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd="/tmp", env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp", "LANG": "C.UTF-8"},
        user=65534, group=65534, extra_groups=(), start_new_session=True,
    )
    lock = threading.Lock()
    exceeded = threading.Event()
    buffers = [bytearray(), bytearray()]
    total = 0

    def kill() -> None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def read(stream, index: int) -> None:
        nonlocal total
        try:
            while chunk := os.read(stream.fileno(), 4096):
                with lock:
                    remaining = max(0, MAX_OUTPUT - total)
                    buffers[index].extend(chunk[:remaining])
                    total += len(chunk)
                    if total > MAX_OUTPUT:
                        exceeded.set()
                        kill()
        finally:
            stream.close()

    readers = [threading.Thread(target=read, args=(stream, i), daemon=True)
               for i, stream in enumerate((process.stdout, process.stderr))]
    for reader in readers:
        reader.start()

    def write() -> None:
        try:
            process.stdin.write(user_input)
            process.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    writer = threading.Thread(target=write, daemon=True)
    writer.start()
    timed_out = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill()
        process.wait()
    finally:
        # Also terminate children left behind by an exited main program.
        kill()
    for reader in readers:
        reader.join(timeout=1)
    status = ("output_limit" if exceeded.is_set() else "timed_out" if timed_out
              else "completed" if process.returncode == 0 else "failed")
    return {
        "status": status, "exit_code": process.returncode,
        "stdout": buffers[0].decode("utf-8", errors="replace"),
        "stderr": buffers[1].decode("utf-8", errors="replace"),
        "duration_ms": round((time.monotonic() - started) * 1000),
        "output_truncated": exceeded.is_set(),
    }


if __name__ == "__main__":
    try:
        request = sys.stdin.buffer.read(150000)
        result = execute(json.loads(request))
    except Exception as exc:
        result = {"supervisor_error": type(exc).__name__}
    sys.stdout.write(json.dumps(result, ensure_ascii=True))
    sys.stdout.flush()
