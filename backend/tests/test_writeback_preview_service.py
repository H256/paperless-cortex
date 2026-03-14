from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from app.models import (
    Correspondent,
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
from app.services.writeback.writeback_preview_cache import (
    get_cached_writeback_candidate_doc_ids,
    get_cached_writeback_preview,
    invalidate_writeback_preview_cache,
)

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def test_preview_for_doc_ids_builds_changed_item_with_pending_values(
    session_factory: Any, monkeypatch: MonkeyPatch
) -> None:
    from app.config import load_settings
    from app.services.integrations import paperless

    with session_factory() as db:
        local_corr = Correspondent(id=8801, name="Local Corr")
        local_tag = Tag(id=9901, name="LocalTag")
        remote_tag = Tag(id=9902, name="RemoteTag")
        remote_corr = Correspondent(id=8802, name="Remote Corr")
        doc = Document(id=901, title="Local title", correspondent_id=8801)
        doc.tags = [local_tag]
        db.add(local_corr)
        db.add(local_tag)
        db.add(remote_tag)
        db.add(remote_corr)
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
                    "correspondent": 8802,
                    "tags": [9902],
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
        assert item.tags.original == {"ids": [9902], "names": ["RemoteTag"]}
        assert isinstance(item.correspondent.proposed, dict)
        assert item.correspondent.original == {"id": 8802, "name": "Remote Corr"}
        assert item.correspondent.proposed.get("name") == "Local Corr"
        assert item.correspondent.proposed.get("pending_name") == "Pending Corr"


def test_preview_for_doc_ids_uses_fallback_document_fetch(
    session_factory: Any, monkeypatch: MonkeyPatch
) -> None:
    from app.config import load_settings
    from app.services.integrations import paperless

    with session_factory() as db:
        db.add(Document(id=902, title="Doc 902"))
        db.commit()

        called = {"fallback": 0}
        monkeypatch.setattr(paperless, "get_documents_cached", lambda *_args, **_kwargs: {})

        def _fallback(*_args: object, **_kwargs: object) -> dict[str, object]:
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


def test_local_writeback_candidate_doc_ids_dedupes_sources(session_factory: Any) -> None:
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


def test_writeback_candidate_cache_invalidates(session_factory: Any) -> None:
    invalidate_writeback_preview_cache()
    with session_factory() as db:
        db.add(
            DocumentPendingTag(
                doc_id=906,
                names_json=json.dumps(["TagA"], ensure_ascii=False),
                updated_at="2026-02-20T10:00:00+00:00",
            )
        )
        db.commit()

        first = get_cached_writeback_candidate_doc_ids(
            build_candidates=lambda: local_writeback_candidate_doc_ids(db)
        )
        assert 906 in first

        db.query(DocumentPendingTag).filter(DocumentPendingTag.doc_id == 906).delete()
        db.commit()

        cached = get_cached_writeback_candidate_doc_ids(
            build_candidates=lambda: local_writeback_candidate_doc_ids(db)
        )
        assert 906 in cached

        invalidate_writeback_preview_cache()
        refreshed = get_cached_writeback_candidate_doc_ids(
            build_candidates=lambda: local_writeback_candidate_doc_ids(db)
        )
        assert 906 not in refreshed


def test_writeback_preview_cache_invalidates(session_factory: Any, monkeypatch: MonkeyPatch) -> None:
    from app.config import load_settings
    from app.services.integrations import paperless

    invalidate_writeback_preview_cache()
    with session_factory() as db:
        db.add(Document(id=907, title="Preview Cache Doc"))
        db.commit()

        monkeypatch.setattr(
            paperless,
            "get_documents_cached",
            lambda *_args, **_kwargs: {
                907: {
                    "id": 907,
                    "title": "Remote title",
                    "created": None,
                    "correspondent": None,
                    "tags": [],
                    "notes": [],
                }
            },
        )

        first = get_cached_writeback_preview(
            doc_ids=[907],
            build_preview=lambda: preview_for_doc_ids(load_settings(), db, [907]),
        )
        assert len(first) == 1
        assert first[0].changed is True

        local_doc = db.get(Document, 907)
        assert local_doc is not None
        local_doc.title = "Remote title"
        db.commit()

        cached = get_cached_writeback_preview(
            doc_ids=[907],
            build_preview=lambda: preview_for_doc_ids(load_settings(), db, [907]),
        )
        assert len(cached) == 1
        assert cached[0].changed is True

        invalidate_writeback_preview_cache()
        refreshed = get_cached_writeback_preview(
            doc_ids=[907],
            build_preview=lambda: preview_for_doc_ids(load_settings(), db, [907]),
        )
        assert len(refreshed) == 1
        assert refreshed[0].changed is False
