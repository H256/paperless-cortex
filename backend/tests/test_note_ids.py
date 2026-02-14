from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base
from app.models import Document
from app.models import DocumentNote
from app.services.note_ids import next_local_note_id


def test_next_local_note_id_defaults_to_minus_one_when_no_notes() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        assert next_local_note_id(db) == -1


def test_next_local_note_id_decrements_existing_negative_min() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Document(id=9991, title="Doc 9991", created="2026-02-14T00:00:00+00:00"))
        db.add(DocumentNote(id=-5, document_id=9991, note="local", created="2026-02-14T00:00:00+00:00"))
        db.commit()
    with Session(engine) as db:
        assert next_local_note_id(db) == -6
