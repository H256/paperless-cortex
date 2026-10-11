"""Regression test for issue #145: CI workflows must run on the ForgeJO host.

The only remote is ForgeJO, whose Actions reads ``.gitea/workflows``. The
The canonical workflow sources live in ``.github/workflows`` (GitHub-only), so a
mirror is maintained in ``.gitea/workflows`` by
``scripts/sync_gitea_workflows.py``. This test pins the mirror's contract in
two complementary ways:

* ``test_gitea_workflow_mirror_exists_and_matches`` is an *independent* oracle:
  it compares each committed ``.gitea`` file against its ``.github`` source
  using a plain path rewrite (not the script's transform), so it catches a
  drifted mirror or a buggy transform even if the script and the mirror agree
  with each other;
* ``test_sync_script_check_reports_no_drift`` drives the real script's
  ``--check`` mode, so the CI gate's exit-code semantics are exercised too.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "sync_gitea_workflows.py"
GITHUB_DIR = REPO_ROOT / ".github" / "workflows"
GITEA_DIR = REPO_ROOT / ".gitea" / "workflows"


def test_gitea_workflow_mirror_exists_and_matches() -> None:
    github_files = sorted(GITHUB_DIR.glob("*.yml"))
    assert github_files, "expected at least one .github/workflows/*.yml source"

    for src in github_files:
        target = GITEA_DIR / src.name
        assert target.exists(), f"missing mirror: {target.relative_to(REPO_ROOT)}"
        expected = src.read_text(encoding="utf-8").replace(
            ".github/workflows/", ".gitea/workflows/"
        )
        actual = target.read_text(encoding="utf-8")
        assert actual == expected, (
            f"{src.name} mirror diverges from its .github source "
            "(run `python scripts/sync_gitea_workflows.py`)"
        )


def test_sync_script_check_reports_no_drift() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"sync_gitea_workflows.py --check reported drift:\n{result.stdout}"
    )
