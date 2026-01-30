from __future__ import annotations

import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import sqlalchemy  # noqa: F401
except ModuleNotFoundError:
    sqlalchemy = types.ModuleType("sqlalchemy")

    def _placeholder(*_args, **_kwargs):
        return None

    class _DeclarativeBase:
        metadata = object()

    class _Mapped:
        def __class_getitem__(cls, _item):
            return cls

    sqlalchemy.create_engine = _placeholder
    sqlalchemy.and_ = _placeholder
    sqlalchemy.exists = _placeholder
    sqlalchemy.func = types.SimpleNamespace()
    sqlalchemy.delete = _placeholder
    sqlalchemy.Boolean = sqlalchemy.Column = sqlalchemy.ForeignKey = sqlalchemy.Integer = _placeholder
    sqlalchemy.String = sqlalchemy.Table = sqlalchemy.Text = _placeholder

    orm = types.ModuleType("sqlalchemy.orm")
    orm.Session = type("Session", (), {})
    orm.sessionmaker = lambda *args, **kwargs: _placeholder
    orm.DeclarativeBase = _DeclarativeBase
    orm.Mapped = _Mapped
    orm.mapped_column = _placeholder
    orm.relationship = _placeholder

    sqlalchemy.orm = orm
    sys.modules["sqlalchemy"] = sqlalchemy
    sys.modules["sqlalchemy.orm"] = orm

from app.main import api  # noqa: E402


def main() -> None:
    output_path = ROOT / "openapi.json"
    output_path.write_text(json.dumps(api.openapi(), indent=2), encoding="utf-8")
    print(f"Wrote OpenAPI spec to {output_path}")


if __name__ == "__main__":
    main()
