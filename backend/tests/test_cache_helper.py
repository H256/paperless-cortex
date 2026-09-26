"""Focused tests for the bounded, TTL-expiring LRU cache helper (issue #211)."""

from __future__ import annotations

import time

import pytest

from app.services.documents.cache import TtlLruCache


class _Clock:
    """A controllable clock: call ``advance`` to move time deterministically."""

    def __init__(self, start: float = 1000.0) -> None:
        self._t = start

    def now(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


@pytest.fixture()
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    """A controllable clock: call ``clock.advance`` to move time deterministically."""
    clock = _Clock()
    monkeypatch.setattr(time, "time", clock.now)
    return clock


def test_get_returns_none_when_absent(clock: _Clock) -> None:
    cache = TtlLruCache(ttl_seconds=15, maxsize=8)
    assert cache.get("missing") is None


def test_put_then_get_roundtrip(clock: _Clock) -> None:
    cache = TtlLruCache(ttl_seconds=15, maxsize=8)
    cache.put("a", {"v": 1})
    assert cache.get("a") == {"v": 1}
    assert len(cache) == 1


def test_expired_entry_is_evicted_on_access(clock: _Clock) -> None:
    cache = TtlLruCache(ttl_seconds=15, maxsize=8)
    cache.put("a", {"v": 1})
    clock.advance(16)  # beyond TTL
    assert cache.get("a") is None
    assert len(cache) == 0


def test_expired_entries_purged_on_any_access(clock: _Clock) -> None:
    cache = TtlLruCache(ttl_seconds=15, maxsize=8)
    cache.put("a", {"v": 1})
    cache.put("b", {"v": 2})
    clock.advance(16)
    # Accessing a (expired) purges b too, even though b was never touched.
    assert cache.get("a") is None
    assert len(cache) == 0


def test_size_bound_evicts_least_recently_used(clock: _Clock) -> None:
    cache = TtlLruCache(ttl_seconds=15, maxsize=2)
    cache.put("a", {"v": 1})
    cache.put("b", {"v": 2})
    cache.get("a")  # make a most-recently-used
    cache.put("c", {"v": 3})  # evicts LRU (b)
    assert cache.get("b") is None
    assert cache.get("a") == {"v": 1}
    assert cache.get("c") == {"v": 3}
    assert len(cache) == 2


def test_maxsize_never_exceeded_after_many_puts(clock: _Clock) -> None:
    cache = TtlLruCache(ttl_seconds=15, maxsize=3)
    for i in range(50):
        cache.put(f"k{i}", i)
    assert len(cache) <= 3


def test_invalidate_removes_single_key(clock: _Clock) -> None:
    cache = TtlLruCache(ttl_seconds=15, maxsize=8)
    cache.put("a", {"v": 1})
    cache.put("b", {"v": 2})
    cache.invalidate("a")
    assert cache.get("a") is None
    assert cache.get("b") == {"v": 2}


def test_clear_empties_cache(clock: _Clock) -> None:
    cache = TtlLruCache(ttl_seconds=15, maxsize=8)
    cache.put("a", {"v": 1})
    cache.clear()
    assert len(cache) == 0
    assert cache.get("a") is None


def test_snapshot_reports_keys_and_timestamps(clock: _Clock) -> None:
    cache = TtlLruCache(ttl_seconds=15, maxsize=8)
    cache.put("a", {"v": 1})
    snap = cache.snapshot()
    assert set(snap) == {"a"}
    value, ts = snap["a"]
    assert value == {"v": 1}
    assert ts == clock.now()


def test_ttl_boundary_exact_is_expired(clock: _Clock) -> None:
    cache = TtlLruCache(ttl_seconds=15, maxsize=8)
    cache.put("a", {"v": 1})
    clock.advance(15)  # exactly TTL -> expired
    assert cache.get("a") is None
