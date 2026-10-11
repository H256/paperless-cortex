"""Bounded, TTL-expiring cache shared by the module-level document caches.

The previous caches stored ``{key: payload}`` + ``{key: timestamp}`` dicts whose
TTL was only a read gate: expired entries were never removed and there was no
size bound, so they grew monotonically until the process was restarted.

``TtlLruCache`` keeps at most ``maxsize`` entries and evicts expired ones on
access (TTL) and least-recently-used entries on write (size), so memory stays
bounded. It is thread-safe and preserves the caller's copy-on-read/write
semantics (the helper stores and returns the value it is given as-is).
"""

from __future__ import annotations

import time
from collections import OrderedDict
from threading import Lock
from typing import Any


class TtlLruCache:
    """A size-bounded, TTL-expiring LRU cache.

    - ``get`` purges expired entries, marks the key most-recently-used, and
      returns the stored value (or ``None`` if absent/expired).
    - ``put`` stores the value, marks it most-recently-used, and evicts
      least-recently-used entries beyond ``maxsize``.
    - ``invalidate`` removes a single key; ``clear`` empties the cache.
    """

    def __init__(self, *, ttl_seconds: float, maxsize: int) -> None:
        self._ttl = float(ttl_seconds)
        self._maxsize = max(1, int(maxsize))
        self._lock = Lock()
        self._entries: OrderedDict[Any, tuple[Any, float]] = OrderedDict()

    def _purge_expired_locked(self, now: float) -> None:
        stale = [k for k, (_, ts) in self._entries.items() if (now - ts) >= self._ttl]
        for k in stale:
            del self._entries[k]

    def get(self, key: Any) -> Any | None:
        now = time.time()
        with self._lock:
            self._purge_expired_locked(now)
            entry = self._entries.get(key)
            if entry is None:
                return None
            value, ts = entry
            if (now - ts) >= self._ttl:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return value

    def put(self, key: Any, value: Any) -> None:
        now = time.time()
        with self._lock:
            self._purge_expired_locked(now)
            self._entries[key] = (value, now)
            self._entries.move_to_end(key)
            while len(self._entries) > self._maxsize:
                self._entries.popitem(last=False)

    def invalidate(self, key: Any) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def snapshot(self) -> dict[Any, tuple[Any, float]]:
        """Return a copy of ``{key: (value, timestamp)}`` for tests."""
        with self._lock:
            return dict(self._entries)
