from __future__ import annotations

import copy
import time
from collections.abc import Callable
from threading import Lock

DocumentsPageBuilder = Callable[[], dict[str, object]]
DocumentsPageKey = tuple[
    int,
    int,
    str | None,
    int | None,
    int | None,
    str | None,
    str | None,
    bool,
    bool,
    str,
]

_CACHE_TTL_SECONDS = 15
_CACHE_LOCK = Lock()
_DOCUMENTS_LIST_CACHE: dict[str, object] = {"entries": {}, "timestamps": {}}


def invalidate_documents_list_cache() -> None:
    with _CACHE_LOCK:
        _DOCUMENTS_LIST_CACHE["entries"] = {}
        _DOCUMENTS_LIST_CACHE["timestamps"] = {}


def get_cached_documents_page(
    *,
    cache_key: DocumentsPageKey,
    build_payload: DocumentsPageBuilder,
) -> dict[str, object]:
    now = time.time()
    with _CACHE_LOCK:
        entries_raw = _DOCUMENTS_LIST_CACHE.get("entries")
        timestamps_raw = _DOCUMENTS_LIST_CACHE.get("timestamps")
        entries = entries_raw if isinstance(entries_raw, dict) else {}
        timestamps = timestamps_raw if isinstance(timestamps_raw, dict) else {}
        cached_ts_raw = timestamps.get(cache_key)
        cached_ts = float(cached_ts_raw) if isinstance(cached_ts_raw, int | float) else 0.0
        cached_payload = entries.get(cache_key)
        if isinstance(cached_payload, dict) and (now - cached_ts) < _CACHE_TTL_SECONDS:
            return copy.deepcopy(cached_payload)
    payload = build_payload()
    with _CACHE_LOCK:
        entries_raw = _DOCUMENTS_LIST_CACHE.get("entries")
        timestamps_raw = _DOCUMENTS_LIST_CACHE.get("timestamps")
        entries = entries_raw if isinstance(entries_raw, dict) else {}
        timestamps = timestamps_raw if isinstance(timestamps_raw, dict) else {}
        entries[cache_key] = copy.deepcopy(payload)
        timestamps[cache_key] = now
        _DOCUMENTS_LIST_CACHE["entries"] = entries
        _DOCUMENTS_LIST_CACHE["timestamps"] = timestamps
    return copy.deepcopy(payload)
