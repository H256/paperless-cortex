from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from app.models import Document, DocumentSuggestion, Tag
from app.services.writeback.writeback_preview import (
    ai_generated_fields_for_docs,
    build_writeback_item,
    preview_for_doc_ids,
)

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def test_ai_generated_fields_for_docs_parses_payload(
    session_factory: Any,
) -> None:
    with session_factory() as db:
        db.add(
            DocumentSuggestion(
                doc_id=701,
                source="paperless_ocr",
                payload=json.dumps(
                    {"title": "AI Title", "correspondent": "AI Corp", "tags": ["x"]},
                    ensure_ascii=False,
                ),
                created_at="2026-01-01T00:00:00+00:00",
                model_name="m",
                processed_at="2026-01-01T00:00:00+00:00",
            )
        )
        db.add(
            DocumentSuggestion(
                doc_id=702,
                source="paperless_ocr",
                payload="not-json",
                created_at="2026-01-01T00:00:00+00:00",
                model_name="m",
                processed_at="2026-01-01T00:00:00+00:00",
            )
        )
        db.commit()
        result = ai_generated_fields_for_docs(db, [701, 702, 703])
        assert result.get(701) == {"title", "correspondent", "tags"}
        assert 702 not in result
        assert 703 not in result


def test_build_writeback_item_marks_ai_generated_fields() -> None:
    doc = Document(id=801, title="Local title")
    remote_doc = {
        "id": 801,
        "title": "Remote title",
        "created": None,
        "correspondent": None,
        "tags": [],
        "notes": [],
    }
    item = build_writeback_item(
        local_doc=doc,
        remote_doc=remote_doc,
        correspondents_by_id={},
        tags_by_id={},
        ai_generated_fields={"title", "tags"},
    )
    assert item.title.ai_generated is True
    assert item.tags.ai_generated is True
    assert item.correspondent.ai_generated is False
    assert item.note.ai_generated is False


def test_preview_for_doc_ids_marks_ai_generated(
    session_factory: Any, monkeypatch: MonkeyPatch
) -> None:
    from app.config import load_settings
    from app.services.integrations import paperless

    with session_factory() as db:
        doc = Document(id=902, title="Local title")
        db.add(doc)
        db.add(
            DocumentSuggestion(
                doc_id=902,
                source="paperless_ocr",
                payload=json.dumps({"title": "AI Title", "tags": ["x"]}, ensure_ascii=False),
                created_at="2026-01-01T00:00:00+00:00",
                model_name="m",
                processed_at="2026-01-01T00:00:00+00:00",
            )
        )
        db.commit()
        monkeypatch.setattr(
            paperless,
            "get_documents_cached",
            lambda *_args, **_kwargs: {
                902: {
                    "id": 902,
                    "title": "Remote title",
                    "created": None,
                    "correspondent": None,
                    "tags": [],
                    "notes": [],
                }
            },
        )
        items = preview_for_doc_ids(load_settings(), db, [902])
        assert len(items) == 1
        assert items[0].title.ai_generated is True
        assert items[0].tags.ai_generated is True
        assert items[0].correspondent.ai_generated is False
