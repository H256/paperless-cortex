from __future__ import annotations

import time
from collections.abc import Callable
from threading import Lock

from app.api_models import WritebackDryRunItem

CandidateBuilder = Callable[[], list[int]]
PreviewBuilder = Callable[[], list[WritebackDryRunItem]]

_CACHE_TTL_SECONDS = 15
_CACHE_LOCK = Lock()
_WRITEBACK_PREVIEW_CACHE: dict[str, object] = {
    "candidate_ts": 0.0,
    "candidate_ids": None,
    "preview_ts": {},
    "preview_items": {},
}


def invalidate_writeback_preview_cache() -> None:
    with _CACHE_LOCK:
        _WRITEBACK_PREVIEW_CACHE["candidate_ts"] = 0.0
        _WRITEBACK_PREVIEW_CACHE["candidate_ids"] = None
        _WRITEBACK_PREVIEW_CACHE["preview_ts"] = {}
        _WRITEBACK_PREVIEW_CACHE["preview_items"] = {}


def get_cached_writeback_candidate_doc_ids(*, build_candidates: CandidateBuilder) -> list[int]:
    now = time.time()
    with _CACHE_LOCK:
        candidate_ts_raw = _WRITEBACK_PREVIEW_CACHE.get("candidate_ts")
        candidate_ts = (
            float(candidate_ts_raw) if isinstance(candidate_ts_raw, int | float) else 0.0
        )
        candidate_ids = _WRITEBACK_PREVIEW_CACHE.get("candidate_ids")
        if isinstance(candidate_ids, list) and (now - candidate_ts) < _CACHE_TTL_SECONDS:
            return list(candidate_ids)
    payload = build_candidates()
    with _CACHE_LOCK:
        _WRITEBACK_PREVIEW_CACHE["candidate_ts"] = now
        _WRITEBACK_PREVIEW_CACHE["candidate_ids"] = list(payload)
    return list(payload)


def get_cached_writeback_preview(
    *,
    doc_ids: list[int],
    build_preview: PreviewBuilder,
) -> list[WritebackDryRunItem]:
    cache_key = tuple(int(doc_id) for doc_id in doc_ids if int(doc_id) > 0)
    now = time.time()
    with _CACHE_LOCK:
        preview_ts_raw = _WRITEBACK_PREVIEW_CACHE.get("preview_ts")
        preview_items_raw = _WRITEBACK_PREVIEW_CACHE.get("preview_items")
        preview_ts = preview_ts_raw if isinstance(preview_ts_raw, dict) else {}
        preview_items = preview_items_raw if isinstance(preview_items_raw, dict) else {}
        cached_ts_raw = preview_ts.get(cache_key)
        cached_ts = float(cached_ts_raw) if isinstance(cached_ts_raw, int | float) else 0.0
        cached_items = preview_items.get(cache_key)
        if isinstance(cached_items, list) and (now - cached_ts) < _CACHE_TTL_SECONDS:
            return list(cached_items)
    payload = build_preview()
    with _CACHE_LOCK:
        preview_ts_raw = _WRITEBACK_PREVIEW_CACHE.get("preview_ts")
        preview_items_raw = _WRITEBACK_PREVIEW_CACHE.get("preview_items")
        preview_ts = preview_ts_raw if isinstance(preview_ts_raw, dict) else {}
        preview_items = preview_items_raw if isinstance(preview_items_raw, dict) else {}
        preview_ts[cache_key] = now
        preview_items[cache_key] = list(payload)
        _WRITEBACK_PREVIEW_CACHE["preview_ts"] = preview_ts
        _WRITEBACK_PREVIEW_CACHE["preview_items"] = preview_items
    return list(payload)
