from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, SuggestionAudit
from app.services.writeback.writeback_execution import execute_calls_with_audit


def _call(doc_id: int) -> Any:
    return SimpleNamespace(doc_id=doc_id, method="PATCH", path=f"/documents/{doc_id}/", payload={})


def _db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def _run(db: Session, calls: list[Any], fail_doc: int, **kwargs: Any) -> set[int]:
    def execute(_settings: Any, _db: Session, call: Any) -> None:
        if call.doc_id == fail_doc:
            raise RuntimeError("paperless down")

    return execute_calls_with_audit(
        settings=None,
        db=db,
        calls=calls,
        dry_run=False,
        execute_call=execute,
        cleanup_pending_rows_after_patch=lambda *_a: None,
        reviewed_timestamp_for_doc=lambda *_a: "2026-01-01T00:00:00+00:00",
        logger=logging.getLogger("test"),
        **kwargs,
    )


def test_audit_rows_survive_a_later_failing_call() -> None:
    db = _db()
    with pytest.raises(RuntimeError):
        _run(db, [_call(1), _call(2)], fail_doc=2)
    db.commit()
    audited = {row.doc_id for row in db.query(SuggestionAudit).all()}
    assert audited == {1}


def test_failed_doc_is_not_audited_when_errors_are_collected() -> None:
    db = _db()
    errors: list[int] = []
    done = _run(
        db,
        [_call(1), _call(2)],
        fail_doc=2,
        on_call_error=lambda call, _exc: errors.append(call.doc_id),
    )
    db.commit()
    assert done == {1}
    assert errors == [2]
    assert {row.doc_id for row in db.query(SuggestionAudit).all()} == {1}
