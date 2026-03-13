from __future__ import annotations

import copy
import threading
import time
from collections.abc import Callable

LocalDocumentBuilder = Callable[[], dict[str, object]]

_CACHE_TTL_SECONDS = 30
_CACHE_LOCK = threading.Lock()
_CACHE: dict[int, dict[str, object]] = {}
_CACHE_TS: dict[int, float] = {}


def invalidate_local_document_cache(doc_id: int | None = None) -> None:
    with _CACHE_LOCK:
        if doc_id is None:
            _CACHE.clear()
            _CACHE_TS.clear()
            return
        _CACHE.pop(int(doc_id), None)
        _CACHE_TS.pop(int(doc_id), None)


def get_cached_local_document_payload(
    *,
    doc_id: int,
    build_payload: LocalDocumentBuilder,
) -> dict[str, object]:
    now = time.time()
    cache_key = int(doc_id)
    with _CACHE_LOCK:
        cached_ts = float(_CACHE_TS.get(cache_key) or 0.0)
        cached_payload = _CACHE.get(cache_key)
        if isinstance(cached_payload, dict) and (now - cached_ts) < _CACHE_TTL_SECONDS:
            return copy.deepcopy(cached_payload)

    payload = build_payload()

    with _CACHE_LOCK:
        _CACHE[cache_key] = copy.deepcopy(payload)
        _CACHE_TS[cache_key] = now
    return payload
