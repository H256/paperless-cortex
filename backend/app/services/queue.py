from __future__ import annotations

import logging
import time
from typing import Iterable

from app.config import Settings

logger = logging.getLogger(__name__)

QUEUE_KEY = "paperless_intelligence:doc_queue"
QUEUE_SET = "paperless_intelligence:doc_queue_set"
TASK_TYPES = ['vision_ocr', 'suggestions', 'embeddings', 'sync']
STATS_TOTAL = "paperless_intelligence:queue_total"
STATS_IN_PROGRESS = "paperless_intelligence:queue_in_progress"
STATS_DONE = "paperless_intelligence:queue_done"
WORKER_HEARTBEAT_KEY = "paperless_intelligence:worker_heartbeat"
WORKER_HEARTBEAT_TTL = 30
CANCEL_KEY = "paperless_intelligence:queue_cancel"
CANCEL_TTL = 300


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
    client = _get_client(settings)
    if not client:
        return 0
    if is_cancel_requested(settings):
        return 0
    ids = [str(doc_id) for doc_id in doc_ids]
    if not ids:
        return 0
    # de-dupe via set
    added = []
    for doc_id in ids:
        if client.sadd(QUEUE_SET, doc_id):
            added.append(doc_id)
        # If task-specific items exist for this doc, remove them in favor of full.
        for task_type in TASK_TYPES:
            task_key = f"{doc_id}:{task_type}"
            if client.srem(QUEUE_SET, task_key):
                payload = __import__("json").dumps({"doc_id": int(doc_id), "task": task_type})
                client.lrem(QUEUE_KEY, 0, payload)
    if not added:
        return 0
    client.rpush(QUEUE_KEY, *added)
    client.incrby(STATS_TOTAL, len(added))
    logger.info("Enqueued docs count=%s", len(added))
    return len(added)


def _task_key(task: dict) -> str:
    doc_id = task.get("doc_id")
    task_type = task.get("task") or "full"
    return f"{doc_id}:{task_type}"


def enqueue_task(settings: Settings, task: dict) -> int:
    client = _get_client(settings)
    if not client:
        return 0
    if is_cancel_requested(settings):
        return 0
    payload = __import__("json").dumps(task)
    key = _task_key(task)
    doc_id = task.get("doc_id")
    if doc_id is not None and client.sismember(QUEUE_SET, str(doc_id)):
        return 0
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
    doc_id = task.get("doc_id")
    if doc_id is not None and client.sismember(QUEUE_SET, str(doc_id)):
        return 0
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
    added = 0
    # lpush in reverse so the first task runs first
    for task in reversed(tasks):
        added += enqueue_task_front(settings, task)
    return added


def enqueue_docs_front(settings: Settings, doc_ids: Iterable[int]) -> int:
    client = _get_client(settings)
    if not client:
        return 0
    if is_cancel_requested(settings):
        return 0
    ids = [str(doc_id) for doc_id in doc_ids]
    if not ids:
        return 0
    added_count = 0
    for doc_id in ids:
        is_new = client.sadd(QUEUE_SET, doc_id)
        if is_new:
            added_count += 1
            client.incr(STATS_TOTAL)
        # Move to front even if already queued.
        client.lrem(QUEUE_KEY, 0, doc_id)
        client.lpush(QUEUE_KEY, doc_id)
    logger.info("Prioritized docs count=%s", len(ids))
    return len(ids)


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


def peek_queue(settings: Settings, limit: int = 20) -> list[int]:
    client = _get_client(settings)
    if not client:
        return []
    raw = client.lrange(QUEUE_KEY, 0, max(0, limit - 1))
    return [int(x) for x in raw if str(x).isdigit()]


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
