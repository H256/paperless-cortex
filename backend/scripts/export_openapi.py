from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if importlib.util.find_spec("sqlalchemy") is None:
    sqlalchemy: Any = types.ModuleType("sqlalchemy")

    def _placeholder(*_args: Any, **_kwargs: Any) -> None:
        return None

    class _DeclarativeBase:
        metadata: object = object()

    class _Mapped:
        def __class_getitem__(cls, _item: Any) -> type[_Mapped]:
            return cls

    sqlalchemy.create_engine = _placeholder
    sqlalchemy.and_ = _placeholder
    sqlalchemy.exists = _placeholder
    sqlalchemy.func = types.SimpleNamespace()
    sqlalchemy.delete = _placeholder
    sqlalchemy.Boolean = sqlalchemy.Column = sqlalchemy.ForeignKey = sqlalchemy.Integer = _placeholder
    sqlalchemy.String = sqlalchemy.Table = sqlalchemy.Text = _placeholder

    orm: Any = types.ModuleType("sqlalchemy.orm")
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
