from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from app.config import load_settings
from app.models import Document
from app.services.pipeline.process_missing import (
    ProcessMissingOptions,
    process_missing_documents,
)

if TYPE_CHECKING:
    from app.config import Settings


def _options(*, dry_run: bool, include_sync: bool, limit: int | None) -> ProcessMissingOptions:
    return ProcessMissingOptions(
        dry_run=dry_run,
        include_sync=include_sync,
        include_evidence_index=False,
        include_vision_ocr=False,
        include_embeddings=True,
        include_embeddings_paperless=True,
        include_embeddings_vision=False,
        include_doc_similarity_index=False,
        include_page_notes=False,
        include_summary_hierarchical=False,
        include_suggestions_paperless=False,
        include_suggestions_vision=False,
        embeddings_mode="paperless",
        limit=limit,
    )


def test_process_missing_documents_dry_run_syncs_limits_and_skips_deleted(
    session_factory: Any,
    monkeypatch: Any,
) -> None:
    from app.services.pipeline import process_missing as process_missing_module

    with session_factory() as db:
        db.add_all(
            [
                Document(
                    id=4101,
                    title="Needs Embeddings A",
                    content="alpha",
                    created="2026-03-11T10:00:00+00:00",
                    modified="2026-03-11T10:00:00+00:00",
                ),
                Document(
                    id=4102,
                    title="Needs Embeddings B",
                    content="beta",
                    created="2026-03-11T10:00:00+00:00",
                    modified="2026-03-11T10:00:00+00:00",
                ),
                Document(
                    id=4103,
                    title="Deleted in Paperless",
                    content="gamma",
                    deleted_at="DELETED in Paperless 2026-03-11T10:01:00+00:00",
                    created="2026-03-11T10:00:00+00:00",
                    modified="2026-03-11T10:00:00+00:00",
                ),
            ]
        )
        db.commit()

    sync_calls: list[dict[str, Any]] = []
    enqueue_calls: list[list[dict[str, Any]]] = []
    cache_calls: list[set[int]] = []

    def _run_sync_documents(**kwargs: Any) -> None:
        sync_calls.append(dict(kwargs))

    def _enqueue_task_sequence(_settings: Settings, tasks: list[dict[str, Any]]) -> int:
        enqueue_calls.append([dict(task) for task in tasks])
        return len(tasks)

    def _collect_pipeline_cache(_db: Any, *, doc_ids: set[int], settings: Settings) -> dict[str, Any]:
        cache_calls.append(set(doc_ids))
        return {"doc_ids": set(doc_ids), "settings_log_level": settings.log_level}

    def _evaluate_doc_pipeline(**kwargs: Any) -> dict[str, Any]:
        doc = cast("Document", kwargs["doc"])
        if int(doc.id) == 4101:
            return {
                "tasks": [{"doc_id": 4101, "task": "embeddings_paperless"}],
                "needs_vision": False,
                "needs_embeddings": True,
                "needs_embeddings_paperless": True,
                "needs_embeddings_vision": False,
                "needs_page_notes": False,
                "needs_summary_hierarchical": False,
                "needs_evidence_index": False,
                "needs_suggestions_paperless": False,
                "needs_suggestions_vision": False,
                "needs_doc_similarity_index": False,
            }
        if int(doc.id) == 4102:
            return {
                "tasks": [{"doc_id": 4102, "task": "embeddings_paperless"}],
                "needs_vision": False,
                "needs_embeddings": True,
                "needs_embeddings_paperless": True,
                "needs_embeddings_vision": False,
                "needs_page_notes": False,
                "needs_summary_hierarchical": False,
                "needs_evidence_index": False,
                "needs_suggestions_paperless": False,
                "needs_suggestions_vision": False,
                "needs_doc_similarity_index": False,
            }
        return {
            "tasks": [],
            "needs_vision": False,
            "needs_embeddings": False,
            "needs_embeddings_paperless": False,
            "needs_embeddings_vision": False,
            "needs_page_notes": False,
            "needs_summary_hierarchical": False,
            "needs_evidence_index": False,
            "needs_suggestions_paperless": False,
            "needs_suggestions_vision": False,
            "needs_doc_similarity_index": False,
        }

    monkeypatch.setattr(process_missing_module, "collect_pipeline_cache", _collect_pipeline_cache)
    monkeypatch.setattr(process_missing_module, "evaluate_doc_pipeline", _evaluate_doc_pipeline)

    settings = load_settings()
    with session_factory() as db:
        result = process_missing_documents(
            settings=settings,
            db=db,
            options=_options(dry_run=True, include_sync=True, limit=1),
            run_sync_documents=_run_sync_documents,
            enqueue_task_sequence=_enqueue_task_sequence,
        )

    assert len(sync_calls) == 1
    assert sync_calls[0]["insert_only"] is True
    assert sync_calls[0]["mark_missing"] is True
    assert cache_calls == [{4101, 4102, 4103}]
    assert result["docs"] == 2
    assert result["missing_docs"] == 2
    assert result["missing_embeddings"] == 2
    assert result["missing_embeddings_paperless"] == 2
    assert result["selected"] == 1
    assert result["enqueued"] == 0
    assert result["tasks"] == 0
    assert result["dry_run"] is True
    assert [preview["doc_id"] for preview in result["preview_docs"]] == [4101, 4102]
    assert all(preview["missing_steps"] == ["paperless"] for preview in result["preview_docs"])
    assert enqueue_calls == []


def test_process_missing_documents_enqueues_selected_tasks(session_factory: Any, monkeypatch: Any) -> None:
    from app.services.pipeline import process_missing as process_missing_module

    with session_factory() as db:
        db.add(
            Document(
                id=4201,
                title="Needs Work",
                content="delta",
                created="2026-03-11T10:00:00+00:00",
                modified="2026-03-11T10:00:00+00:00",
            )
        )
        db.commit()

    enqueued_payloads: list[list[dict[str, Any]]] = []

    def _enqueue_task_sequence(_settings: Settings, tasks: list[dict[str, Any]]) -> int:
        enqueued_payloads.append([dict(task) for task in tasks])
        return len(tasks)

    monkeypatch.setattr(
        process_missing_module,
        "collect_pipeline_cache",
        lambda _db, *, doc_ids, settings: {"doc_ids": set(doc_ids), "settings_log_level": settings.log_level},
    )
    monkeypatch.setattr(
        process_missing_module,
        "evaluate_doc_pipeline",
        lambda **kwargs: {
            "tasks": [
                {"doc_id": int(cast("Document", kwargs["doc"]).id), "task": "embeddings_paperless"},
                {"doc_id": int(cast("Document", kwargs["doc"]).id), "task": "suggestions_paperless"},
            ],
            "needs_vision": False,
            "needs_embeddings": True,
            "needs_embeddings_paperless": True,
            "needs_embeddings_vision": False,
            "needs_page_notes": False,
            "needs_summary_hierarchical": False,
            "needs_evidence_index": False,
            "needs_suggestions_paperless": True,
            "needs_suggestions_vision": False,
            "needs_doc_similarity_index": False,
        },
    )

    with session_factory() as db:
        result = process_missing_documents(
            settings=load_settings(),
            db=db,
            options=_options(dry_run=False, include_sync=False, limit=None),
            run_sync_documents=lambda **_kwargs: None,
            enqueue_task_sequence=_enqueue_task_sequence,
        )

    assert result["docs"] == 1
    assert result["missing_docs"] == 1
    assert result["missing_embeddings"] == 1
    assert result["missing_suggestions_paperless"] == 1
    assert result["selected"] == 1
    assert result["enqueued"] == 1
    assert result["tasks"] == 2
    assert enqueued_payloads == [
        [
            {"doc_id": 4201, "task": "embeddings_paperless"},
            {"doc_id": 4201, "task": "suggestions_paperless"},
        ]
    ]
