from __future__ import annotations

from typing import Any

import app.services.ai.suggestions as suggestions_mod
from app.config import load_settings


def _make_settings(monkeypatch: Any, **overrides: Any) -> Any:
    for key, value in overrides.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, str(value))
    return load_settings()


def test_generate_suggestions_and_field_variants_share_structure(
    monkeypatch: Any,
) -> None:
    settings = _make_settings(monkeypatch, LLM_DEBUG="1")

    captured: dict[str, Any] = {"prompts": [], "calls": 0}

    def fake_chat_completion(
        _settings: Any,
        *,
        model: str,
        messages: list[dict[str, Any]],
        timeout: float | None = None,
        **_kw: Any,
    ) -> str:
        captured["prompts"].append(messages[0]["content"])
        captured["calls"] += 1
        return '{"title": "T", "raw_marker": true}'

    monkeypatch.setattr(suggestions_mod.llm_client, "chat_completion", fake_chat_completion)
    monkeypatch.setattr(suggestions_mod, "ensure_text_llm_ready", lambda _s: None)
    monkeypatch.setattr(
        suggestions_mod, "_load_prompt", lambda _s: "meta={metadata} text={text}"
    )
    monkeypatch.setattr(
        suggestions_mod,
        "_load_field_prompt",
        lambda _f: "meta={metadata} count={count} current={current} text={text}",
    )

    document = {"id": 1, "title": "T"}
    tags = ["a"]
    correspondents = ["c"]

    base = suggestions_mod.generate_suggestions(
        settings, document, "DOC", tags=tags, correspondents=correspondents
    )
    field = suggestions_mod.generate_field_variants(
        settings,
        document,
        "DOC",
        tags=tags,
        correspondents=correspondents,
        field="title",
        count=3,
        current_value="existing",
    )

    assert captured["calls"] == 2
    # Both assemble the shared metadata/text placeholders identically.
    assert '"title": "T"' in captured["prompts"][0]
    assert "DOC" in captured["prompts"][0]
    # Field variants additionally inject the extra placeholders.
    assert "count=3" in captured["prompts"][1]
    assert '"existing"' in captured["prompts"][1]

    # Both parse the JSON response into the same structure.
    assert base == field
    assert base["title"] == "T"
    assert base["raw_marker"] is True


def test_suggestion_llm_helper_json_parse_fallback(
    monkeypatch: Any,
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
        return "not-json"

    monkeypatch.setattr(suggestions_mod.llm_client, "chat_completion", fake_chat_completion)
    monkeypatch.setattr(suggestions_mod, "ensure_text_llm_ready", lambda _s: None)
    monkeypatch.setattr(
        suggestions_mod, "_load_prompt", lambda _s: "meta={metadata} text={text}"
    )

    result = suggestions_mod.generate_suggestions(
        settings, {"id": 1}, "DOC", tags=[], correspondents=[]
    )

    # JSON parse failure falls back to {"raw": ...} (not an exception).
    assert result == {"raw": "not-json"}
