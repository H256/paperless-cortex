from __future__ import annotations


def build_enqueue_document_task_payload(
    *,
    doc_id: int,
    task: str,
    source: str | None,
    force: bool,
    clear_first: bool,
    allowed_tasks: set[str],
) -> dict[str, object]:
    if task not in allowed_tasks:
        raise ValueError("Invalid task")
    payload: dict[str, object] = {"doc_id": doc_id, "task": task}
    if source:
        payload["source"] = source
    if force:
        payload["force"] = True
    if clear_first:
        payload["clear_first"] = True
    return payload


def build_enqueue_document_task_disabled_payload(*, doc_id: int, task: str) -> dict[str, object]:
    return {"enabled": False, "enqueued": 0, "task": task, "doc_id": doc_id}


def build_enqueue_document_task_response(
    *,
    doc_id: int,
    task: str,
    enqueued: int,
) -> dict[str, object]:
    return {"enabled": True, "enqueued": enqueued, "task": task, "doc_id": doc_id}
