from __future__ import annotations

from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert


def upsert_on_conflict(
    model: Any,
    values: dict[str, Any],
    *,
    conflict_columns: list[str],
    update_columns: list[str] | None = None,
) -> "_DialectAwareUpsert":
    """Build an ``INSERT ... ON CONFLICT DO UPDATE`` statement for a model.

    Works on both SQLite and PostgreSQL (the two supported backends).
    Columns in ``update_columns`` are updated on conflict; all other columns
    keep their existing values.
    """
    update_columns = update_columns if update_columns is not None else list(values)
    sqlite_base = sqlite_insert(model).values(**values)
    sqlite_stmt = sqlite_base.on_conflict_do_update(
        index_elements=[getattr(model, col) for col in conflict_columns],
        set_={col: sqlite_base.excluded[col] for col in update_columns},
    )
    pg_base = pg_insert(model).values(**values)
    pg_stmt = pg_base.on_conflict_do_update(
        index_elements=[getattr(model, col) for col in conflict_columns],
        set_={col: pg_base.excluded[col] for col in update_columns},
    )
    return _DialectAwareUpsert(sqlite_stmt, pg_stmt)


class _DialectAwareUpsert:
    """Picks the dialect-appropriate statement at execution time."""

    def __init__(self, sqlite_stmt: Any, pg_stmt: Any) -> None:
        self._sqlite = sqlite_stmt
        self._pg = pg_stmt

    def __call__(self, session: Any, params: dict[str, Any] | None = None) -> Any:
        dialect = session.get_bind().dialect.name
        if dialect == "sqlite":
            return session.execute(self._sqlite, params)
        return session.execute(self._pg, params)
