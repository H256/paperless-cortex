"""Regression tests for running the container as a non-root user (issue #150).

The backend stage of the Dockerfile must not run the app as root. These tests
parse the Dockerfile (no Docker build required) and assert:

- a non-root user is created and the container switches to it via ``USER``,
- uv is installed to a world-accessible location (not ``/root/.local/bin``,
  which lives in root's mode-0700 home and is invisible to other users),
- the uv binary is reachable on ``PATH`` from that location,
- the app source is copied *before* the user switch so the non-root user can
  read it, and
- the entrypoint is the container command (unchanged).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "Dockerfile"


def _dockerfile_text() -> str:
    return DOCKERFILE.read_text()


def test_dockerfile_switches_to_nonroot_user() -> None:
    text = _dockerfile_text()
    # A USER directive must appear. The container's *final* user (the one in
    # effect at runtime) must be non-root. Intermediate `USER root` build steps
    # are legitimate (e.g. chowning before the venv build).
    user_lines = [ln for ln in text.splitlines() if re.match(r"^\s*USER\s+", ln)]
    assert user_lines, "Dockerfile has no USER directive; container runs as root"
    final_user = user_lines[-1].split(None, 1)[1].strip()
    assert final_user != "root", f"container's final user is root: {final_user}"
    # The non-root user must be created explicitly (useradd) before the switch.
    assert re.search(r"^\s*RUN\s+useradd\b", text, re.MULTILINE), (
        "no non-root user is created before the USER switch"
    )


def test_dockerfile_installs_uv_outside_root_home() -> None:
    text = _dockerfile_text()
    # uv must be installed to a world-accessible dir, not /root/.local/bin.
    assert "UV_INSTALL_DIR=" in text, (
        "uv install does not set UV_INSTALL_DIR; it lands in /root/.local/bin"
    )
    # No ENV PATH line may reference the root-only home dir (a comment may).
    path_lines = [ln for ln in text.splitlines() if re.match(r"^\s*ENV\s+PATH=", ln)]
    assert path_lines, "no ENV PATH line found"
    assert not any("/root/.local/bin" in ln for ln in path_lines), (
        "PATH still references /root/.local/bin (root-only home), "
        "unreachable by non-root user"
    )


def test_dockerfile_uv_on_path_for_nonroot_user() -> None:
    text = _dockerfile_text()
    m = re.search(r"UV_INSTALL_DIR=(\S+)", text)
    assert m, "UV_INSTALL_DIR not found"
    uv_dir = m.group(1)
    # The uv dir must be on PATH so `uv` resolves for the non-root user.
    assert uv_dir in text, f"UV_INSTALL_DIR {uv_dir} is not added to PATH"


def test_dockerfile_backend_source_readable_by_nonroot_user() -> None:
    text = _dockerfile_text()
    # The backend source must be copied into the image. The COPY runs as root,
    # producing world-readable files the non-root user can read at runtime.
    # The venv build (as appuser) needs to *write* .venv into the working dir,
    # so the dir is chowned to appuser (chown needs root privilege, so it runs
    # as root) before the USER switch, and `uv sync` runs as appuser after it.
    assert "COPY backend/ ./" in text, "backend source is not copied into the image"
    lines = text.splitlines()
    chown_idx = next(
        (i for i, ln in enumerate(lines) if re.match(r"^\s*RUN\b", ln) and "chown" in ln),
        None,
    )
    user_appuser_idx = next(
        (i for i, ln in enumerate(lines) if re.match(r"^\s*USER\s+appuser\b", ln)),
        None,
    )
    sync_idx = next(
        (i for i, ln in enumerate(lines) if re.match(r"^\s*RUN\b", ln) and "uv sync" in ln),
        None,
    )
    assert chown_idx is not None and user_appuser_idx is not None and sync_idx is not None, (
        "chown, USER appuser, or uv sync RUN command missing"
    )
    # chown (as root) must precede the switch to appuser, and uv sync must run
    # after it so .venv is written by the app user.
    assert chown_idx < user_appuser_idx < sync_idx, (
        "chown (root) must precede USER appuser, and uv sync must run after it"
    )


def test_dockerfile_entrypoint_still_command() -> None:
    text = _dockerfile_text()
    assert re.search(r'CMD\s+\["/app/docker/entrypoint.sh"\]', text), (
        "entrypoint command changed"
    )
