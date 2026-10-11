from __future__ import annotations

import os
from typing import TYPE_CHECKING

import app.config as app_config

if TYPE_CHECKING:
    from pathlib import Path


def test_dotenv_files_are_not_loaded_in_tests(tmp_path: Path) -> None:
    """tests/conftest.py disables `.env` loading so a developer file cannot leak in."""
    env_file = tmp_path / ".env"
    env_file.write_text("DOTENV_LEAK_CHECK=leaked\n", encoding="utf-8")

    app_config._load_env(tmp_path)

    assert "DOTENV_LEAK_CHECK" not in os.environ
