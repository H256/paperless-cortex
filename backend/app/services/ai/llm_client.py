from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Literal

import httpx
from openai import BadRequestError, OpenAI

if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.config import Settings

logger = logging.getLogger(__name__)


def _llm_debug_enabled() -> bool:
    return os.getenv("LLM_DEBUG", "0") == "1"


def _llm_debug_full_response_enabled() -> bool:
    return os.getenv("LLM_DEBUG_FULL_RESPONSE", "0") == "1"


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
    return _require(settings.llm_base_url, "LLM_BASE_URL")


def base_url_for_purpose(
    settings: Settings,
    purpose: Literal["text", "vision", "embedding"] = "text",
) -> str:
    """Get the appropriate LLM base URL for a specific purpose.

    Different purposes (text, vision, embedding) can use different
    endpoints if configured separately in settings.

    Args:
        settings: Application settings
        purpose: Type of LLM operation ("text", "vision", or "embedding")

    Returns:
        Base URL appropriate for the specified purpose

    Raises:
        RuntimeError: If required URL is not configured
    """
    if purpose == "vision":
        return _require(settings.ocr_vision_base_url or settings.llm_base_url, "LLM_BASE_URL")
    if purpose == "embedding":
        return _require(settings.llm_base_url, "LLM_BASE_URL")
    return _require(settings.ocr_chat_base_url or settings.llm_base_url, "LLM_BASE_URL")


def sdk_base_url(
    settings: Settings,
    purpose: Literal["text", "vision", "embedding"] = "text",
) -> str:
    return f"{base_url_for_purpose(settings, purpose=purpose)}/v1"


def client(settings: Settings, timeout: float | None) -> httpx.Client:
    return httpx.Client(timeout=timeout, verify=settings.httpx_verify_tls)


def headers(settings: Settings) -> dict[str, str]:
    api_key = getattr(settings, "llm_api_key", None)
    if api_key:
        return {"Authorization": f"Bearer {api_key}"}
    return {}


def _sdk_client(
    settings: Settings,
    timeout: float | None,
    purpose: Literal["text", "vision", "embedding"] = "text",
) -> OpenAI:
    api_key = settings.llm_api_key or "no-key"
    return OpenAI(
        base_url=sdk_base_url(settings, purpose=purpose),
        api_key=api_key,
        timeout=timeout,
    )


def chat_completion(
    settings: Settings,
    *,
    model: str,
    messages: list[dict[str, object]],
    timeout: float | None,
    purpose: Literal["text", "vision"] = "text",
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
    debug_enabled = _llm_debug_enabled()
    debug_full_response = _llm_debug_full_response_enabled()
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
    purpose: Literal["text", "vision"] = "text",
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
