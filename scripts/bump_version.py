from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"


def read_version() -> tuple[int, int, int]:
    value = VERSION_FILE.read_text(encoding="utf-8").strip()
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        raise ValueError(f"Unsupported VERSION format: {value!r}")
    return tuple(int(part) for part in match.groups())


def bumped(major: int, minor: int, patch: int, part: str) -> str:
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"Unsupported bump part: {part}")


def main() -> None:
    part = sys.argv[1] if len(sys.argv) > 1 else "patch"
    current = read_version()
    next_version = bumped(*current, part=part)
    VERSION_FILE.write_text(f"{next_version}\n", encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "sync_version.py")], check=True)
    print(f"Bumped version to {next_version}")


if __name__ == "__main__":
    main()
