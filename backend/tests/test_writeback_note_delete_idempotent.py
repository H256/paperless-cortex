from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import httpx

from app.config import load_settings
from app.services.integrations import paperless

if TYPE_CHECKING:
    from collections.abc import Iterator


def _settings_with_paperless(monkeypatch: Any) -> Any:
    monkeypatch.setenv("PAPERLESS_BASE_URL", "http://paperless.local")
    monkeypatch.setenv("PAPERLESS_API_TOKEN", "token-123")
    monkeypatch.setenv("HTTPX_VERIFY_TLS", "0")
    return load_settings()


def _make_response(status_code: int) -> httpx.Response:
    request = httpx.Request("DELETE", "http://paperless.local/api/documents/42/notes/")
    return httpx.Response(status_code, request=request)


def _patch_client(monkeypatch: Any, status_code: int) -> None:
    class _FakeClient:
        def delete(self, *args: Any, **kwargs: Any) -> httpx.Response:
            return _make_response(status_code)

    @contextmanager
    def _client(_settings: Any) -> Iterator[_FakeClient]:
        yield _FakeClient()

    monkeypatch.setattr(paperless, "client", _client)
    # Avoid touching the real document cache.
    monkeypatch.setattr(paperless, "invalidate_document_cache", lambda *a, **k: None)


def test_delete_document_note_treats_404_as_success(monkeypatch: Any) -> None:
    settings = _settings_with_paperless(monkeypatch)
    _patch_client(monkeypatch, 404)

    # A 404 (note already gone) must not raise, so a replayed writeback job can
    # complete instead of failing permanently on the stale DELETE.
    paperless.delete_document_note(settings, 42, 7)


def test_delete_document_note_still_raises_on_other_errors(monkeypatch: Any) -> None:
    settings = _settings_with_paperless(monkeypatch)
    _patch_client(monkeypatch, 500)

    try:
        paperless.delete_document_note(settings, 42, 7)
    except httpx.HTTPStatusError:
        return
    raise AssertionError("Expected HTTPStatusError for a 500 response")


def test_delete_document_note_succeeds_on_2xx(monkeypatch: Any) -> None:
    settings = _settings_with_paperless(monkeypatch)
    _patch_client(monkeypatch, 200)

    paperless.delete_document_note(settings, 42, 7)
