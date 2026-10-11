from __future__ import annotations

from typing import Any

from app.config import load_settings
from app.services.integrations import meta_cache


def _reset_meta_cache() -> None:
    meta_cache._cache = {"tags": [], "correspondents": []}
    meta_cache._loaded = False
    meta_cache._last_refresh_failure = 0.0


def _settings(monkeypatch: Any) -> Any:
    monkeypatch.setenv("PAPERLESS_BASE_URL", "http://paperless.local")
    monkeypatch.setenv("PAPERLESS_API_TOKEN", "token-123")
    monkeypatch.setenv("HTTPX_VERIFY_TLS", "0")
    return load_settings()


def test_ensure_cache_skips_refetch_within_backoff_after_failure(monkeypatch: Any) -> None:
    """A failed refresh must not make every subsequent request pay a full
    paginated re-fetch: within the backoff window no HTTP call is issued."""
    _reset_meta_cache()
    settings = _settings(monkeypatch)
    state = {"tag_calls": 0}

    def down_tags(_settings: Any, **_kw: Any) -> Any:
        state["tag_calls"] += 1
        raise RuntimeError("paperless down")

    def down_corr(_settings: Any, **_kw: Any) -> Any:
        raise RuntimeError("paperless down")

    monkeypatch.setattr(meta_cache.paperless, "list_tags", down_tags)
    monkeypatch.setattr(meta_cache.paperless, "list_correspondents", down_corr)
    monkeypatch.setattr(meta_cache, "_now", lambda: 1000.0)

    # First request: not loaded, no backoff yet -> one refresh (fails).
    meta_cache.get_cached_tags(settings)
    assert state["tag_calls"] == 1

    # Second request, still inside the 30s backoff window: no re-fetch.
    meta_cache.get_cached_tags(settings)
    assert state["tag_calls"] == 1


def test_ensure_cache_recovers_after_backoff_window(monkeypatch: Any) -> None:
    """Once the backoff window has elapsed, a failed cache recovers and a
    successful refresh clears the failure marker."""
    _reset_meta_cache()
    settings = _settings(monkeypatch)
    state = {"fail": True}
    now = {"t": 1000.0}

    def flaky(_settings: Any, **_kw: Any) -> Any:
        if state["fail"]:
            raise RuntimeError("paperless down")
        return {"results": [{"name": "tag-a"}]}

    monkeypatch.setattr(meta_cache.paperless, "list_tags", flaky)
    monkeypatch.setattr(meta_cache.paperless, "list_correspondents", flaky)
    monkeypatch.setattr(meta_cache, "_now", lambda: now["t"])

    meta_cache.get_cached_tags(settings)  # refresh #1 fails
    assert meta_cache._loaded is False

    now["t"] = 1000.0 + meta_cache.REFRESH_BACKOFF_SECONDS + 1.0
    state["fail"] = False
    meta_cache.get_cached_tags(settings)  # refresh #2 succeeds
    assert meta_cache._loaded is True
    assert meta_cache._last_refresh_failure == 0.0
    assert meta_cache.get_cached_tags(settings) == ["tag-a"]
