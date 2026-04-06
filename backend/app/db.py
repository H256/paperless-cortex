from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import load_settings

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session


@lru_cache(maxsize=4)
def _get_cached_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


@lru_cache(maxsize=4)
def _get_session_factory(database_url: str) -> sessionmaker[Session]:
    return sessionmaker(autocommit=False, autoflush=False, bind=_get_cached_engine(database_url))


def get_engine() -> Engine:
    settings = load_settings(apply_runtime_overrides=False)
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL not set")
    return _get_cached_engine(settings.database_url)


class _LazySessionLocal:
    def __call__(self) -> Session:
        settings = load_settings(apply_runtime_overrides=False)
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL not set")
        factory = _get_session_factory(settings.database_url)
        return factory()


SessionLocal = _LazySessionLocal()


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
