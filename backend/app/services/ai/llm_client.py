from __future__ import annotations

import atexit
import logging
import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING, Literal

import httpx
from openai import BadRequestError, OpenAI

from app.services.runtime.model_providers import provider_api_key, provider_base_url

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from app.config import Settings

logger = logging.getLogger(__name__)
_CLIENT_LOCK = threading.Lock()
_CLIENTS: dict[tuple[float | None, bool], httpx.Client] = {}
_SDK_CLIENTS: dict[tuple[str, str, float | None], OpenAI] = {}


def _snippet(value: object, max_len: int = 500) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", "\\n")
    if len(text) <= max_len:
        return text
    return text[:max_len] + "...<truncated>"


def _message_content_preview(content: object) -> str:
    if isinstance(content, str):
        return _snippet(content)
    if isinstance(content, list):
        parts: list[str] = []
        for item in content[:5]:
            if isinstance(item, dict):
                item_type = str(item.get("type") or "")
                if item_type == "text":
                    parts.append(f"text:{_snippet(item.get('text') or '', 180)}")
                elif item_type == "input_text":
                    parts.append(f"input_text:{_snippet(item.get('text') or '', 180)}")
                elif item_type:
                    parts.append(item_type)
                else:
                    parts.append(_snippet(item, 120))
            else:
                parts.append(_snippet(item, 120))
        return _snippet(" | ".join(parts), 500)
    return _snippet(content)


def _require(value: str | None, env_name: str) -> str:
    if not value:
        raise RuntimeError(f"{env_name} not set")
    return value.rstrip("/")


def base_url(settings: Settings) -> str:
    """Get the LLM base URL from settings.

    Args:
        settings: Application settings

    Returns:
        Validated and normalized LLM base URL

    Raises:
        RuntimeError: If LLM_BASE_URL is not configured
    """
    return _require(provider_base_url(settings, "text"), "LLM_BASE_URL")


def base_url_for_purpose(
    settings: Settings,
    purpose: Literal["text", "chat", "vision", "embedding"] = "text",
) -> str:
    """Get the appropriate LLM base URL for a specific purpose.

    Different purposes (text, vision, embedding) can use different
    endpoints if configured separately in settings.

    Args:
        settings: Application settings
        purpose: Type of LLM operation ("text", "chat", "vision", or "embedding")

    Returns:
        Base URL appropriate for the specified purpose

    Raises:
        RuntimeError: If required URL is not configured
    """
    if purpose == "vision":
        return _require(provider_base_url(settings, "vision"), "LLM_BASE_URL")
    if purpose == "embedding":
        return _require(provider_base_url(settings, "embedding"), "LLM_BASE_URL")
    role: Literal["text", "chat"] = "chat" if purpose == "chat" else "text"
    return _require(provider_base_url(settings, role), "LLM_BASE_URL")


def sdk_base_url(
    settings: Settings,
    purpose: Literal["text", "chat", "vision", "embedding"] = "text",
) -> str:
    return f"{base_url_for_purpose(settings, purpose=purpose)}/v1"


def clear_client_pool() -> None:
    with _CLIENT_LOCK:
        clients = list(_CLIENTS.values())
        _CLIENTS.clear()
        sdk_clients = list(_SDK_CLIENTS.values())
        _SDK_CLIENTS.clear()
    for pooled_client in clients:
        pooled_client.close()
    for sdk_client in sdk_clients:
        sdk_client.close()


@atexit.register
def _close_pooled_clients() -> None:
    clear_client_pool()


def _client_key(settings: Settings, timeout: float | None) -> tuple[float | None, bool]:
    return (float(timeout) if timeout is not None else None, bool(settings.httpx_verify_tls))


def _shared_client(settings: Settings, timeout: float | None) -> httpx.Client:
    key = _client_key(settings, timeout)
    with _CLIENT_LOCK:
        pooled_client = _CLIENTS.get(key)
        if pooled_client is None or pooled_client.is_closed:
            pooled_client = httpx.Client(timeout=timeout, verify=settings.httpx_verify_tls)
            _CLIENTS[key] = pooled_client
        return pooled_client


@contextmanager
def client(settings: Settings, timeout: float | None) -> Iterator[httpx.Client]:
    yield _shared_client(settings, timeout)


def headers(settings: Settings) -> dict[str, str]:
    api_key = provider_api_key(settings, "text")
    if api_key:
        return {"Authorization": f"Bearer {api_key}"}
    return {}


def _sdk_client(
    settings: Settings,
    timeout: float | None,
    purpose: Literal["text", "chat", "vision", "embedding"] = "text",
) -> OpenAI:
    base = sdk_base_url(settings, purpose=purpose)
    role: Literal["text", "chat", "embedding", "vision"]
    if purpose == "vision":
        role = "vision"
    elif purpose == "embedding":
        role = "embedding"
    elif purpose == "chat":
        role = "chat"
    else:
        role = "text"
    api_key = provider_api_key(settings, role) or "no-key"
    key = (base, api_key, float(timeout) if timeout is not None else None)
    with _CLIENT_LOCK:
        pooled_client = _SDK_CLIENTS.get(key)
        if pooled_client is None:
            pooled_client = OpenAI(
                base_url=base,
                api_key=api_key,
                timeout=timeout,
            )
            _SDK_CLIENTS[key] = pooled_client
        return pooled_client


def chat_completion(
    settings: Settings,
    *,
    model: str,
    messages: list[dict[str, object]],
    timeout: float | None,
    purpose: Literal["text", "chat", "vision"] = "text",
    max_tokens: int | None = None,
    temperature: float | None = None,
    json_mode: bool = False,
) -> str:
    """Execute an LLM chat completion request.

    This is the primary function for calling LLM models. It supports both
    text and vision models, with optional JSON mode and parameter control.

    Args:
        settings: Application settings with LLM configuration
        model: Name of the model to use
        messages: Chat messages in OpenAI format (list of dicts with role/content)
        timeout: Request timeout in seconds, or None for no timeout
        purpose: Whether this is a "text" or "vision" model call
        max_tokens: Maximum tokens in response, or None for model default
        temperature: Sampling temperature (0.0-2.0), or None for model default
        json_mode: If True, request JSON-formatted output

    Returns:
        String content of the model's response

    Raises:
        RuntimeError: If LLM response is malformed or empty
        Exception: Various exceptions from OpenAI SDK for API errors

    Example:
        >>> messages = [{"role": "user", "content": "Summarize this document"}]
        >>> response = chat_completion(
        ...     settings,
        ...     model="gpt-4",
        ...     messages=messages,
        ...     timeout=30.0
        ... )
    """
    client_sdk = _sdk_client(settings, timeout=timeout, purpose=purpose)
    debug_enabled = bool(settings.debug.llm)
    debug_full_response = bool(settings.debug.llm_full_response)
    if debug_enabled:
        logger.info(
            "LLM chat request model=%s purpose=%s timeout=%s max_tokens=%s msg_count=%s",
            model,
            purpose,
            timeout,
            max_tokens,
            len(messages),
        )
        for idx, message in enumerate(messages[:4]):
            role = str(message.get("role") or "unknown")
            preview = _message_content_preview(message.get("content"))
            logger.info("LLM chat request message[%s] role=%s snippet=%s", idx, role, preview)
    kwargs: dict[str, object] = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = int(max_tokens)
    if temperature is not None:
        kwargs["temperature"] = float(temperature)
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = client_sdk.chat.completions.create(**kwargs)
    except BadRequestError:
        if not json_mode:
            raise
        # Some OpenAI-compatible servers do not implement response_format.
        if debug_enabled:
            logger.warning(
                "LLM json_mode unsupported; retrying without response_format model=%s",
                model,
            )
        kwargs.pop("response_format", None)
        response = client_sdk.chat.completions.create(**kwargs)
    choices = response.choices or []
    if not choices:
        raise RuntimeError("LLM response missing choices")
    message = choices[0].message
    content = message.content
    if content is None:
        raise RuntimeError("LLM response missing content")
    result = str(content).strip()
    if debug_enabled:
        if debug_full_response:
            logger.info("LLM chat response model=%s full=%s", model, result)
        else:
            logger.info("LLM chat response model=%s snippet=%s", model, _snippet(result))
    return result


def stream_chat_completion(
    settings: Settings,
    *,
    model: str,
    messages: list[dict[str, object]],
    timeout: float | None,
    purpose: Literal["text", "chat", "vision"] = "text",
    max_tokens: int | None = None,
) -> Iterable[str]:
    client_sdk = _sdk_client(settings, timeout=timeout, purpose=purpose)
    kwargs: dict[str, object] = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = int(max_tokens)
    stream = client_sdk.chat.completions.create(**kwargs)
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
    """Generate a vector embedding for a single text string.

    Args:
        settings: Application settings with LLM configuration
        model: Name of the embedding model to use
        text: Input text to embed
        timeout: Request timeout in seconds

    Returns:
        Vector embedding as a list of floats

    Raises:
        RuntimeError: If embedding response is invalid or empty

    Example:
        >>> vector = embedding(
        ...     settings,
        ...     model="text-embedding-3-small",
        ...     text="Document content here",
        ...     timeout=60.0
        ... )
        >>> len(vector)
        1536
    """
    client_sdk = _sdk_client(settings, timeout=timeout, purpose="embedding")
    response = client_sdk.embeddings.create(model=model, input=text)
    data = response.data or []
    if not data:
        raise RuntimeError("Invalid embedding response")
    embedding = data[0].embedding
    if not isinstance(embedding, list):
        raise RuntimeError("Invalid embedding response")
    return embedding


def embedding_many(
    settings: Settings,
    *,
    model: str,
    texts: list[str],
    timeout: float | None,
) -> list[list[float]]:
    if not texts:
        return []
    client_sdk = _sdk_client(settings, timeout=timeout, purpose="embedding")
    response = client_sdk.embeddings.create(model=model, input=texts)
    data = response.data or []
    if len(data) != len(texts):
        raise RuntimeError(
            f"Invalid embedding response length: expected {len(texts)}, got {len(data)}"
        )
    vectors: list[list[float]] = []
    for item in data:
        embedding = item.embedding
        if not isinstance(embedding, list):
            raise RuntimeError("Invalid embedding response")
        vectors.append(embedding)
    return vectors
