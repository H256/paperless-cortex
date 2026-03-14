from __future__ import annotations

from threading import Lock
from typing import Any

_LOCK = Lock()
_COUNTERS: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
_TIMERS: dict[tuple[str, tuple[tuple[str, str], ...]], dict[str, float]] = {}


def _normalize_labels(labels: dict[str, object]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(key), str(value)) for key, value in labels.items() if value is not None))


def increment_counter(name: str, value: float = 1.0, **labels: object) -> None:
    key = (str(name), _normalize_labels(labels))
    with _LOCK:
        _COUNTERS[key] = float(_COUNTERS.get(key, 0.0)) + float(value)


def observe_duration(name: str, duration_ms: float, **labels: object) -> None:
    key = (str(name), _normalize_labels(labels))
    value = max(0.0, float(duration_ms))
    with _LOCK:
        current = _TIMERS.get(key)
        if current is None:
            _TIMERS[key] = {
                "count": 1.0,
                "sum_ms": value,
                "max_ms": value,
            }
            return
        current["count"] = float(current.get("count", 0.0)) + 1.0
        current["sum_ms"] = float(current.get("sum_ms", 0.0)) + value
        current["max_ms"] = max(float(current.get("max_ms", 0.0)), value)


def snapshot_metrics() -> dict[str, list[dict[str, Any]]]:
    with _LOCK:
        counters = [
            {"name": name, "labels": dict(label_items), "value": value}
            for (name, label_items), value in sorted(_COUNTERS.items())
        ]
        timers = []
        for (name, label_items), values in sorted(_TIMERS.items()):
            count = float(values.get("count", 0.0))
            sum_ms = float(values.get("sum_ms", 0.0))
            max_ms = float(values.get("max_ms", 0.0))
            timers.append(
                {
                    "name": name,
                    "labels": dict(label_items),
                    "count": int(count),
                    "sum_ms": sum_ms,
                    "avg_ms": (sum_ms / count) if count else 0.0,
                    "max_ms": max_ms,
                }
            )
        return {"counters": counters, "timers": timers}


def clear_metrics() -> None:
    with _LOCK:
        _COUNTERS.clear()
        _TIMERS.clear()
