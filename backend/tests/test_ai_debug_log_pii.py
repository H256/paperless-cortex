from __future__ import annotations

from typing import Any

import app.services.ai.suggestions as suggestions_mod
import app.services.ai.vision_ocr as vision_ocr_mod
from app.config import load_settings

# A document text long enough that the assembled prompt exceeds the 500-char
# snippet cap, so an untruncated log would contain the full PII payload.
_LONG_TEXT = ("PII-PAYLOAD-" * 80)  # 960 chars


def _make_settings(monkeypatch: Any, **overrides: Any) -> Any:
    monkeypatch.setenv("LLM_DEBUG", "1")
    monkeypatch.setenv("LLM_BASE_URL", "http://llm.local")
    monkeypatch.setenv("TEXT_MODEL", "test-model")
    monkeypatch.setenv("VISION_MODEL", "test-vision")
    for key, value in overrides.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, str(value))
    return load_settings()


def test_generate_suggestions_prompt_log_is_truncated(
    monkeypatch: Any, caplog: Any
) -> None:
    settings = _make_settings(monkeypatch)

    captured: dict[str, Any] = {}

    def fake_chat_completion(
        _settings: Any,
        *,
        model: str,
        messages: list[dict[str, Any]],
        timeout: float | None = None,
        **_kw: Any,
    ) -> str:
        captured["prompt"] = messages[0]["content"]
        return "{}"

    monkeypatch.setattr(suggestions_mod.llm_client, "chat_completion", fake_chat_completion)
    monkeypatch.setattr(suggestions_mod, "ensure_text_llm_ready", lambda _s: None)
    monkeypatch.setattr(
        suggestions_mod,
        "_load_prompt",
        lambda _s: "meta={metadata} text={text}",
    )

    import logging

    caplog.set_level(logging.INFO)
    suggestions_mod.generate_suggestions(
        settings,
        {"id": 1, "title": "T"},
        _LONG_TEXT,
        tags=[],
        correspondents=[],
    )

    # The prompt sent to the model still carries the full document text...
    assert _LONG_TEXT[:20] in captured["prompt"]
    # ...but the debug log must be a truncated snippet, not the full prompt.
    prompt_logs = [
        r for r in caplog.records if r.message.startswith("Suggestions prompt:")
    ]
    assert prompt_logs, "expected a Suggestions prompt debug log"
    logged = prompt_logs[0].message
    assert "...<truncated>" in logged
    assert len(logged) < 700
    # The full PII payload must not appear in the log.
    assert _LONG_TEXT not in logged


def test_vision_generate_prompt_log_is_truncated(
    monkeypatch: Any, caplog: Any
) -> None:
    settings = _make_settings(monkeypatch)

    def fake_chat_completion(
        _settings: Any,
        *,
        model: str,
        messages: list[dict[str, Any]],
        timeout: float | None = None,
        **_kw: Any,
    ) -> str:
        return "ocr-text"

    monkeypatch.setattr(vision_ocr_mod.llm_client, "chat_completion", fake_chat_completion)
    monkeypatch.setattr(
        vision_ocr_mod, "ensure_vision_llm_ready", lambda _s, **_kw: None
    )

    import logging

    caplog.set_level(logging.INFO)
    vision_ocr_mod._vision_generate(
        settings,
        "test-vision",
        "prompt-with-pii " + _LONG_TEXT,
        b"png",
        page_number=1,
        width=100,
        height=100,
    )

    prompt_logs = [
        r for r in caplog.records if r.message.startswith("Vision OCR prompt:")
    ]
    assert prompt_logs, "expected a Vision OCR prompt debug log"
    logged = prompt_logs[0].message
    assert "...<truncated>" in logged
    assert _LONG_TEXT not in logged
