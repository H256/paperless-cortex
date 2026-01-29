from __future__ import annotations

import logging
from typing import Iterable

from app.config import Settings

logger = logging.getLogger(__name__)

QUEUE_KEY = "paperless_intelligence:doc_queue"
STATS_TOTAL = "paperless_intelligence:queue_total"
STATS_IN_PROGRESS = "paperless_intelligence:queue_in_progress"
STATS_DONE = "paperless_intelligence:queue_done"


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
    ids = [str(doc_id) for doc_id in doc_ids]
    if not ids:
        return 0
    client.rpush(QUEUE_KEY, *ids)
    client.incrby(STATS_TOTAL, len(ids))
    logger.info("Enqueued docs count=%s", len(ids))
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
