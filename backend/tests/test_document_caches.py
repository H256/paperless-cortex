"""Per-cache eviction tests for the bounded document caches (issue #211).

The 3 multi-entry caches (documents_list_cache, local_document_cache,
page_texts_cache) are now backed by TtlLruCache, so expired entries are
purged on access and the entry count is bounded by maxsize. The 2
single-entry caches (dashboard_cache, document_stats_cache) are already
size-bounded (one entry) and are pinned here as regression tests.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, cast

import pytest

from app.services.documents import (
    dashboard_cache,
    document_stats_cache,
    documents_list_cache,
    local_document_cache,
    page_texts_cache,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_SENTINEL_SESSION = cast("Session", object())


class _Clock:
    def __init__(self, start: float = 1000.0) -> None:
        self._t = start

    def now(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


@pytest.fixture()
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    clock = _Clock()
    monkeypatch.setattr(time, "time", clock.now)
    return clock


def _counting_build(counter: dict[str, int], value: dict[str, object]) -> dict[str, object]:
    counter["n"] = counter.get("n", 0) + 1
    return value


def test_local_document_cache_is_size_bounded() -> None:
    local_document_cache.invalidate_local_document_cache()
    for i in range(local_document_cache._CACHE_MAXSIZE + 10):
        local_document_cache.get_cached_local_document_payload(
            doc_id=i,
            build_payload=lambda _i=i: {"doc_id": _i},
        )
    assert len(local_document_cache._CACHE) <= local_document_cache._CACHE_MAXSIZE


def test_local_document_cache_evicts_expired_on_access(clock: _Clock) -> None:
    local_document_cache.invalidate_local_document_cache()
    counter = {"n": 0}
    local_document_cache.get_cached_local_document_payload(
        doc_id=1, build_payload=lambda: _counting_build(counter, {"v": 1})
    )
    assert counter["n"] == 1
    clock.advance(local_document_cache._CACHE_TTL_SECONDS + 1)
    local_document_cache.get_cached_local_document_payload(
        doc_id=1, build_payload=lambda: _counting_build(counter, {"v": 1})
    )
    assert counter["n"] == 2  # rebuilt after expiry
    assert len(local_document_cache._CACHE) == 1


def test_page_texts_cache_is_size_bounded() -> None:
    page_texts_cache.invalidate_page_texts_cache()
    for i in range(page_texts_cache._CACHE_MAXSIZE + 10):
        page_texts_cache.get_cached_page_texts_payload(
            doc_id=i, build_payload=lambda _i=i: {"page": _i}
        )
    assert len(page_texts_cache._CACHE) <= page_texts_cache._CACHE_MAXSIZE


def test_page_texts_cache_evicts_expired_on_access(clock: _Clock) -> None:
    page_texts_cache.invalidate_page_texts_cache()
    counter = {"n": 0}
    page_texts_cache.get_cached_page_texts_payload(
        doc_id=1, build_payload=lambda: _counting_build(counter, {"v": 1})
    )
    clock.advance(page_texts_cache._CACHE_TTL_SECONDS + 1)
    page_texts_cache.get_cached_page_texts_payload(
        doc_id=1, build_payload=lambda: _counting_build(counter, {"v": 1})
    )
    assert counter["n"] == 2


def test_documents_list_cache_is_size_bounded() -> None:
    documents_list_cache.invalidate_documents_list_cache()
    for i in range(documents_list_cache._CACHE_MAXSIZE + 10):
        documents_list_cache.get_cached_documents_page(
            cache_key=(i, 20, None, None, None, None, None, False, False, "all"),
            build_payload=lambda: {"results": []},
        )
    assert len(documents_list_cache._CACHE) <= documents_list_cache._CACHE_MAXSIZE


def test_documents_list_cache_evicts_expired_on_access(clock: _Clock) -> None:
    documents_list_cache.invalidate_documents_list_cache()
    key = (1, 20, None, None, None, None, None, False, False, "all")
    counter = {"n": 0}
    documents_list_cache.get_cached_documents_page(
        cache_key=key, build_payload=lambda: _counting_build(counter, {"results": []})
    )
    clock.advance(documents_list_cache._CACHE_TTL_SECONDS + 1)
    documents_list_cache.get_cached_documents_page(
        cache_key=key, build_payload=lambda: _counting_build(counter, {"results": []})
    )
    assert counter["n"] == 2


def test_dashboard_cache_is_single_entry(clock: _Clock) -> None:
    dashboard_cache.invalidate_dashboard_cache()
    dashboard_cache.get_cached_dashboard_payload(
        _SENTINEL_SESSION, build_payload=lambda _db: {"a": 1}
    )
    dashboard_cache.get_cached_dashboard_payload(
        _SENTINEL_SESSION, build_payload=lambda _db: {"b": 2}
    )
    # Single-entry: at most one payload is ever held.
    data = dashboard_cache._DASHBOARD_CACHE.get("data")
    assert isinstance(data, dict)
    assert len(dashboard_cache._DASHBOARD_CACHE) == 2  # {"ts": ..., "data": ...}


def test_document_stats_cache_is_single_entry(clock: _Clock) -> None:
    document_stats_cache.invalidate_document_stats_cache()
    document_stats_cache.get_cached_document_stats(
        _SENTINEL_SESSION, build_payload=lambda _db: {"a": 1}
    )
    document_stats_cache.get_cached_document_stats(
        _SENTINEL_SESSION, build_payload=lambda _db: {"b": 2}
    )
    assert isinstance(document_stats_cache._DOCUMENT_STATS_CACHE.get("data"), dict)
    assert len(document_stats_cache._DOCUMENT_STATS_CACHE) == 2
