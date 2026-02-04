from __future__ import annotations

import json
import logging
from typing import Iterable

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


def _require(value: str | None, env_name: str) -> str:
    if not value:
        raise RuntimeError(f"{env_name} not set")
    return value.rstrip("/")


def base_url(settings: Settings) -> str:
    return _require(settings.llm_base_url, "LLM_BASE_URL")


def client(settings: Settings, timeout: float | None) -> httpx.Client:
    return httpx.Client(timeout=timeout, verify=settings.httpx_verify_tls)


def headers(settings: Settings) -> dict[str, str]:
    api_key = getattr(settings, "llm_api_key", None)
    if api_key:
        return {"Authorization": f"Bearer {api_key}"}
    return {}


def chat_completion(
    settings: Settings,
    base_url: str,
    *,
    model: str,
    messages: list[dict[str, object]],
    timeout: float | None,
) -> str:
    with client(settings, timeout=timeout) as http:
        response = http.post(
            f"{base_url}/v1/chat/completions",
            headers=headers(settings),
            json={
                "model": model,
                "messages": messages,
                "stream": False,
            },
        )
        response.raise_for_status()
        payload = response.json()
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError("LLM response missing choices")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if content is None:
        raise RuntimeError("LLM response missing content")
    return str(content).strip()


def stream_chat_completion(
    settings: Settings,
    base_url: str,
    *,
    model: str,
    messages: list[dict[str, object]],
    timeout: float | None,
) -> Iterable[str]:
    with client(settings, timeout=timeout) as http:
        with http.stream(
            "POST",
            f"{base_url}/v1/chat/completions",
            headers=headers(settings),
            json={
                "model": model,
                "messages": messages,
                "stream": True,
            },
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                if line.startswith("data:"):
                    line = line.split("data:", 1)[1].strip()
                if not line:
                    continue
                if line == "[DONE]":
                    break
                try:
                    data = json.loads(line)
                except Exception:
                    continue
                choices = data.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                token = delta.get("content")
                if token:
                    yield str(token)
