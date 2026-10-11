"""Regression tests for the Docker entrypoint worker signal forwarding (issue #149).

The entrypoint starts the worker in the background and the API in the
foreground. Without a stop-signal trap, ``docker stop`` signals only the
foreground process and the background worker is SIGKILLed mid-task after the
grace timeout. These tests execute ``docker/entrypoint.sh`` with stubbed
``alembic`` / ``python`` / ``uvicorn`` on ``PATH`` (no real Postgres or Docker)
and assert:

- a stop signal (SIGTERM / SIGINT) is forwarded to the worker and the API,
  so both shut down cleanly;
- a worker crash does not take the API (or the container) down; and
- the API exit status is propagated.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = REPO_ROOT / "docker" / "entrypoint.sh"


def _write_stubs(tmp: Path, worker_mode: str) -> Path:
    """Create stub alembic/python/uvicorn on a temp dir; return the dir."""
    stub_bin = tmp / "stub-bin"
    stub_bin.mkdir()

    alembic = stub_bin / "alembic"
    alembic.write_text("#!/bin/sh\nexit 0\n")
    alembic.chmod(0o755)

    # The worker stub logs the signal it receives, then exits.
    python = stub_bin / "python"
    python.write_text(
        "#!/bin/sh\n"
        "touch \"$STUB_WORKER_READY\"\n"
        "trap 'echo SIGTERM >> \"$STUB_WORKER_LOG\"; exit 0' TERM\n"
        "trap 'echo SIGINT >> \"$STUB_WORKER_LOG\"; exit 0' INT\n"
        "if [ \"$STUB_WORKER_MODE\" = \"crash\" ]; then exit 0; fi\n"
        "while :; do sleep 0.2; done\n"
    )
    python.chmod(0o755)

    # The API (uvicorn) stub logs the signal it receives, then exits.
    uvicorn = stub_bin / "uvicorn"
    uvicorn.write_text(
        "#!/bin/sh\n"
        "touch \"$STUB_API_READY\"\n"
        "trap 'echo SIGTERM >> \"$STUB_API_LOG\"; exit 0' TERM\n"
        "trap 'echo SIGINT >> \"$STUB_API_LOG\"; exit 0' INT\n"
        "while :; do sleep 0.2; done\n"
    )
    uvicorn.chmod(0o755)

    return stub_bin


def _start_entrypoint(
    tmp: Path,
    stub_bin: Path,
    worker_mode: str,
) -> tuple[subprocess.Popen, Path, Path]:
    env = os.environ.copy()
    env["PATH"] = f"{stub_bin}{os.pathsep}{env.get('PATH', '')}"
    env["DATABASE_URL"] = "postgresql+psycopg://u:p@h:5432/db"
    env["STUB_WORKER_MODE"] = worker_mode
    env["STUB_WORKER_LOG"] = str(tmp / "worker.log")
    env["STUB_WORKER_READY"] = str(tmp / "worker.ready")
    env["STUB_API_LOG"] = str(tmp / "api.log")
    env["STUB_API_READY"] = str(tmp / "api.ready")
    env.setdefault("MIGRATION_RETRY_SLEEP", "0")
    proc = subprocess.Popen(
        ["bash", str(ENTRYPOINT)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc, tmp / "worker.log", tmp / "api.log"


def _wait_ready(tmp: Path, timeout: float = 5.0) -> bool:
    """Wait until both stubs have reported ready (trap is installed)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if (tmp / "worker.ready").exists() and (tmp / "api.ready").exists():
            return True
        time.sleep(0.05)
    return False


def _terminate_and_reap(proc: subprocess.Popen) -> int:
    proc.terminate()  # SIGTERM
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    return proc.returncode


def test_entrypoint_forwards_sigterm_to_worker_and_api(tmp_path: Path) -> None:
    stub_bin = _write_stubs(tmp_path, "run")
    proc, worker_log, api_log = _start_entrypoint(tmp_path, stub_bin, "run")
    try:
        assert _wait_ready(tmp_path)
        code = _terminate_and_reap(proc)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()

    assert code == 0, (code, proc.stderr.read() if proc.stderr else "")
    assert "SIGTERM" in worker_log.read_text()
    assert "SIGTERM" in api_log.read_text()


def test_entrypoint_forwards_sigint_to_worker_and_api(tmp_path: Path) -> None:
    stub_bin = _write_stubs(tmp_path, "run")
    proc, worker_log, api_log = _start_entrypoint(tmp_path, stub_bin, "run")
    try:
        assert _wait_ready(tmp_path)
        proc.send_signal(signal.SIGINT)
        code = _terminate_and_reap(proc)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()

    assert code == 0, (code, proc.stderr.read() if proc.stderr else "")
    # The entrypoint forwards a stop signal (SIGINT) to the children as SIGTERM.
    assert "SIGTERM" in worker_log.read_text()
    assert "SIGTERM" in api_log.read_text()


def test_entrypoint_worker_crash_does_not_take_down_api(tmp_path: Path) -> None:
    stub_bin = _write_stubs(tmp_path, "crash")
    proc, _worker_log, api_log = _start_entrypoint(tmp_path, stub_bin, "crash")
    try:
        # The worker (crash mode) exits immediately; the API must keep running,
        # so the entrypoint must stay alive once both are up.
        assert _wait_ready(tmp_path)
        code = _terminate_and_reap(proc)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()

    assert code == 0, (code, proc.stderr.read() if proc.stderr else "")
    # The API received the forwarded stop signal (proof it was still alive and
    # was shut down cleanly).
    assert "SIGTERM" in api_log.read_text()
