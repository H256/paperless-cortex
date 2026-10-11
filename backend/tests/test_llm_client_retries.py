"""Regression tests for issue #136 (AUDIT AI-010).

- The pooled OpenAI SDK client must be created with max_retries=0 so the SDK
  does not silently re-issue 429/5xx chat/embedding POSTs at up to 3x cost.
- A 400 while json_mode is set must only trigger a second chat call when the
  400 indicates response_format is unsupported, not for every 400 (e.g. an
  invalid model name).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
from openai import BadRequestError

from app.config import load_settings
from app.services.ai import llm_client


def _make_bad_request(message: str, body: object | None) -> BadRequestError:
    request = httpx.Request("POST", "http://llm.local/v1/chat/completions")
    response = httpx.Response(400, request=request, headers={"x-request-id": "x"})
    return BadRequestError(message, response=response, body=body)


def test_sdk_client_pool_passes_max_retries_zero(monkeypatch: Any) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "http://llm.local")
    monkeypatch.setenv("HTTPX_VERIFY_TLS", "1")
    settings = load_settings()
    created: list[object] = []

    class FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            self.closed = False
            created.append(self)

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(llm_client, "OpenAI", FakeOpenAI)
    llm_client.clear_client_pool()

    llm_client._sdk_client(settings, timeout=10, purpose="text")

    assert len(created) == 1
    assert created[0].kwargs["max_retries"] == 0

    llm_client.clear_client_pool()


def test_chat_completion_json_mode_invalid_model_400_does_not_retry(
    monkeypatch: Any,
) -> None:
    """An invalid-model 400 must be re-raised, not retried without
    response_format (no second paid chat call)."""
    monkeypatch.setenv("LLM_BASE_URL", "http://llm.local")
    settings = load_settings()
    calls: list[dict[str, Any]] = []

    def _create(**kwargs: object) -> Any:
        calls.append(kwargs)
        raise _make_bad_request(
            "model 'foo' not found", {"error": "model 'foo' not found"}
        )

    fake_sdk = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
    )
    monkeypatch.setattr(llm_client, "_sdk_client", lambda *a, **k: fake_sdk)

    try:
        llm_client.chat_completion(
            settings, model="foo", messages=[{"role": "user", "content": "hi"}],
            timeout=10, json_mode=True,
        )
    except BadRequestError:
        pass
    else:
        raise AssertionError("expected BadRequestError to propagate")

    # Exactly one call: the 400 was re-raised, not retried.
    assert len(calls) == 1


def test_chat_completion_json_mode_response_format_400_retries(
    monkeypatch: Any,
) -> None:
    """A 400 naming response_format must retry once without response_format."""
    monkeypatch.setenv("LLM_BASE_URL", "http://llm.local")
    settings = load_settings()
    calls: list[dict[str, Any]] = []

    def _create(**kwargs: object) -> Any:
        calls.append(kwargs)
        if "response_format" in kwargs:
            raise _make_bad_request(
                "response_format is not supported",
                {"error": "response_format is not supported"},
            )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]
        )

    fake_sdk = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
    )
    monkeypatch.setattr(llm_client, "_sdk_client", lambda *a, **k: fake_sdk)

    result = llm_client.chat_completion(
        settings, model="m", messages=[{"role": "user", "content": "hi"}],
        timeout=10, json_mode=True,
    )

    assert result == "ok"
    assert len(calls) == 2
    # First call carried response_format; the retry did not.
    assert "response_format" in calls[0]
    assert "response_format" not in calls[1]


def test_chat_completion_non_json_mode_400_propagates(monkeypatch: Any) -> None:
    """Without json_mode a 400 propagates immediately (single call)."""
    monkeypatch.setenv("LLM_BASE_URL", "http://llm.local")
    settings = load_settings()
    calls: list[dict[str, Any]] = []

    def _create(**kwargs: object) -> Any:
        calls.append(kwargs)
        raise _make_bad_request("response_format is not supported", None)

    fake_sdk = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
    )
    monkeypatch.setattr(llm_client, "_sdk_client", lambda *a, **k: fake_sdk)

    try:
        llm_client.chat_completion(
            settings, model="m", messages=[{"role": "user", "content": "hi"}],
            timeout=10, json_mode=False,
        )
    except BadRequestError:
        pass
    else:
        raise AssertionError("expected BadRequestError to propagate")

    assert len(calls) == 1
