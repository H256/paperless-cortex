"""Migration sanity tests (AUDIT BT-009, issue #180).

Catches:
- Duplicate/branched alembic heads (single-head invariant).
- Migration files that fail to import or lack upgrade/downgrade.
- Model-vs-migration schema drift: ``alembic upgrade head`` on a scratch
  SQLite DB (with batch mode) must produce the same tables and columns as
  ``Base.metadata.create_all``.
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from sqlalchemy import create_engine, inspect

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_DIR = BACKEND_ROOT / "alembic"


# ---------------------------------------------------------------------------
# 1. Single-head invariant
# ---------------------------------------------------------------------------


def test_alembic_single_head() -> None:
    """There must be exactly one migration head."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    assert len(heads) == 1, f"Expected exactly 1 head, got {len(heads)}: {heads}"


# ---------------------------------------------------------------------------
# 2. All migration files are importable and have upgrade/downgrade
# ---------------------------------------------------------------------------


def test_all_migration_files_importable_and_well_formed() -> None:
    """Every version file must define upgrade() and downgrade()."""
    version_dir = ALEMBIC_DIR / "versions"
    files = sorted(version_dir.glob("*.py"))
    assert files, f"No migration files found in {version_dir}"

    for f in files:
        if f.name == "__init__.py":
            continue
        import importlib.util

        spec = importlib.util.spec_from_file_location(f.stem, f)
        assert spec is not None, f"Could not create spec for {f.name}"
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        assert hasattr(module, "upgrade"), f"{f.name} missing upgrade()"
        assert hasattr(module, "downgrade"), f"{f.name} missing downgrade()"
        assert callable(module.upgrade), f"{f.name}.upgrade is not callable"
        assert callable(module.downgrade), f"{f.name}.downgrade is not callable"


# ---------------------------------------------------------------------------
# 3. Schema drift: alembic upgrade head vs Base.metadata.create_all
# ---------------------------------------------------------------------------


def _run_alembic_upgrade(db_path: Path) -> None:
    """Run ``alembic upgrade head`` against *db_path*.

    The production migrations are PostgreSQL-oriented and use direct
    ``op.create_foreign_key`` / ``op.drop_constraint`` (ALTER TABLE ... ADD
    CONSTRAINT), which the SQLite dialect does not support. SQLite does not
    enforce foreign-key constraints at DDL time, so we patch the SQLite
    dialect's ``add_constraint`` / ``drop_constraint`` to no-ops for the
    duration of the upgrade. This lets the migrations run to completion on a
    scratch SQLite DB; the resulting tables and columns are then compared
    against ``Base.metadata``.
    """
    import os
    import textwrap
    import unittest.mock as mock

    from alembic.config import Config
    from alembic.ddl.sqlite import SQLiteImpl

    from alembic import command

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    ini = Path(tempfile.mktemp(prefix="alembic_ini_", suffix=".ini"))
    ini.write_text(
        textwrap.dedent(
            f"""\
            [alembic]
            script_location = {ALEMBIC_DIR}
            sqlalchemy.url = sqlite:///{db_path}

            [loggers]
            keys = root,sqlalchemy,alembic

            [handlers]
            keys = console

            [formatters]
            keys = generic

            [logger_root]
            level = WARN
            handlers = console
            qualname =

            [logger_sqlalchemy]
            level = WARN
            handlers =
            qualname = sqlalchemy.engine

            [logger_alembic]
            level = INFO
            handlers =
            qualname = alembic

            [handler_console]
            class = StreamHandler
            args = (sys.stderr,)
            level = NOTSET
            formatter = generic

            [formatter_generic]
            format = %(levelname)-5.5s [%(name)s] %(message)s
            """
        )
    )

    cfg = Config(str(ini))

    def _alter_column(self, table_name, column_name, *, name=None, type_=None, **kw):
        # SQLite supports in-place column renames; type changes it cannot do
        # (no ALTER COLUMN ... TYPE). Perform the rename via raw SQL so the
        # resulting schema matches the model; ignore type-only changes.
        if name is not None:
            eng = create_engine(f"sqlite:///{db_path}")
            with eng.begin() as conn:
                conn.exec_driver_sql(
                    f'ALTER TABLE {table_name} RENAME COLUMN {column_name} TO {name}'
                )
            eng.dispose()

    # SQLite cannot ALTER constraints/columns or add FKs in place (PostgreSQL
    # supports these; SQLite does not enforce them at DDL time). No-op them so
    # the migrations run to completion; only the resulting tables/columns are
    # compared, not the constraints themselves.
    with mock.patch.object(SQLiteImpl, "add_constraint", return_value=None), \
         mock.patch.object(SQLiteImpl, "drop_constraint", return_value=None), \
         mock.patch.object(SQLiteImpl, "create_foreign_key", return_value=None, create=True), \
         mock.patch.object(SQLiteImpl, "alter_column", side_effect=_alter_column, autospec=True):
        command.upgrade(cfg, "head")


def test_alembic_upgrade_head_matches_model_metadata() -> None:
    """``alembic upgrade head`` on a scratch DB must produce the same schema
    as ``Base.metadata.create_all`` (tables and columns)."""
    from app.models import Base

    a = Path(tempfile.gettempdir()) / f"mig_a_{uuid.uuid4().hex}.db"
    _run_alembic_upgrade(a)
    eng_a = create_engine(f"sqlite:///{a}")
    insp_a = inspect(eng_a)
    tables_a = set(insp_a.get_table_names())
    cols_a = {t: [c["name"] for c in insp_a.get_columns(t)] for t in tables_a}

    b = Path(tempfile.gettempdir()) / f"mig_b_{uuid.uuid4().hex}.db"
    eng_b = create_engine(f"sqlite:///{b}")
    Base.metadata.create_all(eng_b)
    insp_b = inspect(eng_b)
    tables_b = set(insp_b.get_table_names())
    cols_b = {t: [c["name"] for c in insp_b.get_columns(t)] for t in tables_b}

    missing_in_migrations = tables_b - tables_a
    extra_in_migrations = tables_a - tables_b - {"alembic_version"}

    assert not missing_in_migrations, (
        f"Tables in Base.metadata but missing from migrations: {missing_in_migrations}"
    )
    assert not extra_in_migrations, (
        f"Tables in migrations but missing from Base.metadata: {extra_in_migrations}"
    )

    col_diff = {
        t: (set(cols_a[t]) ^ set(cols_b.get(t, [])))
        for t in tables_a
        if t != "alembic_version" and set(cols_a[t]) != set(cols_b.get(t, []))
    }
    assert not col_diff, f"Column drift between migrations and model: {col_diff}"
