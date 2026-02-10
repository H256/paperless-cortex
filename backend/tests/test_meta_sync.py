from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, Document, Tag
from app.services import paperless
from app.services.meta_sync import sync_tags_all


def test_sync_tags_all_prunes_removed_tags(api_client, monkeypatch):
    engine = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        keep = Tag(id=1, name="keep")
        stale = Tag(id=2, name="stale")
        doc = Document(id=123, title="Doc")
        doc.tags = [keep, stale]
        db.add_all([keep, stale, doc])
        db.commit()

    monkeypatch.setattr(
        paperless,
        "list_tags",
        lambda settings, page=1, page_size=200: {
            "results": [{"id": 1, "name": "keep"}],
            "next": None,
        },
    )

    with Session(engine) as db:
        total, upserted = sync_tags_all(settings=None, db=db, page_size=200)
        assert total == 1
        assert upserted == 1

    with Session(engine) as db:
        tag_ids = sorted(row.id for row in db.query(Tag).all())
        assert tag_ids == [1]
        doc = db.query(Document).filter(Document.id == 123).one()
        assert [tag.id for tag in doc.tags] == [1]
