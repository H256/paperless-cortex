from __future__ import annotations

import logging
import time
from typing import Iterable

from app.config import Settings

logger = logging.getLogger(__name__)

QUEUE_KEY = "paperless_intelligence:doc_queue"
QUEUE_SET = "paperless_intelligence:doc_queue_set"
TASK_TYPES = [
    "sync",
    "vision_ocr",
    "embeddings_paperless",
    "embeddings_vision",
    "suggestions_paperless",
    "suggestions_vision",
    "suggest_field",
]
STATS_TOTAL = "paperless_intelligence:queue_total"
STATS_IN_PROGRESS = "paperless_intelligence:queue_in_progress"
STATS_DONE = "paperless_intelligence:queue_done"
WORKER_HEARTBEAT_KEY = "paperless_intelligence:worker_heartbeat"
WORKER_HEARTBEAT_TTL = 30
CANCEL_KEY = "paperless_intelligence:queue_cancel"
CANCEL_TTL = 300
PAUSE_KEY = "paperless_intelligence:queue_paused"
PAUSE_TTL = 24 * 60 * 60


def _redis_url(host: str) -> str:
    if host.startswith("redis://") or host.startswith("rediss://"):
        return host
    return f"redis://{host}"


def _get_client(settings: Settings):
    if not settings.redis_host:
        return None
    try:
        import redis
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("redis package not installed") from exc
    return redis.Redis.from_url(_redis_url(settings.redis_host), decode_responses=True)


def enqueue_docs(settings: Settings, doc_ids: Iterable[int]) -> int:
    return enqueue_full_sequence(settings, doc_ids, include_sync=True)


def _task_key(task: dict) -> str:
    doc_id = task.get("doc_id")
    task_type = task.get("task") or "full"
    source = task.get("source")
    field = task.get("field")
    suffix = ""
    if source:
        suffix += f":{source}"
    if field:
        suffix += f":{field}"
    return f"{doc_id}:{task_type}{suffix}"


def enqueue_task(settings: Settings, task: dict) -> int:
    client = _get_client(settings)
    if not client:
        return 0
    if is_cancel_requested(settings):
        return 0
    payload = __import__("json").dumps(task)
    key = _task_key(task)
    if client.sadd(QUEUE_SET, key):
        client.rpush(QUEUE_KEY, payload)
        client.incr(STATS_TOTAL)
        logger.info("Enqueued task=%s", key)
        return 1
    return 0


def enqueue_task_front(settings: Settings, task: dict) -> int:
    client = _get_client(settings)
    if not client:
        return 0
    if is_cancel_requested(settings):
        return 0
    payload = __import__("json").dumps(task)
    key = _task_key(task)
    is_new = client.sadd(QUEUE_SET, key)
    if is_new:
        client.incr(STATS_TOTAL)
    client.lrem(QUEUE_KEY, 0, payload)
    client.lpush(QUEUE_KEY, payload)
    logger.info("Prioritized task=%s", key)
    return 1


def enqueue_task_sequence_front(settings: Settings, tasks: list[dict]) -> int:
    if not tasks:
        return 0
    # lpush in reverse so the first task runs first
    return _enqueue_tasks_bulk(settings, list(reversed(tasks)), front=True)


def enqueue_task_sequence(settings: Settings, tasks: list[dict]) -> int:
    if not tasks:
        return 0
    return _enqueue_tasks_bulk(settings, tasks, front=False)


def _enqueue_tasks_bulk(settings: Settings, tasks: list[dict], front: bool) -> int:
    client = _get_client(settings)
    if not client:
        return 0
    if is_cancel_requested(settings):
        return 0
    if not tasks:
        return 0
    batch_size = 500
    added = 0
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i : i + batch_size]
        keys = [_task_key(task) for task in batch]
        payloads = [__import__("json").dumps(task) for task in batch]
        pipe = client.pipeline()
        for key in keys:
            pipe.sadd(QUEUE_SET, key)
        results = pipe.execute()
        to_add = [payloads[idx] for idx, res in enumerate(results) if res]
        if not to_add:
            continue
        pipe = client.pipeline()
        for payload in to_add:
            if front:
                pipe.lrem(QUEUE_KEY, 0, payload)
                pipe.lpush(QUEUE_KEY, payload)
            else:
                pipe.rpush(QUEUE_KEY, payload)
            pipe.incr(STATS_TOTAL)
        pipe.execute()
        added += len(to_add)
    if added:
        logger.info("Enqueued tasks=%s front=%s", added, front)
    return added


def enqueue_full_sequence(
    settings: Settings, doc_ids: Iterable[int], include_sync: bool = False
) -> int:
    total = 0
    for doc_id in doc_ids:
        tasks: list[dict] = []
        if include_sync:
            tasks.append({"doc_id": int(doc_id), "task": "sync"})
        if settings.enable_vision_ocr:
            tasks.append({"doc_id": int(doc_id), "task": "vision_ocr"})
            tasks.append({"doc_id": int(doc_id), "task": "embeddings_vision"})
        else:
            tasks.append({"doc_id": int(doc_id), "task": "embeddings_paperless"})
        tasks.append({"doc_id": int(doc_id), "task": "suggestions_paperless"})
        if settings.enable_vision_ocr:
            tasks.append({"doc_id": int(doc_id), "task": "suggestions_vision"})
        total += enqueue_task_sequence(settings, tasks)
    return total


def enqueue_docs_front(settings: Settings, doc_ids: Iterable[int]) -> int:
    return enqueue_full_sequence_front(settings, doc_ids, include_sync=True)


def enqueue_full_sequence_front(
    settings: Settings, doc_ids: Iterable[int], include_sync: bool = False
) -> int:
    total = 0
    for doc_id in doc_ids:
        tasks: list[dict] = []
        if include_sync:
            tasks.append({"doc_id": int(doc_id), "task": "sync"})
        if settings.enable_vision_ocr:
            tasks.append({"doc_id": int(doc_id), "task": "vision_ocr"})
            tasks.append({"doc_id": int(doc_id), "task": "embeddings_vision"})
        else:
            tasks.append({"doc_id": int(doc_id), "task": "embeddings_paperless"})
        tasks.append({"doc_id": int(doc_id), "task": "suggestions_paperless"})
        if settings.enable_vision_ocr:
            tasks.append({"doc_id": int(doc_id), "task": "suggestions_vision"})
        total += enqueue_task_sequence_front(settings, tasks)
    return total


def queue_length(settings: Settings) -> int | None:
    client = _get_client(settings)
    if not client:
        return None
    return int(client.llen(QUEUE_KEY))


def queue_stats(settings: Settings) -> dict[str, int] | None:
    client = _get_client(settings)
    if not client:
        return None
    total = int(client.get(STATS_TOTAL) or 0)
    in_progress = int(client.get(STATS_IN_PROGRESS) or 0)
    done = int(client.get(STATS_DONE) or 0)
    length = int(client.llen(QUEUE_KEY))
    return {
        "length": length,
        "total": total,
        "in_progress": in_progress,
        "done": done,
    }


def peek_queue(settings: Settings, limit: int = 20) -> list[dict]:
    client = _get_client(settings)
    if not client:
        return []
    raw = client.lrange(QUEUE_KEY, 0, max(0, limit - 1))
    items: list[dict] = []
    for entry in raw:
        try:
            payload = __import__("json").loads(entry)
            if isinstance(payload, dict):
                items.append(payload)
                continue
        except Exception:
            pass
        if str(entry).isdigit():
            items.append({"doc_id": int(entry), "task": "full"})
        else:
            items.append({"raw": entry})
    return items


def clear_queue(settings: Settings) -> None:
    client = _get_client(settings)
    if not client:
        return
    client.delete(QUEUE_KEY)
    client.delete(QUEUE_SET)


def reset_stats(settings: Settings) -> None:
    client = _get_client(settings)
    if not client:
        return
    client.set(STATS_TOTAL, 0)
    client.set(STATS_IN_PROGRESS, 0)
    client.set(STATS_DONE, 0)


def mark_in_progress(settings: Settings) -> None:
    client = _get_client(settings)
    if not client:
        return
    client.incr(STATS_IN_PROGRESS)


def mark_done(settings: Settings) -> None:
    client = _get_client(settings)
    if not client:
        return
    client.decr(STATS_IN_PROGRESS)
    client.incr(STATS_DONE)


def request_cancel(settings: Settings) -> None:
    client = _get_client(settings)
    if not client:
        return
    client.set(CANCEL_KEY, "1", ex=CANCEL_TTL)


def clear_cancel(settings: Settings) -> None:
    client = _get_client(settings)
    if not client:
        return
    client.delete(CANCEL_KEY)


def cancel_queue(settings: Settings) -> None:
    request_cancel(settings)
    clear_queue(settings)
    reset_stats(settings)


def is_cancel_requested(settings: Settings) -> bool:
    client = _get_client(settings)
    if not client:
        return False
    return bool(client.get(CANCEL_KEY))


def pause_queue(settings: Settings) -> None:
    client = _get_client(settings)
    if not client:
        return
    client.set(PAUSE_KEY, "1", ex=PAUSE_TTL)


def resume_queue(settings: Settings) -> None:
    client = _get_client(settings)
    if not client:
        return
    client.delete(PAUSE_KEY)


def is_paused(settings: Settings) -> bool:
    client = _get_client(settings)
    if not client:
        return False
    return bool(client.get(PAUSE_KEY))


def _parse_queue_entry(entry: str) -> dict | None:
    try:
        payload = __import__("json").loads(entry)
        if isinstance(payload, dict):
            return payload
    except Exception:
        payload = None
    if str(entry).isdigit():
        return {"doc_id": int(entry), "task": "full"}
    return None


def reorder_queue(settings: Settings, from_index: int, to_index: int) -> bool:
    client = _get_client(settings)
    if not client:
        return False
    items = client.lrange(QUEUE_KEY, 0, -1)
    if not items:
        return False
    if from_index < 0 or from_index >= len(items):
        return False
    entry = items.pop(from_index)
    if to_index < 0:
        to_index = 0
    if to_index > len(items):
        to_index = len(items)
    items.insert(to_index, entry)
    client.delete(QUEUE_KEY)
    if items:
        client.rpush(QUEUE_KEY, *items)
    return True


def move_queue_item_to_top(settings: Settings, index: int) -> bool:
    return reorder_queue(settings, index, 0)


def move_queue_item_to_bottom(settings: Settings, index: int) -> bool:
    client = _get_client(settings)
    if not client:
        return False
    items = client.lrange(QUEUE_KEY, 0, -1)
    if not items or index < 0 or index >= len(items):
        return False
    return reorder_queue(settings, index, len(items) - 1)


def remove_queue_item(settings: Settings, index: int) -> bool:
    client = _get_client(settings)
    if not client:
        return False
    items = client.lrange(QUEUE_KEY, 0, -1)
    if not items or index < 0 or index >= len(items):
        return False
    entry = items.pop(index)
    client.delete(QUEUE_KEY)
    if items:
        client.rpush(QUEUE_KEY, *items)
    payload = _parse_queue_entry(entry)
    if payload:
        key = _task_key(payload)
        client.srem(QUEUE_SET, key)
    return True


def mark_worker_heartbeat(settings: Settings) -> None:
    client = _get_client(settings)
    if not client:
        return
    now = int(time.time())
    client.set(WORKER_HEARTBEAT_KEY, now, ex=WORKER_HEARTBEAT_TTL)


def worker_status(settings: Settings) -> tuple[bool, str]:
    client = _get_client(settings)
    if not client:
        return False, "Redis not configured"
    raw = client.get(WORKER_HEARTBEAT_KEY)
    if not raw:
        return False, "No heartbeat"
    try:
        last = int(raw)
    except Exception:
        return False, "Invalid heartbeat"
    age = max(0, int(time.time()) - last)
    if age > WORKER_HEARTBEAT_TTL:
        return False, f"Heartbeat stale ({age}s)"
    return True, f"Heartbeat {age}s ago"
