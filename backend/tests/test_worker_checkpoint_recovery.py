from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.services.worker_checkpoint import get_task_run_checkpoint


def test_get_task_run_checkpoint_returns_none_when_task_runs_table_missing():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with session_factory() as db:
        assert get_task_run_checkpoint(db, run_id=1) is None
