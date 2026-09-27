#!/usr/bin/env python3
"""Keep .gitea/workflows in sync with .github/workflows.

ForgeJO's Actions reads .gitea/workflows, but the canonical workflow sources
live in .github/workflows. This script mirrors each GitHub workflow into the
Gitea directory, rewriting only the self-referential path strings so the
mirrored files re-trigger themselves when they change.

Usage:
    python scripts/sync_gitea_workflows.py          # write mirrored files
    python scripts/sync_gitea_workflows.py --check  # exit 1 on any drift

The parity test (tests/test_gitea_workflow_parity.py) relies on --check.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GITHUB_DIR = REPO_ROOT / ".github" / "workflows"
GITEA_DIR = REPO_ROOT / ".gitea" / "workflows"
SOURCE_PATH = ".github/workflows/"
TARGET_PATH = ".gitea/workflows/"


def transform(text: str) -> str:
    return text.replace(SOURCE_PATH, TARGET_PATH)


def sync() -> int:
    GITEA_DIR.mkdir(parents=True, exist_ok=True)
    for src in sorted(GITHUB_DIR.glob("*.yml")):
        (GITEA_DIR / src.name).write_text(transform(src.read_text(encoding="utf-8")))
    return 0


def check() -> int:
    drifted = False
    for src in sorted(GITHUB_DIR.glob("*.yml")):
        target = GITEA_DIR / src.name
        expected = transform(src.read_text(encoding="utf-8"))
        actual = target.read_text(encoding="utf-8") if target.exists() else None
        if actual != expected:
            drifted = True
            print(f"drift: {src.name} (expected {len(expected)} bytes, "
                  f"actual {len(actual) if actual is not None else 'missing'})")
    return 1 if drifted else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="only verify, do not write")
    args = parser.parse_args()
    return check() if args.check else sync()


if __name__ == "__main__":
    sys.exit(main())
