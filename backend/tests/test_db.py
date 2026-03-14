from __future__ import annotations

from typing import Any

from app import db as db_module


def test_get_engine_reuses_cached_engine(monkeypatch: Any) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///cached-engine-test.db")

    first = db_module.get_engine()
    second = db_module.get_engine()

    assert first is second
