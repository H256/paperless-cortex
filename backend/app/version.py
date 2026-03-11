from __future__ import annotations

import re
from pathlib import Path


def _read_pyproject_version(path: Path) -> str | None:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r'(?m)^version = "([^"]+)"\s*$', content)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def _read_repo_version() -> str:
    backend_root = Path(__file__).resolve().parents[1]
    project_root = Path(__file__).resolve().parents[2]
    candidates = [
        project_root / "VERSION",
        backend_root / "VERSION",
    ]
    for version_file in candidates:
        try:
            value = version_file.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value:
            return value

    pyproject_candidates = [
        backend_root / "pyproject.toml",
        project_root / "pyproject.toml",
    ]
    for pyproject in pyproject_candidates:
        pyproject_version = _read_pyproject_version(pyproject)
        if pyproject_version:
            return pyproject_version
    return "0.0.0"


APP_VERSION = _read_repo_version()
API_VERSION = APP_VERSION
