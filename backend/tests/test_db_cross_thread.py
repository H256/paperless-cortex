"""Regression test for issue #144: production SQLite engine must be thread-safe.

FastAPI serves synchronous route handlers from a worker-thread pool, so a
pooled SQLite connection created in one thread is handed out to another.
Without ``connect_args={"check_same_thread": False}`` for SQLite URLs,
pysqlite raises ``sqlite3.ProgrammingError`` when the recycled connection
executes a statement in the new thread.

Unlike the rest of the suite (whose own engines all pass
``check_same_thread=False``), this test drives the *production* engine
factory in ``app.db`` end to end.
"""

import os
import threading
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db import SessionLocal, get_engine


def _run_in_thread(func: Callable[[], None]) -> list[BaseException]:
    """Run ``func`` in a fresh thread; return any exception it raised."""
    errors: list[BaseException] = []

    def target() -> None:
        try:
            func()
        except BaseException as exc:  # captured and asserted in main thread
            errors.append(exc)

    worker = threading.Thread(target=target)
    worker.start()
    worker.join()
    return errors


@pytest.fixture()
def production_engine(tmp_path: Path) -> Iterator[Engine]:
    """Point the production engine factory at a unique temporary SQLite file."""
    db_file = tmp_path / f"cross_thread_{uuid.uuid4().hex}.sqlite3"
    # ?check_same_thread=true forces pysqlite's native thread-affine default;
    # SQLAlchemy 2.0 otherwise silently overrides it to False for file-based
    # SQLite URLs, which would mask the regression this test pins down.
    previous_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_file}?check_same_thread=true"
    # Unique URL per run -> unique lru_cache key in app.db -> fresh engine
    # with an empty QueuePool.
    engine = get_engine()
    try:
        yield engine
    finally:
        engine.dispose()
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url


def test_sqlite_engine_survives_cross_thread_pool_reuse(production_engine: Engine) -> None:
    # Thread B is started before thread A and stays alive throughout:
    # pysqlite's check_same_thread compares thread ids, and CPython can hand
    # a fresh thread the id of a just-exited one, which would mask the
    # cross-thread error. FastAPI's worker pool is long-lived, which is the
    # production shape being reproduced.
    b_may_run = threading.Event()
    errors_b: list[BaseException] = []
    seen: list[str] = []

    def thread_b() -> None:
        b_may_run.wait(timeout=10)
        # The pool holds exactly one recycled connection (created in thread A),
        # so B's first checkout reuses it across threads.
        try:
            session = SessionLocal()
            rows = session.execute(text("SELECT value FROM t")).all()
            seen.extend(row[0] for row in rows)
            session.commit()
            session.close()
        except BaseException as exc:  # captured and asserted in main thread
            errors_b.append(exc)

    b_worker = threading.Thread(target=thread_b)
    b_worker.start()

    def thread_a() -> None:
        session = SessionLocal()
        session.execute(text("CREATE TABLE t (value TEXT NOT NULL)"))
        session.execute(text("INSERT INTO t (value) VALUES ('from-thread-a')"))
        session.commit()
        session.close()  # returns the connection to the QueuePool

    errors_a = _run_in_thread(thread_a)
    assert not errors_a, f"thread A raised {errors_a[0]!r}"
    b_may_run.set()
    b_worker.join()
    assert not errors_b, f"thread B raised {errors_b[0]!r}"
    assert seen == ["from-thread-a"]
