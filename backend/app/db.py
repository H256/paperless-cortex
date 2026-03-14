from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import load_settings

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session


def get_engine() -> Engine:
    settings = load_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL not set")
    return create_engine(settings.database_url, pool_pre_ping=True)


class _LazySessionLocal:
    def __call__(self) -> Session:
        factory = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
        return factory()


SessionLocal = _LazySessionLocal()


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
