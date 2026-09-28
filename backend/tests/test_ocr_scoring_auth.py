from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.config import ModelProviderRuntime, ModelProvidersRuntime, load_settings
from app.services.ai import ocr_scoring


def _settings_with_key(api_key: str | None) -> Any:
    settings = load_settings(apply_runtime_overrides=False)
    provider = ModelProviderRuntime(
        base_url="http://llm.local", api_key=api_key, model="test-model"
    )
    return replace(
        settings,
        vision=replace(settings.vision, ocr_chat_base_url="http://llm.local"),
        model_providers=ModelProvidersRuntime(
            text=provider, chat=provider, embedding=provider, vision=provider
        ),
    )


class _FakeResponse:
    def __init__(self, status: int, payload: dict[str, Any] | str) -> None:
        self.status_code = status
        self._payload = payload

    def json(self) -> Any:
        if isinstance(self._payload, str):
            raise ValueError("not json")
        return self._payload

    @property
    def text(self) -> str:
        return self._payload if isinstance(self._payload, str) else str(self._payload)


class _FakeClient:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = list(responses)
        self.post_calls: list[dict[str, Any]] = []
        self.is_closed = False

    def post(self, url: str, json: dict[str, Any] | None = None,
             headers: dict[str, str] | None = None) -> _FakeResponse:
        self.post_calls.append({"url": url, "headers": headers or {}})
        return self._responses.pop(0)

    def close(self) -> None:
        self.is_closed = True


def _install_client(monkeypatch: Any, client: _FakeClient) -> None:
    monkeypatch.setattr(ocr_scoring, "_shared_client", lambda *a, **k: client)


def test_auth_headers_sends_bearer_when_key_set() -> None:
    settings = _settings_with_key("secret-key-1234")
    assert ocr_scoring._auth_headers(settings) == {
        "Authorization": "Bearer secret-key-1234"
    }


def test_auth_headers_empty_when_no_key() -> None:
    settings = _settings_with_key(None)
    assert ocr_scoring._auth_headers(settings) == {}


def test_post_json_sends_auth_header(monkeypatch: Any) -> None:
    settings = _settings_with_key("secret-key-1234")
    client = _FakeClient([_FakeResponse(200, {"ok": True})])
    _install_client(monkeypatch, client)
    status, _ = ocr_scoring._post_json(settings, "http://llm.local/v1/completions", {}, 5)
    assert status == 200
    assert client.post_calls[0]["headers"] == {"Authorization": "Bearer secret-key-1234"}


def test_post_json_no_auth_header_when_keyless(monkeypatch: Any) -> None:
    settings = _settings_with_key(None)
    client = _FakeClient([_FakeResponse(200, {"ok": True})])
    _install_client(monkeypatch, client)
    ocr_scoring._post_json(settings, "http://llm.local/v1/completions", {}, 5)
    assert client.post_calls[0]["headers"] == {}


def test_ppl_reports_auth_failed_on_401(monkeypatch: Any) -> None:
    settings = _settings_with_key("secret-key-1234")
    client = _FakeClient([_FakeResponse(401, {"error": "unauthorized"})])
    _install_client(monkeypatch, client)
    result = ocr_scoring.try_prompt_logprob_ppl(settings, "x" * 200, "test-model")
    assert result == {"supported": False, "reason": "auth failed"}


def test_ppl_reports_auth_failed_on_403(monkeypatch: Any) -> None:
    settings = _settings_with_key("secret-key-1234")
    client = _FakeClient([_FakeResponse(403, {"error": "forbidden"})])
    _install_client(monkeypatch, client)
    result = ocr_scoring.try_prompt_logprob_ppl(settings, "x" * 200, "test-model")
    assert result == {"supported": False, "reason": "auth failed"}


def test_ppl_works_on_keyless_endpoint(monkeypatch: Any) -> None:
    settings = _settings_with_key(None)
    payload = {"choices": [{"logprobs": {"token_logprobs": [-0.5, -1.0]}}]}
    client = _FakeClient([_FakeResponse(200, payload)])
    _install_client(monkeypatch, client)
    result = ocr_scoring.try_prompt_logprob_ppl(settings, "x" * 200, "test-model")
    assert result["supported"] is True
    assert result["tokens"] == 2
    assert client.post_calls[0]["headers"] == {}
