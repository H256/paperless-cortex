"""Regression tests for the root ``.dockerignore`` (issue #152).

Without a ``.dockerignore`` ``docker build`` uploads the entire working tree
to the daemon (``frontend/node_modules`` ~259M, ``backend/.venv`` ~156M,
``.git``, and any gitignored ``.env`` with real ``PAPERLESS_API_TOKEN`` /
LLM keys), and bakes the local ``node_modules`` into the frontend stage on
top of ``npm ci``. The image only needs ``frontend/``, ``backend/``,
``docker/``, and ``VERSION``.

These tests apply the ``.dockerignore`` rules to a representative set of
paths and assert the heavy/secret entries are excluded while the paths the
Dockerfile ``COPY``s remain in the build context.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERIGNORE = REPO_ROOT / ".dockerignore"


def _load_patterns() -> list[str]:
    """Return the non-comment, non-blank patterns from the .dockerignore."""
    return [
        line
        for line in DOCKERIGNORE.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _pattern_to_regex(pattern: str) -> re.Pattern:
    """Translate a single .dockerignore pattern into a regex (segment-aware)."""
    out: list[str] = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "*":
            if pattern[i : i + 2] == "**":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("".join(out))


def _is_excluded(path: str, is_dir: bool, patterns: list[str]) -> bool:
    """Apply .dockerignore rules (last matching negation wins).

    A pattern excludes a path if it matches the path itself OR any ancestor
    directory of the path (matching a parent directory excludes everything
    under it, as in gitignore).
    """
    excluded = False
    for raw in patterns:
        p = raw.strip()
        neg = p.startswith("!")
        if neg:
            p = p[1:]
        dir_only = p.endswith("/")
        if dir_only:
            p = p[:-1]
        has_slash = "/" in p
        anchored = p.startswith("/")
        if anchored:
            p = p[1:]
        rx = _pattern_to_regex(p)
        # Candidates: every ancestor directory (always dirs) plus the path
        # itself (a dir iff is_dir). A pattern excludes the path if it
        # matches the path or any ancestor directory (matching a parent
        # directory excludes everything under it, as in gitignore).
        parts = path.split("/")
        candidates = [
            ("/".join(parts[:i]), True) for i in range(1, len(parts))
        ]
        candidates.append((path, is_dir))
        matched = False
        for cand, cand_is_dir in candidates:
            if dir_only and not cand_is_dir:
                continue
            if has_slash or anchored:
                if rx.fullmatch(cand) is not None:
                    matched = True
                    break
            else:
                if any(rx.fullmatch(seg) for seg in cand.split("/")):
                    matched = True
                    break
        if matched:
            excluded = not neg
    return excluded


# Paths the Dockerfile COPYs that MUST stay in the build context.
# (frontend/dist is built inside the image by `npm run build-only`, so it is
# not needed in the context and is intentionally not asserted here.)
REQUIRED_IN_CONTEXT = [
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/src",
    "backend/pyproject.toml",
    "backend/uv.lock",
    "backend/openapi.json",
    "backend/app",
    "docker/entrypoint.sh",
    "VERSION",
]

# Heavy / secret entries that MUST be excluded from the build context.
EXCLUDED_FROM_CONTEXT = [
    "frontend/node_modules",
    "frontend/node_modules/lodash",
    "backend/.venv",
    "backend/.venv/lib",
    ".git",
    ".git/HEAD",
    ".env",
    ".env.local",
    ".session1",
    "__pycache__",
    "backend/app/__pycache__",
    "module.pyc",
    "data",
    "data/cache",
    "tmp",
    "coverage",
    "docs",
    "docs/architecture-overview.md",
    ".idea",
]


def test_dockerignore_exists() -> None:
    assert DOCKERIGNORE.is_file(), "repo root must contain a .dockerignore"


def test_dockerignore_excludes_heavy_and_secret_paths() -> None:
    patterns = _load_patterns()
    for path in EXCLUDED_FROM_CONTEXT:
        is_dir = path in {"frontend/node_modules", "backend/.venv", "data", "tmp", "coverage", "docs", "__pycache__", "backend/app/__pycache__"}
        assert _is_excluded(path, is_dir, patterns), f"{path} should be excluded"


def test_dockerignore_keeps_build_inputs() -> None:
    patterns = _load_patterns()
    for path in REQUIRED_IN_CONTEXT:
        is_dir = path in {"frontend/src", "frontend/dist", "backend/app"}
        assert not _is_excluded(path, is_dir, patterns), f"{path} must stay in context"
