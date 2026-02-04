from __future__ import annotations

import logging
from typing import Iterable

import httpx
from openai import OpenAI

from app.config import Settings

logger = logging.getLogger(__name__)


def _require(value: str | None, env_name: str) -> str:
    if not value:
        raise RuntimeError(f"{env_name} not set")
    return value.rstrip("/")


def base_url(settings: Settings) -> str:
    return _require(settings.llm_base_url, "LLM_BASE_URL")


def sdk_base_url(settings: Settings) -> str:
    return f"{base_url(settings)}/v1"


def client(settings: Settings, timeout: float | None) -> httpx.Client:
    return httpx.Client(timeout=timeout, verify=settings.httpx_verify_tls)


def headers(settings: Settings) -> dict[str, str]:
    api_key = getattr(settings, "llm_api_key", None)
    if api_key:
        return {"Authorization": f"Bearer {api_key}"}
    return {}


def _sdk_client(settings: Settings, timeout: float | None) -> OpenAI:
    api_key = settings.llm_api_key or "no-key"
    return OpenAI(base_url=sdk_base_url(settings), api_key=api_key, timeout=timeout)


def chat_completion(
    settings: Settings,
    *,
    model: str,
    messages: list[dict[str, object]],
    timeout: float | None,
) -> str:
    client_sdk = _sdk_client(settings, timeout=timeout)
    response = client_sdk.chat.completions.create(
        model=model,
        messages=messages,
        stream=False,
    )
    choices = response.choices or []
    if not choices:
        raise RuntimeError("LLM response missing choices")
    message = choices[0].message
    content = message.content
    if content is None:
        raise RuntimeError("LLM response missing content")
    return str(content).strip()


def stream_chat_completion(
    settings: Settings,
    *,
    model: str,
    messages: list[dict[str, object]],
    timeout: float | None,
) -> Iterable[str]:
    client_sdk = _sdk_client(settings, timeout=timeout)
    stream = client_sdk.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
    )
    for event in stream:
        choices = event.choices or []
        if not choices:
            continue
        delta = choices[0].delta
        token = delta.content
        if token:
            yield str(token)


def embedding(
    settings: Settings,
    *,
    model: str,
    text: str,
    timeout: float | None,
) -> list[float]:
    client_sdk = _sdk_client(settings, timeout=timeout)
    response = client_sdk.embeddings.create(model=model, input=text)
    data = response.data or []
    if not data:
        raise RuntimeError("Invalid embedding response")
    embedding = data[0].embedding
    if not isinstance(embedding, list):
        raise RuntimeError("Invalid embedding response")
    return embedding
