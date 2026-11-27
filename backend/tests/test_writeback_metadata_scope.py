from __future__ import annotations

from typing import Any

from app.api_models import WritebackDryRunCall
from app.config import load_settings
from app.models import Document, Tag
from app.services.integrations import paperless
from app.services.writeback.writeback_apply import (
    execute_writeback_call,
    writeback_metadata_scope,
)


def _patch_call(doc_id: int) -> WritebackDryRunCall:
    return WritebackDryRunCall(
        doc_id=doc_id,
        method="PATCH",
        path=f"/api/documents/{doc_id}/",
        payload={
            "tags": [1],
            "pending_tag_names": ["Brand New"],
            "correspondent": None,
            "pending_correspondent_name": "Acme",
        },
    )


def _install_fakes(monkeypatch: Any) -> dict[str, int]:
    counts = {"list_tags": 0, "list_corr": 0, "update_tag": 0, "update_corr": 0, "create_tag": 0}
    created_tags: list[dict[str, Any]] = []
    created_corrs: list[dict[str, Any]] = []

    def list_tags(*_a: Any, **_k: Any) -> list[dict[str, Any]]:
        counts["list_tags"] += 1
        return [{"id": 1, "name": "Existing"}, *created_tags]

    def list_corr(*_a: Any, **_k: Any) -> list[dict[str, Any]]:
        counts["list_corr"] += 1
        return list(created_corrs)

    def create_tag(*_a: Any, **_k: Any) -> dict[str, Any]:
        counts["create_tag"] += 1
        created_tags.append({"id": 2, "name": "Brand New"})
        return created_tags[-1]

    def create_corr(*_a: Any, **_k: Any) -> dict[str, Any]:
        created_corrs.append({"id": 77, "name": "Acme"})
        return created_corrs[-1]

    def update_tag(*_a: Any, **_k: Any) -> dict[str, Any]:
        counts["update_tag"] += 1
        return {}

    def update_corr(*_a: Any, **_k: Any) -> dict[str, Any]:
        counts["update_corr"] += 1
        return {}

    monkeypatch.setattr(paperless, "list_all_tags", list_tags)
    monkeypatch.setattr(paperless, "list_all_correspondents", list_corr)
    monkeypatch.setattr(paperless, "create_tag", create_tag)
    monkeypatch.setattr(paperless, "create_correspondent", create_corr)
    monkeypatch.setattr(paperless, "update_tag", update_tag)
    monkeypatch.setattr(paperless, "update_correspondent", update_corr)
    monkeypatch.setattr(paperless, "update_document", lambda *_a, **_k: {})
    return counts


def _seed(session_factory: Any, doc_ids: list[int]) -> Any:
    db = session_factory()
    db.add(Tag(id=1, name="Existing"))
    for doc_id in doc_ids:
        db.add(Document(id=doc_id, title=f"Doc {doc_id}"))
    db.commit()
    return db


def test_batch_scope_fetches_and_unowns_once(session_factory: Any, monkeypatch: Any) -> None:
    counts = _install_fakes(monkeypatch)
    doc_ids = [1301, 1302, 1303]
    db = _seed(session_factory, doc_ids)
    settings = load_settings()
    try:
        with writeback_metadata_scope():
            for doc_id in doc_ids:
                execute_writeback_call(settings, db, _patch_call(doc_id))
        db.commit()
    finally:
        db.close()
    assert counts["list_tags"] == 1
    assert counts["list_corr"] == 1
    assert counts["create_tag"] == 1, "same new tag must be created once per batch"
    assert counts["update_tag"] == 2, "each tag is made shared once (Existing + Brand New)"
    assert counts["update_corr"] == 1, "created in doc 1, made shared once on first re-use"


def test_without_scope_every_call_reads_fresh_lists(session_factory: Any, monkeypatch: Any) -> None:
    counts = _install_fakes(monkeypatch)
    doc_ids = [1311, 1312]
    db = _seed(session_factory, doc_ids)
    settings = load_settings()
    try:
        for doc_id in doc_ids:
            execute_writeback_call(settings, db, _patch_call(doc_id))
        db.commit()
    finally:
        db.close()
    assert counts["list_tags"] == 2
    assert counts["list_corr"] == 2
