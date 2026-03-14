from __future__ import annotations

import time
from collections.abc import Callable
from threading import Lock

from sqlalchemy.orm import Session

StatsBuilder = Callable[[Session], dict[str, int]]

_CACHE_LOCK = Lock()
_DOCUMENT_STATS_CACHE: dict[str, object] = {"ts": 0.0, "data": None}
_DOCUMENT_STATS_CACHE_TTL_SECONDS = 15


def invalidate_document_stats_cache() -> None:
    with _CACHE_LOCK:
        _DOCUMENT_STATS_CACHE["ts"] = 0.0
        _DOCUMENT_STATS_CACHE["data"] = None


def get_cached_document_stats(
    db: Session,
    *,
    build_payload: StatsBuilder,
) -> dict[str, int]:
    now = time.time()
    with _CACHE_LOCK:
        cached_ts_raw = _DOCUMENT_STATS_CACHE.get("ts")
        cached_ts = float(cached_ts_raw) if isinstance(cached_ts_raw, int | float) else 0.0
        cached_data = _DOCUMENT_STATS_CACHE.get("data")
        if isinstance(cached_data, dict) and (now - cached_ts) < _DOCUMENT_STATS_CACHE_TTL_SECONDS:
            return cached_data
    payload = build_payload(db)
    with _CACHE_LOCK:
        _DOCUMENT_STATS_CACHE["ts"] = now
        _DOCUMENT_STATS_CACHE["data"] = payload
    return payload
