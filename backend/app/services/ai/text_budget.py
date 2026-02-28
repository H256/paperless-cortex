from __future__ import annotations


def truncate_chars(text: str, max_chars: int, suffix: str = "\n[TRUNCATED]") -> str:
    if max_chars <= 0:
        return text
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + suffix


def truncate_for_tokens(
    text: str,
    max_input_tokens: int,
    *,
    chars_per_token: float = 3.5,
    suffix: str = "\n[TRUNCATED]",
) -> str:
    if max_input_tokens <= 0:
        return text
    max_chars = int(max_input_tokens * chars_per_token)
    return truncate_chars(text, max_chars=max_chars, suffix=suffix)
