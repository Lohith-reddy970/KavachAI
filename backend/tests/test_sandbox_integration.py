"""Opt-in tests that execute programs only inside the real Linux container."""
import os

import pytest

from app import config
from app.security import sandbox

pytestmark = pytest.mark.skipif(os.getenv("KAVACH_RUN_SANDBOX_INTEGRATION") != "1",
                                reason="Set KAVACH_RUN_SANDBOX_INTEGRATION=1 with a provisioned local Docker engine")


@pytest.fixture(autouse=True)
def real_runtime(monkeypatch):
    monkeypatch.setattr(config, "SANDBOX_ENABLED", True)
    health = sandbox.status(refresh=True)
    assert health["available"], health["reason"]


def test_real_python_output_input_and_worker_identity():
    result = sandbox.execute("import os\nprint(os.getuid())\nprint(input().upper())", "actual input\n")
    assert result["status"] == "completed"
    assert result["stdout"] == "65534\nACTUAL INPUT\n"


def test_real_syntax_error():
    result = sandbox.execute("this is invalid python!")
    assert result["status"] == "failed" and "SyntaxError" in result["stderr"]


def test_real_timeout():
    result = sandbox.execute("import time\ntime.sleep(60)", timeout_seconds=1)
    assert result["status"] == "timed_out"


def test_real_output_limit():
    result = sandbox.execute("while True: print('x' * 4096)")
    assert result["status"] == "output_limit" and result["output_truncated"]
    assert len(result["stdout"]) + len(result["stderr"]) <= 65536


def test_real_network_filesystem_and_privilege_boundaries():
    code = '''import os, socket
from pathlib import Path
assert os.getuid() == 65534
assert not any(key.startswith('KAVACH_') or key.startswith('DOCKER_') for key in os.environ)
assert not Path('/mnt/c/Users').exists()
assert not Path('/var/run/docker.sock').exists()
status = Path('/proc/self/status').read_text()
assert 'CapEff:\t0000000000000000' in status
assert 'NoNewPrivs:\t1' in status
try:
    Path('/opt/kavach/forbidden').write_text('blocked')
except OSError:
    pass
else:
    raise AssertionError('root filesystem was writable')
try:
    socket.create_connection(('1.1.1.1', 443), timeout=1)
except OSError:
    pass
else:
    raise AssertionError('outbound networking was possible')
print('boundaries enforced')
'''
    result = sandbox.execute(code)
    assert result["status"] == "completed", result
    assert result["stdout"] == "boundaries enforced\n"


def test_real_temporary_files_are_discarded_between_jobs():
    assert sandbox.execute("from pathlib import Path\nPath('/tmp/kavach-isolation-marker').write_text('ephemeral')")["status"] == "completed"
    result = sandbox.execute("from pathlib import Path\nprint(Path('/tmp/kavach-isolation-marker').exists())")
    assert result["stdout"] == "False\n"


def test_real_memory_limit():
    result = sandbox.execute("data = bytearray(512 * 1024 * 1024)")
    assert result["status"] == "failed"


def test_no_job_containers_remain():
    response = sandbox._control(sandbox._transport(), ["ps", "--all", "--quiet", "--filter", "label=io.kavach.sandbox.job=1"])
    assert response.returncode == 0 and not response.stdout.strip()
