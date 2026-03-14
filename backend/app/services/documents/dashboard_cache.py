from __future__ import annotations

import time
from collections.abc import Callable
from threading import Lock

from sqlalchemy.orm import Session

DashboardBuilder = Callable[[Session], dict[str, object]]

_CACHE_LOCK = Lock()
_DASHBOARD_CACHE: dict[str, object] = {"ts": 0.0, "data": None}
_DASHBOARD_CACHE_TTL_SECONDS = 15


def invalidate_dashboard_cache() -> None:
    with _CACHE_LOCK:
        _DASHBOARD_CACHE["ts"] = 0.0
        _DASHBOARD_CACHE["data"] = None


def get_cached_dashboard_payload(db: Session, *, build_payload: DashboardBuilder) -> dict[str, object]:
    now = time.time()
    with _CACHE_LOCK:
        cached_ts_raw = _DASHBOARD_CACHE.get("ts")
        cached_ts = float(cached_ts_raw) if isinstance(cached_ts_raw, int | float) else 0.0
        cached_data = _DASHBOARD_CACHE.get("data")
        if isinstance(cached_data, dict) and (now - cached_ts) < _DASHBOARD_CACHE_TTL_SECONDS:
            return cached_data
    payload = build_payload(db)
    with _CACHE_LOCK:
        _DASHBOARD_CACHE["ts"] = now
        _DASHBOARD_CACHE["data"] = payload
    return payload
