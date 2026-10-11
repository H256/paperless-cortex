"""Regression tests for the Docker entrypoint (issue #146).

A fresh Postgres volume has no tables, so the entrypoint must run
``alembic upgrade head`` before starting the worker/API; otherwise every
``/api/*`` call 500s until a manual migration is run.

These tests execute ``docker/entrypoint.sh`` with stubbed ``alembic`` /
``python`` / ``uvicorn`` on ``PATH`` so the whole script runs to completion
without a real Postgres or a Docker build. They assert:

- the migration step runs (and gates startup) when ``DATABASE_URL`` is set,
- the migration step is skipped when ``DATABASE_URL`` is unset,
- a transient migration failure is retried, and
- a persistent migration failure aborts the container (non-zero exit).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = REPO_ROOT / "docker" / "entrypoint.sh"


def _run_entrypoint(
    env_overrides: dict[str, str],
    tmp: Path,
    alembic_mode: str,
    remove_keys: tuple[str, ...] = (),
) -> subprocess.CompletedProcess:
    """Run the entrypoint with stubbed commands; return the completed process."""
    stub_bin = tmp / "stub-bin"
    stub_bin.mkdir()

    log_file = tmp / "alembic.log"
    fail_once_marker = tmp / "fail_once.marker"

    alembic = stub_bin / "alembic"
    alembic.write_text(
        "#!/bin/sh\n"
        "echo \"alembic $*\" >> \"$STUB_ALEMBIC_LOG\"\n"
        "if [ \"$STUB_ALEMBIC_MODE\" = \"always_fail\" ]; then exit 1; fi\n"
        "if [ \"$STUB_ALEMBIC_MODE\" = \"fail_once\" ]; then\n"
        "  if [ ! -f \"$STUB_ALEMBIC_FAIL_MARKER\" ]; then\n"
        "    touch \"$STUB_ALEMBIC_FAIL_MARKER\"\n"
        "    exit 1\n"
        "  fi\n"
        "fi\n"
        "exit 0\n"
    )
    alembic.chmod(0o755)

    for name in ("python", "uvicorn"):
        stub = stub_bin / name
        stub.write_text("#!/bin/sh\nexit 0\n")
        stub.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{stub_bin}{os.pathsep}{env.get('PATH', '')}"
    env["STUB_ALEMBIC_LOG"] = str(log_file)
    env["STUB_ALEMBIC_MODE"] = alembic_mode
    env["STUB_ALEMBIC_FAIL_MARKER"] = str(fail_once_marker)
    # Keep the retry loop fast in the failure test.
    env.setdefault("MIGRATION_RETRY_SLEEP", "0")
    env.update(env_overrides)
    for key in remove_keys:
        env.pop(key, None)

    return subprocess.run(
        ["bash", str(ENTRYPOINT)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_entrypoint_runs_migrations_when_database_url_set(tmp_path: Path) -> None:
    result = _run_entrypoint({"DATABASE_URL": "postgresql+psycopg://u:p@h:5432/db"}, tmp_path, "always_ok")

    assert result.returncode == 0, result.stderr
    log = (tmp_path / "alembic.log").read_text()
    assert "alembic upgrade head" in log


def test_entrypoint_skips_migrations_when_database_url_unset(tmp_path: Path) -> None:
    # DATABASE_URL must be genuinely absent (not merely empty) for the skip path.
    result = _run_entrypoint({}, tmp_path, "always_ok", remove_keys=("DATABASE_URL",))

    assert result.returncode == 0, result.stderr
    log_file = tmp_path / "alembic.log"
    assert not log_file.exists() or "upgrade head" not in log_file.read_text()


def test_entrypoint_retries_transient_migration_failure(tmp_path: Path) -> None:
    result = _run_entrypoint(
        {"DATABASE_URL": "postgresql+psycopg://u:p@h:5432/db", "MAX_MIGRATION_ATTEMPTS": "5"},
        tmp_path,
        "fail_once",
    )

    assert result.returncode == 0, result.stderr
    log = (tmp_path / "alembic.log").read_text()
    # Failing once then succeeding means the migration command ran twice.
    assert log.count("upgrade head") == 2


def test_entrypoint_aborts_on_persistent_migration_failure(tmp_path: Path) -> None:
    result = _run_entrypoint(
        {"DATABASE_URL": "postgresql+psycopg://u:p@h:5432/db", "MAX_MIGRATION_ATTEMPTS": "3"},
        tmp_path,
        "always_fail",
    )

    assert result.returncode != 0
    assert "alembic upgrade head failed" in result.stderr
