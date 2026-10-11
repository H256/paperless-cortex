from __future__ import annotations

from typing import Any

from app.config import load_settings
from app.services.integrations import paperless


def _enabled_settings(monkeypatch: Any) -> Any:
    monkeypatch.setenv("PAPERLESS_BASE_URL", "http://paperless.local")
    monkeypatch.setenv("PAPERLESS_API_TOKEN", "token-123")
    monkeypatch.setenv("HTTPX_VERIFY_TLS", "0")
    # _cache_enabled is off under pytest (PYTEST_CURRENT_TEST set); force it on so
    # the cached code paths (and their eviction) are exercised.
    monkeypatch.setattr(paperless, "_cache_enabled", lambda settings, ttl: True)
    return load_settings()


def test_list_cache_evicts_expired_on_access(monkeypatch: Any) -> None:
    settings = _enabled_settings(monkeypatch)
    now = 1000.0
    monkeypatch.setattr(paperless.time, "time", lambda: now)
    # 500 expired list entries (older than the 10s TTL) + 1 fresh entry.
    for i in range(500):
        paperless._LIST_CACHE[f"stale-{i}"] = (now - 20.0, {"results": [i]})
    fresh_key = paperless._list_cache_key({"q": "fresh"})
    paperless._LIST_CACHE[fresh_key] = (now - 1.0, {"results": ["fresh"]})
    assert len(paperless._LIST_CACHE) == 501

    # A fresh read must prune the expired entries without touching the network.
    payload = paperless.list_documents_cached(settings, q="fresh")

    assert payload == {"results": ["fresh"]}
    # The fresh entry survives; the cache is bounded (not 501).
    assert fresh_key in paperless._LIST_CACHE
    assert len(paperless._LIST_CACHE) <= paperless._LIST_CACHE_MAXSIZE


def test_doc_cache_evicts_expired_on_access(monkeypatch: Any) -> None:
    settings = _enabled_settings(monkeypatch)
    now = 1000.0
    monkeypatch.setattr(paperless.time, "time", lambda: now)
    for i in range(500):
        paperless._DOC_CACHE[i] = (now - 20.0, {"id": i})
    paperless._DOC_CACHE[999] = (now - 1.0, {"id": 999})
    assert len(paperless._DOC_CACHE) == 501

    payload = paperless.get_document_cached(settings, 999)

    assert payload == {"id": 999}
    # The fresh entry survives; the cache is bounded (not 501).
    assert 999 in paperless._DOC_CACHE
    assert len(paperless._DOC_CACHE) <= paperless._DOC_CACHE_MAXSIZE


def test_list_cache_is_bounded_by_maxsize(monkeypatch: Any) -> None:
    settings = _enabled_settings(monkeypatch)
    now = 1000.0
    monkeypatch.setattr(paperless.time, "time", lambda: now)
    monkeypatch.setattr(paperless, "list_documents", lambda *a, **k: {"results": []})
    # Fill with fresh entries beyond the size cap; access must evict the oldest.
    for i in range(paperless._LIST_CACHE_MAXSIZE + 50):
        paperless._LIST_CACHE[f"k-{i}"] = (now - 1.0, {"results": [i]})
    paperless.list_documents_cached(settings, q="cap")
    assert len(paperless._LIST_CACHE) <= paperless._LIST_CACHE_MAXSIZE


def test_doc_cache_is_bounded_by_maxsize(monkeypatch: Any) -> None:
    settings = _enabled_settings(monkeypatch)
    now = 1000.0
    monkeypatch.setattr(paperless.time, "time", lambda: now)
    monkeypatch.setattr(paperless, "get_document", lambda *a, **k: {"id": 0})
    for i in range(paperless._DOC_CACHE_MAXSIZE + 50):
        paperless._DOC_CACHE[i] = (now - 1.0, {"id": i})
    paperless.get_document_cached(settings, 0)
    assert len(paperless._DOC_CACHE) <= paperless._DOC_CACHE_MAXSIZE
