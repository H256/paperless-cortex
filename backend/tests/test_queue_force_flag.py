from __future__ import annotations

from typing import Any

from app.services.pipeline.queue_tasks import build_task_sequence
from app.services.pipeline.worker_dispatch import build_dispatch_handler


def _vision_settings() -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(enable_vision_ocr=True)


def _find_task(tasks: list[dict[str, Any]], task_name: str) -> dict[str, Any]:
    for task in tasks:
        if task.get("task") == task_name:
            return task
    raise AssertionError(f"task {task_name} not found in {tasks}")


def test_build_task_sequence_carries_force_on_embeddings_vision() -> None:
    tasks = build_task_sequence(_vision_settings(), 101, force=True)
    assert _find_task(tasks, "vision_ocr").get("force") is True
    assert _find_task(tasks, "embeddings_vision").get("force") is True


def test_build_task_sequence_default_force_is_false() -> None:
    tasks = build_task_sequence(_vision_settings(), 102)
    assert _find_task(tasks, "embeddings_vision").get("force") is False


def test_dispatch_embeddings_vision_passes_force_to_handler() -> None:
    calls: list[dict[str, Any]] = []

    def _process_embeddings_vision_fn(
        _settings: Any, _db: Any, doc_id: int, run_id: int | None = None, force: bool = False
    ) -> None:
        calls.append({"doc_id": doc_id, "run_id": run_id, "force": force})

    handler = build_dispatch_handler(
        settings=object(),
        db=object(),
        task_type="embeddings_vision",
        doc_id=103,
        task={"doc_id": 103, "task": "embeddings_vision", "force": True},
        run_id=7,
        process_sync_only_fn=lambda *_args: None,
        process_evidence_index_fn=lambda *_args, **_kwargs: None,
        process_embeddings_paperless_fn=lambda *_args, **_kwargs: None,
        process_embeddings_vision_fn=_process_embeddings_vision_fn,
        process_similarity_index_fn=lambda *_args: None,
        process_cleanup_texts_fn=lambda *_args, **_kwargs: None,
        process_page_notes_fn=lambda *_args, **_kwargs: None,
        process_summary_hierarchical_fn=lambda *_args, **_kwargs: None,
        process_suggestions_paperless_fn=lambda *_args: None,
        process_suggestions_vision_fn=lambda *_args: None,
        process_suggest_field_fn=lambda *_args: None,
    )
    assert handler is not None
    handler()
    assert calls == [{"doc_id": 103, "run_id": 7, "force": True}]


def test_dispatch_embeddings_vision_defaults_force_to_false() -> None:
    calls: list[dict[str, Any]] = []

    def _process_embeddings_vision_fn(
        _settings: Any, _db: Any, doc_id: int, run_id: int | None = None, force: bool = False
    ) -> None:
        calls.append({"doc_id": doc_id, "force": force})

    handler = build_dispatch_handler(
        settings=object(),
        db=object(),
        task_type="embeddings_vision",
        doc_id=104,
        task={"doc_id": 104, "task": "embeddings_vision"},
        run_id=None,
        process_sync_only_fn=lambda *_args: None,
        process_evidence_index_fn=lambda *_args, **_kwargs: None,
        process_embeddings_paperless_fn=lambda *_args, **_kwargs: None,
        process_embeddings_vision_fn=_process_embeddings_vision_fn,
        process_similarity_index_fn=lambda *_args: None,
        process_cleanup_texts_fn=lambda *_args, **_kwargs: None,
        process_page_notes_fn=lambda *_args, **_kwargs: None,
        process_summary_hierarchical_fn=lambda *_args, **_kwargs: None,
        process_suggestions_paperless_fn=lambda *_args: None,
        process_suggestions_vision_fn=lambda *_args: None,
        process_suggest_field_fn=lambda *_args: None,
    )
    assert handler is not None
    handler()
    assert calls == [{"doc_id": 104, "force": False}]
