from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"
BACKEND_PYPROJECT = ROOT / "backend" / "pyproject.toml"
FRONTEND_PACKAGE = ROOT / "frontend" / "package.json"
FRONTEND_VERSION_TS = ROOT / "frontend" / "src" / "generated" / "version.ts"


def read_version() -> str:
    value = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError("VERSION file is empty")
    return value


def update_backend_pyproject(version: str) -> None:
    content = BACKEND_PYPROJECT.read_text(encoding="utf-8")
    pattern = r'(?m)^version = ".*"\r?$'
    if not re.search(pattern, content):
        raise RuntimeError("backend/pyproject.toml version field not found")
    updated = re.sub(pattern, f'version = "{version}"', content, count=1)
    BACKEND_PYPROJECT.write_text(updated, encoding="utf-8")


def update_frontend_package(version: str) -> None:
    content = FRONTEND_PACKAGE.read_text(encoding="utf-8")
    pattern = r'(?m)^  "version": ".*",\r?$'
    if not re.search(pattern, content):
        raise RuntimeError("frontend/package.json version field not found")
    updated = re.sub(pattern, f'  "version": "{version}",', content, count=1)
    FRONTEND_PACKAGE.write_text(updated, encoding="utf-8")


def write_frontend_constant(version: str) -> None:
    FRONTEND_VERSION_TS.parent.mkdir(parents=True, exist_ok=True)
    FRONTEND_VERSION_TS.write_text(
        f"export const FRONTEND_VERSION = '{version}'\n",
        encoding="utf-8",
    )


def main() -> None:
    version = read_version()
    update_backend_pyproject(version)
    update_frontend_package(version)
    write_frontend_constant(version)
    print(f"Synchronized version {version}")


if __name__ == "__main__":
    main()
