from __future__ import annotations

import json
import logging
import time
from threading import Lock
from typing import Iterable

from app.config import Settings
from app.services.queue_tasks import build_task_sequence

logger = logging.getLogger(__name__)

QUEUE_KEY = "paperless_intelligence:doc_queue"
QUEUE_SET = "paperless_intelligence:doc_queue_set"
TASK_TYPES = [
    "sync",
    "evidence_index",
    "vision_ocr",
    "embeddings_paperless",
    "embeddings_vision",
    "similarity_index",
    "cleanup_texts",
    "page_notes_paperless",
    "page_notes_vision",
    "summary_hierarchical",
    "suggestions_paperless",
    "suggestions_vision",
    "suggest_field",
]
STATS_TOTAL = "paperless_intelligence:queue_total"
STATS_IN_PROGRESS = "paperless_intelligence:queue_in_progress"
STATS_DONE = "paperless_intelligence:queue_done"
LAST_RUN_SECONDS_KEY = "paperless_intelligence:queue_last_run_seconds"
LAST_RUN_AT_KEY = "paperless_intelligence:queue_last_run_at"
WORKER_HEARTBEAT_KEY = "paperless_intelligence:worker_heartbeat"
WORKER_HEARTBEAT_TTL = 30
WORKER_LOCK_KEY = "paperless_intelligence:worker_lock"
WORKER_LOCK_TTL = 300
RUNNING_TASK_KEY = "paperless_intelligence:queue_running_task"
CANCEL_KEY = "paperless_intelligence:queue_cancel"
CANCEL_TTL = 300
PAUSE_KEY = "paperless_intelligence:queue_paused"
PAUSE_TTL = 24 * 60 * 60
DELAYED_QUEUE_KEY = "paperless_intelligence:doc_queue_delayed"
DLQ_KEY = "paperless_intelligence:doc_queue_dlq"

_CLIENT_LOCK = Lock()
_CLIENT_BY_URL: dict[str, object] = {}


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
    url = _redis_url(settings.redis_host)
    with _CLIENT_LOCK:
        cached = _CLIENT_BY_URL.get(url)
        if cached is not None:
            return cached
        client = redis.Redis.from_url(
            url,
            decode_responses=True,
            health_check_interval=30,
            socket_keepalive=True,
            retry_on_timeout=True,
        )
        _CLIENT_BY_URL[url] = client
        return client


def enqueue_docs(settings: Settings, doc_ids: Iterable[int]) -> int:
    return enqueue_full_sequence(settings, doc_ids, include_sync=True)


def task_key(task: dict) -> str:
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


def _enqueue_task(settings: Settings, task: dict, *, front: bool) -> int:
    client = _get_client(settings)
    if not client:
        return 0
    if is_cancel_requested(settings):
        return 0
    payload = json.dumps(task)
    key = task_key(task)
    is_new = client.sadd(QUEUE_SET, key)
    if is_new:
        client.incr(STATS_TOTAL)
    if front:
        if is_new:
            client.lpush(QUEUE_KEY, payload)
            logger.info("Prioritized new task=%s", key)
            return 1
        removed = int(client.lrem(QUEUE_KEY, 0, payload) or 0)
        if removed > 0:
            client.lpush(QUEUE_KEY, payload)
            logger.info("Reprioritized queued task=%s", key)
            return 1
        # Task key exists in set but payload not in list -> likely currently running.
        logger.info("Skip reprioritize running task=%s", key)
        return 0
    if is_new:
        client.rpush(QUEUE_KEY, payload)
        logger.info("Enqueued task=%s", key)
        return 1
    return 0


def enqueue_task(settings: Settings, task: dict) -> int:
    return _enqueue_task(settings, task, front=False)


def enqueue_task_front(settings: Settings, task: dict) -> int:
    return _enqueue_task(settings, task, front=True)


def enqueue_task_delayed(settings: Settings, task: dict, delay_seconds: int) -> int:
    client = _get_client(settings)
    if not client:
        return 0
    if is_cancel_requested(settings):
        return 0
    payload = json.dumps(task)
    key = task_key(task)
    is_new = client.sadd(QUEUE_SET, key)
    due_at = time.time() + max(1, int(delay_seconds))
    if is_new:
        client.zadd(DELAYED_QUEUE_KEY, {payload: due_at})
        client.incr(STATS_TOTAL)
        logger.info("Enqueued delayed task=%s due_in=%ss", key, int(max(1, int(delay_seconds))))
        return 1
    return 0


def move_due_delayed_tasks(settings: Settings, limit: int = 100) -> int:
    client = _get_client(settings)
    if not client:
        return 0
    now = time.time()
    moved = 0
    candidates = client.zrangebyscore(DELAYED_QUEUE_KEY, 0, now, start=0, num=max(1, int(limit)))
    if not candidates:
        return 0
    for payload in candidates:
        removed = int(client.zrem(DELAYED_QUEUE_KEY, payload) or 0)
        if removed <= 0:
            continue
        client.rpush(QUEUE_KEY, payload)
        moved += 1
    return moved


def enqueue_task_sequence_front(settings: Settings, tasks: list[dict], force: bool = False) -> int:
    if not tasks:
        return 0
    # lpush in reverse so the first task runs first
    return _enqueue_tasks_bulk(settings, list(reversed(tasks)), front=True, force=force)


def enqueue_task_sequence(settings: Settings, tasks: list[dict]) -> int:
    if not tasks:
        return 0
    return _enqueue_tasks_bulk(settings, tasks, front=False, force=False)


def _enqueue_tasks_bulk(settings: Settings, tasks: list[dict], front: bool, force: bool) -> int:
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
        keys = [task_key(task) for task in batch]
        payloads = [json.dumps(task) for task in batch]
        if front and force:
            pipe = client.pipeline()
            for key in keys:
                pipe.sadd(QUEUE_SET, key)
            sadd_results = pipe.execute()
            added_batch = sum(1 for result in sadd_results if result)
            if added_batch:
                client.incrby(STATS_TOTAL, added_batch)
            for idx, (key, payload) in enumerate(zip(keys, payloads)):
                is_new = bool(sadd_results[idx])
                if is_new:
                    client.lpush(QUEUE_KEY, payload)
                    continue
                removed = int(client.lrem(QUEUE_KEY, 0, payload) or 0)
                if removed > 0:
                    client.lpush(QUEUE_KEY, payload)
                else:
                    logger.info("Skip reprioritize running task=%s", key)
            added += added_batch
            continue

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
        tasks = build_task_sequence(settings, doc_id, include_sync=include_sync)
        total += enqueue_task_sequence(settings, tasks)
    return total


def enqueue_docs_front(settings: Settings, doc_ids: Iterable[int]) -> int:
    return enqueue_full_sequence_front(settings, doc_ids, include_sync=True)


def enqueue_full_sequence_front(
    settings: Settings, doc_ids: Iterable[int], include_sync: bool = False
) -> int:
    total = 0
    for doc_id in doc_ids:
        tasks = build_task_sequence(settings, doc_id, include_sync=include_sync)
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
    if in_progress > 0 and length == 0:
        try:
            has_lock = bool(client.get(WORKER_LOCK_KEY))
            running_raw = client.get(RUNNING_TASK_KEY)
            running_started_at = None
            if running_raw:
                running_payload = json.loads(str(running_raw))
                if isinstance(running_payload, dict):
                    started_at_raw = running_payload.get("started_at")
                    if started_at_raw is not None:
                        running_started_at = int(started_at_raw)
            heartbeat_raw = client.get(WORKER_HEARTBEAT_KEY)
            heartbeat_at = int(heartbeat_raw) if heartbeat_raw is not None else None
            now = int(time.time())
            heartbeat_stale = heartbeat_at is None or (now - heartbeat_at) > (WORKER_HEARTBEAT_TTL * 2)
            running_old_enough = (
                running_started_at is None
                or (now - int(running_started_at)) > max(60, WORKER_HEARTBEAT_TTL * 2)
            )
            if (not has_lock) and heartbeat_stale and running_old_enough:
                client.set(STATS_IN_PROGRESS, 0)
                in_progress = 0
        except Exception:
            pass
    last_run_seconds_raw = client.get(LAST_RUN_SECONDS_KEY)
    last_run_at = client.get(LAST_RUN_AT_KEY)
    last_run_seconds = None
    if last_run_seconds_raw is not None:
        try:
            last_run_seconds = float(last_run_seconds_raw)
        except Exception:
            last_run_seconds = None
    return {
        "length": length,
        "total": total,
        "in_progress": in_progress,
        "done": done,
        "last_run_seconds": last_run_seconds,
        "last_run_at": last_run_at,
    }


def peek_queue(settings: Settings, limit: int = 20) -> list[dict]:
    client = _get_client(settings)
    if not client:
        return []
    raw = client.lrange(QUEUE_KEY, 0, max(0, limit - 1))
    items: list[dict] = []
    for entry in raw:
        try:
            payload = json.loads(entry)
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
    client.delete(DELAYED_QUEUE_KEY)


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
    current = int(client.get(STATS_IN_PROGRESS) or 0)
    next_value = max(0, current - 1)
    client.set(STATS_IN_PROGRESS, next_value)
    client.incr(STATS_DONE)


def record_last_run(settings: Settings, duration_seconds: float) -> None:
    client = _get_client(settings)
    if not client:
        return
    try:
        client.set(LAST_RUN_SECONDS_KEY, max(0.0, float(duration_seconds)))
        client.set(LAST_RUN_AT_KEY, int(time.time()))
    except Exception:
        return


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
    try:
        return bool(client.get(CANCEL_KEY))
    except Exception:
        logger.warning("Cancel check failed; treating as not-cancelled", exc_info=True)
        return False


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
    try:
        return bool(client.get(PAUSE_KEY))
    except Exception:
        logger.warning("Pause check failed; treating as not-paused", exc_info=True)
        return False


def _parse_queue_entry(entry: str) -> dict | None:
    try:
        payload = json.loads(entry)
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
        key = task_key(payload)
        client.srem(QUEUE_SET, key)
    return True


def mark_worker_heartbeat(settings: Settings) -> None:
    client = _get_client(settings)
    if not client:
        return
    now = int(time.time())
    client.set(WORKER_HEARTBEAT_KEY, now, ex=WORKER_HEARTBEAT_TTL)


def acquire_worker_lock(settings: Settings, token: str) -> bool:
    client = _get_client(settings)
    if not client:
        return False
    try:
        return bool(client.set(WORKER_LOCK_KEY, token, nx=True, ex=WORKER_LOCK_TTL))
    except Exception:
        return False


def refresh_worker_lock(settings: Settings, token: str) -> bool:
    client = _get_client(settings)
    if not client:
        return False
    try:
        current = client.get(WORKER_LOCK_KEY)
        if current != token:
            return False
        client.set(WORKER_LOCK_KEY, token, ex=WORKER_LOCK_TTL)
        return True
    except Exception:
        return False


def release_worker_lock(settings: Settings, token: str) -> None:
    client = _get_client(settings)
    if not client:
        return
    try:
        current = client.get(WORKER_LOCK_KEY)
        if current == token:
            client.delete(WORKER_LOCK_KEY)
    except Exception:
        return


def worker_lock_status(settings: Settings) -> dict[str, object]:
    client = _get_client(settings)
    if not client:
        return {"has_lock": False, "owner": None, "ttl_seconds": None}
    try:
        owner = client.get(WORKER_LOCK_KEY)
        ttl_raw = client.ttl(WORKER_LOCK_KEY)
    except Exception:
        return {"has_lock": False, "owner": None, "ttl_seconds": None}
    ttl_seconds: int | None
    if ttl_raw is None or int(ttl_raw) < 0:
        ttl_seconds = None
    else:
        ttl_seconds = int(ttl_raw)
    return {
        "has_lock": bool(owner),
        "owner": owner,
        "ttl_seconds": ttl_seconds,
    }


def set_running_task(settings: Settings, task: dict) -> None:
    client = _get_client(settings)
    if not client:
        return
    try:
        payload = {
            "task": task,
            "started_at": int(time.time()),
        }
        client.set(RUNNING_TASK_KEY, json.dumps(payload))
    except Exception:
        return


def clear_running_task(settings: Settings) -> None:
    client = _get_client(settings)
    if not client:
        return
    try:
        client.delete(RUNNING_TASK_KEY)
    except Exception:
        return


def get_running_task(settings: Settings) -> dict[str, object]:
    client = _get_client(settings)
    if not client:
        return {"task": None, "started_at": None}
    try:
        raw = client.get(RUNNING_TASK_KEY)
    except Exception:
        return {"task": None, "started_at": None}
    if not raw:
        return {"task": None, "started_at": None}
    try:
        payload = json.loads(raw)
    except Exception:
        return {"task": None, "started_at": None}
    if not isinstance(payload, dict):
        return {"task": None, "started_at": None}
    task = payload.get("task")
    started_at = payload.get("started_at")
    if not isinstance(task, dict):
        task = None
    if started_at is not None:
        try:
            started_at = int(started_at)
        except Exception:
            started_at = None
    # Self-heal stale "running" marker after crash/interrupt:
    # if lock is gone and heartbeat is stale, clear marker.
    try:
        has_lock = bool(client.get(WORKER_LOCK_KEY))
        heartbeat_raw = client.get(WORKER_HEARTBEAT_KEY)
        heartbeat_at = int(heartbeat_raw) if heartbeat_raw is not None else None
        now = int(time.time())
        heartbeat_stale = heartbeat_at is None or (now - heartbeat_at) > (WORKER_HEARTBEAT_TTL * 2)
        running_old_enough = started_at is None or (now - int(started_at)) > max(60, WORKER_HEARTBEAT_TTL * 2)
        if (not has_lock) and heartbeat_stale and running_old_enough:
            client.delete(RUNNING_TASK_KEY)
            return {"task": None, "started_at": None}
    except Exception:
        pass
    return {"task": task, "started_at": started_at}


def add_dead_letter(
    settings: Settings,
    *,
    task: dict,
    error_type: str,
    error_message: str,
    attempt: int,
) -> None:
    client = _get_client(settings)
    if not client:
        return
    payload = {
        "task": task,
        "error_type": error_type,
        "error_message": error_message,
        "attempt": int(attempt),
        "created_at": int(time.time()),
    }
    client.lpush(DLQ_KEY, json.dumps(payload))


def peek_dead_letters(settings: Settings, limit: int = 100) -> list[dict]:
    client = _get_client(settings)
    if not client:
        return []
    raw_items = client.lrange(DLQ_KEY, 0, max(0, int(limit) - 1))
    items: list[dict] = []
    for raw in raw_items:
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"raw": raw}
        if isinstance(payload, dict):
            items.append(payload)
    return items


def peek_delayed_queue(settings: Settings, limit: int = 50) -> list[dict]:
    client = _get_client(settings)
    if not client:
        return []
    now = time.time()
    raw = client.zrange(DELAYED_QUEUE_KEY, 0, max(0, limit - 1), withscores=True)
    items: list[dict] = []
    for entry, score in raw:
        task_payload: dict | None = None
        try:
            parsed = json.loads(entry)
            if isinstance(parsed, dict):
                task_payload = parsed
        except Exception:
            task_payload = None
        due_at = int(score)
        due_in = max(0, int(round(score - now)))
        items.append(
            {
                "task": task_payload,
                "raw": None if task_payload is not None else str(entry),
                "due_at": due_at,
                "due_in_seconds": due_in,
            }
        )
    return items


def clear_dead_letters(settings: Settings) -> None:
    client = _get_client(settings)
    if not client:
        return
    client.delete(DLQ_KEY)


def requeue_dead_letter_item(settings: Settings, index: int) -> bool:
    client = _get_client(settings)
    if not client:
        return False
    items = client.lrange(DLQ_KEY, 0, -1)
    if not items or index < 0 or index >= len(items):
        return False
    entry = items.pop(index)
    client.delete(DLQ_KEY)
    if items:
        client.rpush(DLQ_KEY, *items)
    try:
        parsed = json.loads(entry)
    except Exception:
        return False
    if not isinstance(parsed, dict):
        return False
    task = parsed.get("task")
    if not isinstance(task, dict):
        return False
    task["retry_count"] = 0
    return enqueue_task(settings, task) > 0


def reset_worker_lock(settings: Settings, force: bool = False) -> dict[str, object]:
    client = _get_client(settings)
    if not client:
        return {"had_lock": False, "reset": False, "reason": "redis_unavailable"}
    try:
        had_lock = bool(client.exists(WORKER_LOCK_KEY))
        if not force:
            raw_heartbeat = client.get(WORKER_HEARTBEAT_KEY)
            if raw_heartbeat:
                try:
                    heartbeat_at = int(raw_heartbeat)
                    age = max(0, int(time.time()) - heartbeat_at)
                    if age <= WORKER_HEARTBEAT_TTL:
                        return {
                            "had_lock": had_lock,
                            "reset": False,
                            "reason": "worker_active",
                        }
                except Exception:
                    pass
        deleted = int(client.delete(WORKER_LOCK_KEY))
        return {
            "had_lock": had_lock,
            "reset": deleted > 0,
            "reason": "ok" if deleted > 0 else "not_found",
        }
    except Exception:
        return {"had_lock": False, "reset": False, "reason": "error"}


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
