"""Regression test for AUDIT INFRA-009 (#153).

`docker/worker_entrypoint.sh` used to `exit 0` when `QUEUE_ENABLED` was not
`1`. With `restart: unless-stopped`, Docker treats exit 0 as "completed" and
never restarts or flags the container, so a worker started against a `.env`
copied from `.env.example` (`QUEUE_ENABLED=0`) sat as `Exited (0)` forever
while silently processing zero tasks.

The fix makes the entrypoint fail loudly (non-zero exit) so the container is
flagged as failed instead of silently completed.
"""

import subprocess
from pathlib import Path

ENTRYPOINT = Path(__file__).resolve().parents[2] / "docker" / "worker_entrypoint.sh"


def _run(entrypoint: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["sh", str(entrypoint)],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_worker_entrypoint_exits_nonzero_when_queue_disabled() -> None:
    """A worker started with the queue disabled must fail (non-zero), not complete."""
    result = _run(
        ENTRYPOINT,
        {"PATH": "/usr/bin:/bin", "QUEUE_ENABLED": "0"},
    )
    assert result.returncode != 0
    assert "QUEUE_ENABLED" in result.stderr


def test_worker_entrypoint_exits_nonzero_when_queue_unset() -> None:
    """Unset QUEUE_ENABLED defaults to disabled and must also fail loudly."""
    result = _run(ENTRYPOINT, {"PATH": "/usr/bin:/bin"})
    assert result.returncode != 0
    assert "QUEUE_ENABLED" in result.stderr


def test_worker_entrypoint_passes_guard_when_queue_enabled() -> None:
    """With QUEUE_ENABLED=1 the guard is passed (no 'will not start' message);
    the script then execs the worker, which fails in this env for unrelated
    reasons (no Redis / app.worker), so we only assert the guard was cleared."""
    result = _run(
        ENTRYPOINT,
        {"PATH": "/usr/bin:/bin", "QUEUE_ENABLED": "1"},
    )
    combined = result.stdout + result.stderr
    assert "will not start" not in combined
