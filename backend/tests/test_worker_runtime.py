from __future__ import annotations

import logging
from typing import Any

from app.services.pipeline.worker_dispatch import build_dispatch_handler
from app.services.pipeline.worker_runtime import (
    dispatch_worker_task,
    handle_worker_cancel_request,
    parse_worker_queue_item,
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
        settings=object(),
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
        settings=object(),
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


def test_build_dispatch_handler_routes_cleanup_texts_options() -> None:
    calls: list[dict[str, Any]] = []

    handler = build_dispatch_handler(
        settings=object(),
        db=object(),
        task_type="cleanup_texts",
        doc_id=41,
        task={"source": "vision_ocr", "clear_first": True},
        run_id=9,
        process_sync_only_fn=lambda *_args: None,
        process_evidence_index_fn=lambda *_args, **_kwargs: None,
        process_embeddings_paperless_fn=lambda *_args, **_kwargs: None,
        process_embeddings_vision_fn=lambda *_args, **_kwargs: None,
        process_similarity_index_fn=lambda *_args: None,
        process_cleanup_texts_fn=lambda _settings, _db, doc_id, **kwargs: calls.append(
            {"doc_id": doc_id, **kwargs}
        ),
        process_page_notes_fn=lambda *_args, **_kwargs: None,
        process_summary_hierarchical_fn=lambda *_args, **_kwargs: None,
        process_suggestions_paperless_fn=lambda *_args: None,
        process_suggestions_vision_fn=lambda *_args: None,
        process_suggest_field_fn=lambda *_args: None,
    )

    assert handler is not None
    handler()
    assert calls == [{"doc_id": 41, "source": "vision_ocr", "clear_first": True}]
