from __future__ import annotations

from pathlib import Path


def _read_repo_version() -> str:
    root = Path(__file__).resolve().parents[2]
    version_file = root / "VERSION"
    try:
        value = version_file.read_text(encoding="utf-8").strip()
    except Exception:
        return "0.0.0"
    return value or "0.0.0"


APP_VERSION = _read_repo_version()
API_VERSION = APP_VERSION
