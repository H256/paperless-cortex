from __future__ import annotations

import json

from app.models import (
    Document,
    DocumentPendingCorrespondent,
    DocumentPendingTag,
    SuggestionAudit,
    Tag,
)
from app.services.writeback.writeback_preview import (
    local_writeback_candidate_doc_ids,
    preview_for_doc_ids,
)


def test_preview_for_doc_ids_builds_changed_item_with_pending_values(session_factory, monkeypatch):
    from app.config import load_settings
    from app.services import paperless

    with session_factory() as db:
        local_tag = Tag(id=9901, name="LocalTag")
        doc = Document(id=901, title="Local title")
        doc.tags = [local_tag]
        db.add(local_tag)
        db.add(doc)
        db.add(
            DocumentPendingTag(
                doc_id=901,
                names_json=json.dumps(["PendingTag"], ensure_ascii=False),
                updated_at="2026-02-20T10:00:00+00:00",
            )
        )
        db.add(
            DocumentPendingCorrespondent(
                doc_id=901,
                name="Pending Corr",
                updated_at="2026-02-20T10:00:00+00:00",
            )
        )
        db.commit()

        monkeypatch.setattr(
            paperless,
            "get_documents_cached",
            lambda *_args, **_kwargs: {
                901: {
                    "id": 901,
                    "title": "Remote title",
                    "created": None,
                    "correspondent": None,
                    "tags": [],
                    "notes": [],
                }
            },
        )

        items = preview_for_doc_ids(load_settings(), db, [901])
        assert len(items) == 1
        item = items[0]
        assert item.doc_id == 901
        assert item.changed is True
        assert item.title.changed is True
        assert isinstance(item.tags.proposed, dict)
        assert item.tags.proposed.get("pending_names") == ["PendingTag"]
        assert isinstance(item.correspondent.proposed, dict)
        assert item.correspondent.proposed.get("pending_name") == "Pending Corr"


def test_preview_for_doc_ids_uses_fallback_document_fetch(session_factory, monkeypatch):
    from app.config import load_settings
    from app.services import paperless

    with session_factory() as db:
        db.add(Document(id=902, title="Doc 902"))
        db.commit()

        called = {"fallback": 0}
        monkeypatch.setattr(paperless, "get_documents_cached", lambda *_args, **_kwargs: {})

        def _fallback(*_args, **_kwargs):
            called["fallback"] += 1
            return {
                "id": 902,
                "title": "Remote 902",
                "created": None,
                "correspondent": None,
                "tags": [],
                "notes": [],
            }

        monkeypatch.setattr(paperless, "get_document_cached", _fallback)

        items = preview_for_doc_ids(load_settings(), db, [902])
        assert len(items) == 1
        assert items[0].doc_id == 902
        assert called["fallback"] == 1


def test_local_writeback_candidate_doc_ids_dedupes_sources(session_factory):
    with session_factory() as db:
        db.add(
            SuggestionAudit(
                doc_id=903,
                action="apply_to_document:title",
                source="paperless_ocr",
                field="title",
                old_value="old",
                new_value="new",
                created_at="2026-02-20T10:00:00+00:00",
            )
        )
        db.add(
            SuggestionAudit(
                doc_id=904,
                action="ignored_action",
                source="paperless_ocr",
                field="title",
                old_value="old",
                new_value="new",
                created_at="2026-02-20T10:00:00+00:00",
            )
        )
        db.add(
            DocumentPendingTag(
                doc_id=903,
                names_json=json.dumps(["TagA"], ensure_ascii=False),
                updated_at="2026-02-20T10:00:00+00:00",
            )
        )
        db.add(
            DocumentPendingCorrespondent(
                doc_id=905,
                name="Corr A",
                updated_at="2026-02-20T10:00:00+00:00",
            )
        )
        db.commit()

        result = local_writeback_candidate_doc_ids(db)
        assert 903 in result
        assert 905 in result
        assert 904 not in result
        assert result.count(903) == 1
