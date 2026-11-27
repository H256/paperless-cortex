from __future__ import annotations

import logging
from typing import Any

from app.config import load_settings
from app.services.pipeline import worker_dispatch
from app.services.pipeline.worker_dispatch import build_dispatch_handler
from app.services.pipeline.worker_runtime import (
    dispatch_worker_task,
    handle_worker_cancel_request,
    parse_worker_queue_item,
    run_worker_iteration_gate,
)


def test_parse_worker_queue_item_dict_payload() -> None:
    events: list[tuple[str, object]] = []

    parsed = parse_worker_queue_item(
        b'{"doc_id": 42, "task": "vision_ocr", "retry_count": 2}',
        log_fn=lambda _logger, _level, message, **kwargs: events.append((message, kwargs.get("payload"))),
        logger=logging.getLogger(__name__),
    )

    assert parsed == {
        "doc_id": 42,
        "task_type": "vision_ocr",
        "task_payload": {"doc_id": 42, "task": "vision_ocr", "retry_count": 2},
        "retry_attempt": 2,
    }
    assert events == []


def test_parse_worker_queue_item_plain_doc_id() -> None:
    parsed = parse_worker_queue_item(
        "99",
        log_fn=lambda *_args, **_kwargs: None,
        logger=logging.getLogger(__name__),
    )

    assert parsed == {
        "doc_id": 99,
        "task_type": "full",
        "task_payload": {"doc_id": 99, "task": "full"},
        "retry_attempt": 0,
    }


def test_parse_worker_queue_item_invalid_payload_logs_warning() -> None:
    events: list[tuple[str, object]] = []

    parsed = parse_worker_queue_item(
        b'{"doc_id": "bad", "task": "sync"}',
        log_fn=lambda _logger, _level, message, **kwargs: events.append((message, kwargs.get("payload"))),
        logger=logging.getLogger(__name__),
    )

    assert parsed is None
    assert events == [("Invalid task doc_id in queue payload", {"doc_id": "bad", "task": "sync"})]


def test_handle_worker_cancel_request_clears_runtime_state() -> None:
    calls: list[str] = []

    handled = handle_worker_cancel_request(
        object(),
        is_cancel_requested_fn=lambda _settings: True,
        clear_queue_fn=lambda _settings: calls.append("clear_queue"),
        reset_stats_fn=lambda _settings: calls.append("reset_stats"),
        clear_cancel_fn=lambda _settings: calls.append("clear_cancel"),
        log_fn=lambda _logger, _level, message, **_kwargs: calls.append(message),
        logger=logging.getLogger(__name__),
    )

    assert handled is True
    assert calls == [
        "Worker cancel requested; clearing queue",
        "clear_queue",
        "reset_stats",
        "clear_cancel",
    ]


def test_dispatch_worker_task_routes_vision_ocr_force_flag() -> None:
    calls: list[tuple[str, Any]] = []

    dispatch_worker_task(
        settings=load_settings(),
        db=object(),
        task_type="vision_ocr",
        doc_id=7,
        task={"force": True},
        run_id=11,
        build_handler_fn=lambda *_args: None,
        process_vision_ocr_force_fn=lambda _settings, _db, doc_id, force, run_id: calls.append(
            ("vision_ocr", {"doc_id": doc_id, "force": force, "run_id": run_id})
        ),
        process_full_doc_fn=lambda *_args: calls.append(("full", None)),
    )

    assert calls == [("vision_ocr", {"doc_id": 7, "force": True, "run_id": 11})]


def test_dispatch_worker_task_uses_handler_before_full_fallback() -> None:
    calls: list[str] = []

    dispatch_worker_task(
        settings=load_settings(),
        db=object(),
        task_type="sync",
        doc_id=5,
        task={"doc_id": 5, "task": "sync"},
        run_id=None,
        build_handler_fn=lambda *_args: lambda: calls.append("handler"),
        process_vision_ocr_force_fn=lambda *_args: calls.append("vision"),
        process_full_doc_fn=lambda *_args: calls.append("full"),
    )

    assert calls == ["handler"]


def test_build_dispatch_handler_routes_cleanup_texts_options(
    monkeypatch: Any,
) -> None:
    calls: list[dict[str, Any]] = []

    def _reclean_page_texts(
        _db: Any,
        _settings: Any,
        *,
        doc_id: int | None = None,
        source: str | None = None,
        clear_first: bool = False,
    ) -> None:
        calls.append({"doc_id": doc_id, "source": source, "clear_first": clear_first})

    monkeypatch.setattr(worker_dispatch, "reclean_page_texts", _reclean_page_texts)

    handler = build_dispatch_handler(
        settings=load_settings(),
        db=object(),
        task_type="cleanup_texts",
        doc_id=41,
        task={"source": "vision_ocr", "clear_first": True},
        run_id=9,
        is_cancel_requested_fn=lambda _s: False,
        get_tags_fn=lambda _s: [],
        get_correspondents_fn=lambda _s: [],
        get_document_fn=lambda _s, _i: {},
        generate_suggestions_fn=lambda *_a, **_k: {},
        persist_suggestions_fn=lambda *_a, **_k: None,
        generate_field_variants_fn=lambda *_a, **_k: {},
        upsert_suggestion_fn=lambda *_a, **_k: None,
        audit_suggestion_run_fn=lambda *_a, **_k: None,
    )

    assert handler is not None
    handler()
    assert calls == [{"doc_id": 41, "source": "vision_ocr", "clear_first": True}]


def test_build_dispatch_handler_routes_producer_task_types(
    monkeypatch: Any,
) -> None:
    """Producers enqueue page_notes_paperless/page_notes_vision/summary_hierarchical/
    embeddings_paperless; each must route to its dedicated handler (not the
    full-document fallback) with the correct source/mode."""
    calls: list[dict[str, Any]] = []

    def _page_notes(
        _settings: Any,
        _db: Any,
        doc_id: int,
        source: str,
        *,
        run_id: int | None = None,
        is_cancel_requested_fn: Any = None,
    ) -> None:
        calls.append({"fn": "page_notes", "doc_id": doc_id, "source": source})

    def _summary(
        _settings: Any,
        _db: Any,
        doc_id: int,
        source: str,
        *,
        run_id: int | None = None,
    ) -> None:
        calls.append({"fn": "summary", "doc_id": doc_id, "source": source})

    def _embeddings(
        _settings: Any,
        _db: Any,
        doc_id: int,
        *,
        is_cancel_requested_fn: Any = None,
        run_id: int | None = None,
        embeddings_mode: str | None = None,
    ) -> None:
        calls.append({"fn": "embeddings", "doc_id": doc_id, "mode": embeddings_mode})

    monkeypatch.setattr(worker_dispatch, "process_page_notes", _page_notes)
    monkeypatch.setattr(worker_dispatch, "process_summary_hierarchical", _summary)
    monkeypatch.setattr(worker_dispatch, "process_embeddings_paperless", _embeddings)

    def _build(task_type: str, task: dict[str, Any]) -> Any:
        return build_dispatch_handler(
            settings=load_settings(),
            db=object(),
            task_type=task_type,
            doc_id=41,
            task=task,
            run_id=9,
            is_cancel_requested_fn=lambda _s: False,
            get_tags_fn=lambda _s: [],
            get_correspondents_fn=lambda _s: [],
            get_document_fn=lambda _s, _i: {},
            generate_suggestions_fn=lambda *_a, **_k: {},
            persist_suggestions_fn=lambda *_a, **_k: None,
            generate_field_variants_fn=lambda *_a, **_k: {},
            upsert_suggestion_fn=lambda *_a, **_k: None,
            audit_suggestion_run_fn=lambda *_a, **_k: None,
        )

    cases = [
        (
            "page_notes_paperless",
            {},
            {"fn": "page_notes", "doc_id": 41, "source": "paperless_ocr"},
        ),
        (
            "page_notes_vision",
            {},
            {"fn": "page_notes", "doc_id": 41, "source": "vision_ocr"},
        ),
        (
            "summary_hierarchical",
            {"source": "vision_ocr"},
            {"fn": "summary", "doc_id": 41, "source": "vision_ocr"},
        ),
        (
            "summary_hierarchical",
            {},
            {"fn": "summary", "doc_id": 41, "source": "vision_ocr"},
        ),
        (
            "embeddings_paperless",
            {"embeddings_mode": "both"},
            {"fn": "embeddings", "doc_id": 41, "mode": "both"},
        ),
        (
            "embeddings_paperless",
            {},
            {"fn": "embeddings", "doc_id": 41, "mode": None},
        ),
    ]
    for task_type, task, expected in cases:
        handler = _build(task_type, task)
        assert handler is not None, f"missing dispatch handler for {task_type}"
        handler()
        assert calls[-1] == expected


def _gate_kwargs(
    calls: list[str],
    *,
    paused: bool,
    cancel: bool,
) -> dict[str, Any]:
    return {
        "is_paused_fn": lambda _settings: paused,
        "is_cancel_requested_fn": lambda _settings: cancel,
        "clear_queue_fn": lambda _settings: calls.append("clear_queue"),
        "reset_stats_fn": lambda _settings: calls.append("reset_stats"),
        "clear_cancel_fn": lambda _settings: calls.append("clear_cancel"),
        "log_fn": lambda _logger, _level, message, **_kwargs: calls.append(message),
        "logger": logging.getLogger(__name__),
    }


def test_iteration_gate_processes_cancel_while_paused() -> None:
    calls: list[str] = []

    handled = run_worker_iteration_gate(object(), **_gate_kwargs(calls, paused=True, cancel=True))

    assert handled is True
    assert calls == [
        "Worker cancel requested; clearing queue",
        "clear_queue",
        "reset_stats",
        "clear_cancel",
    ]


def test_iteration_gate_paused_without_cancel_sleeps_only() -> None:
    calls: list[str] = []

    handled = run_worker_iteration_gate(object(), **_gate_kwargs(calls, paused=True, cancel=False))

    assert handled is True
    assert calls == []


def test_iteration_gate_cancel_without_pause_is_processed() -> None:
    calls: list[str] = []

    handled = run_worker_iteration_gate(object(), **_gate_kwargs(calls, paused=False, cancel=True))

    assert handled is True
    assert calls == [
        "Worker cancel requested; clearing queue",
        "clear_queue",
        "reset_stats",
        "clear_cancel",
    ]


def test_iteration_gate_idle_proceeds() -> None:
    calls: list[str] = []

    handled = run_worker_iteration_gate(object(), **_gate_kwargs(calls, paused=False, cancel=False))

    assert handled is False
    assert calls == []
