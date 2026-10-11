"""Tests for the AI upsert helpers (issue #208).

The old delete-then-insert pattern is non-atomic: its delete and insert are
separate transactions, so another session can insert the same composite key
in between, and the first session's insert then hits the composite PK and
raises an unhandled IntegrityError.

These tests reproduce that interleaving deterministically (explicit commits
between statements) and verify the ON CONFLICT upsert survives it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from app.models import (
    Document,
    DocumentPageNote,
    DocumentSectionSummary,
    DocumentSuggestion,
)
from app.services.ai.hierarchical_storage import (
    replace_section_summaries,
    upsert_page_note,
)
from app.services.ai.suggestion_store import upsert_suggestion


def _seed_document(db: Any) -> None:
    db.add(Document(id=1, title="t"))
    db.commit()


def test_old_delete_then_insert_pattern_can_conflict(session_factory: Any) -> None:
    """Reproduce the hazard: A deletes + commits, B inserts the same key,
    A then inserts it -> IntegrityError on the old pattern."""
    with session_factory() as db:
        _seed_document(db)
        upsert_suggestion(db, 1, "src", '{"v":0}')  # existing row R0

    # Session A: delete R0, commit (old pattern, delete split from insert)
    with session_factory() as a:
        a.execute(
            delete(DocumentSuggestion).where(
                DocumentSuggestion.doc_id == 1,
                DocumentSuggestion.source == "src",
            )
        )
        a.commit()

    # Session B: insert the same key, commit
    with session_factory() as b:
        b.add(
            DocumentSuggestion(
                doc_id=1,
                source="src",
                payload='{"v":"b"}',
                created_at="c",
                model_name=None,
                processed_at="p",
            )
        )
        b.commit()

    # Session A: now insert the same key (old pattern) -> conflicts with B's row
    with session_factory() as a:
        a.add(
            DocumentSuggestion(
                doc_id=1,
                source="src",
                payload='{"v":"a"}',
                created_at="c",
                model_name=None,
                processed_at="p",
            )
        )
        try:
            a.commit()
            raised = False
        except IntegrityError:
            raised = True
    assert raised, (
        "expected the old delete-then-insert pattern to raise IntegrityError "
        "when another session inserted the same key in between"
    )


def test_upsert_suggestion_survives_interleaved_same_key(session_factory: Any) -> None:
    """Same interleaving, but the upserts are atomic ON CONFLICT: no
    IntegrityError, and exactly one consistent row remains."""
    with session_factory() as db:
        _seed_document(db)
        upsert_suggestion(db, 1, "src", '{"v":0}')

    # Session A: upsert (single atomic statement), commit
    with session_factory() as a:
        upsert_suggestion(a, 1, "src", '{"v":"a"}')

    # Session B: upsert the same key, commit
    with session_factory() as b:
        upsert_suggestion(b, 1, "src", '{"v":"b"}')

    # Session A again: upsert the same key -> must update, not conflict
    with session_factory() as a:
        upsert_suggestion(a, 1, "src", '{"v":"a2"}')

    with session_factory() as db:
        rows = db.query(DocumentSuggestion).filter_by(doc_id=1, source="src").all()
    assert len(rows) == 1, f"expected exactly 1 row, got {len(rows)}"
    assert rows[0].payload == '{"v":"a2"}'


def test_upsert_page_note_survives_interleaved_same_key(session_factory: Any) -> None:
    with session_factory() as db:
        _seed_document(db)
        upsert_page_note(
            db, doc_id=1, page=1, source="s", payload={"text": "0"}, status="ok"
        )

    with session_factory() as a:
        upsert_page_note(
            a, doc_id=1, page=1, source="s", payload={"text": "a"}, status="ok"
        )

    with session_factory() as b:
        upsert_page_note(
            b, doc_id=1, page=1, source="s", payload={"text": "b"}, status="ok"
        )

    with session_factory() as a:
        upsert_page_note(
            a, doc_id=1, page=1, source="s", payload={"text": "a2"}, status="ok"
        )

    with session_factory() as db:
        rows = (
            db.query(DocumentPageNote)
            .filter_by(doc_id=1, page=1, source="s")
            .all()
        )
    assert len(rows) == 1, f"expected exactly 1 row, got {len(rows)}"
    assert rows[0].notes_text == "a2"


def test_replace_section_summaries_survives_interleaved_same_key(session_factory: Any) -> None:
    with session_factory() as db:
        _seed_document(db)
        replace_section_summaries(
            db, doc_id=1, source="s", summaries=[("1-2", {"text": "0"})]
        )

    with session_factory() as a:
        replace_section_summaries(
            a,
            doc_id=1,
            source="s",
            summaries=[("1-2", {"text": "A"}), ("3-4", {"text": "B"})],
        )

    with session_factory() as b:
        replace_section_summaries(
            b,
            doc_id=1,
            source="s",
            summaries=[("1-2", {"text": "A2"}), ("3-4", {"text": "B2"})],
        )

    with session_factory() as db:
        rows = (
            db.query(DocumentSectionSummary)
            .filter_by(doc_id=1, source="s")
            .all()
        )
    keys = sorted(r.section_key for r in rows)
    assert keys == ["1-2", "3-4"], f"expected exactly 2 sections, got {keys}"


def test_upsert_suggestion_idempotent_update_in_place(session_factory: Any) -> None:
    with session_factory() as db:
        _seed_document(db)
        upsert_suggestion(
            db, 1, "src", '{"a":1}', model_name="m1", processed_at="2026-01-01T00:00:00+00:00"
        )
        first_created = (
            db.query(DocumentSuggestion)
            .filter_by(doc_id=1, source="src")
            .one()
            .created_at
        )
        upsert_suggestion(
            db, 1, "src", '{"a":2}', model_name="m2", processed_at="2026-02-01T00:00:00+00:00"
        )
        row = (
            db.query(DocumentSuggestion)
            .filter_by(doc_id=1, source="src")
            .one()
        )
    assert row.payload == '{"a":2}'
    assert row.model_name == "m2"
    # created_at must advance on re-upsert (matches the old delete+insert reset
    # semantics that the pipeline staleness check relies on).
    assert row.created_at != first_created
    assert row.created_at == "2026-02-01T00:00:00+00:00"
