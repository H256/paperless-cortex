from __future__ import annotations

from app.config import load_settings
from app.services.chat import MAX_HISTORY_CHARS, MAX_HISTORY_TURNS, answer_question


def test_answer_question_enriches_citations_with_evidence(monkeypatch):
    settings = load_settings()

    monkeypatch.setattr("app.services.chat.ensure_text_llm_ready", lambda _settings: None)
    monkeypatch.setattr("app.services.chat.ensure_qdrant_ready", lambda _settings: None)
    monkeypatch.setattr("app.services.chat.embed_text", lambda _settings, _text: [0.1, 0.2])
    monkeypatch.setattr(
        "app.services.chat.search_points",
        lambda _settings, _vector, limit=18, **_kwargs: {
            "result": [
                {
                    "score": 0.9,
                    "payload": {
                        "doc_id": 1756,
                        "page": 3,
                        "source": "vision_ocr",
                        "text": "This is a sufficiently long snippet for evidence testing.",
                        "quality_score": 88,
                        "bbox": None,
                    },
                }
            ]
        },
    )
    monkeypatch.setattr("app.services.chat._load_prompt", lambda _settings: "{question}\n{sources}\n{history}")
    monkeypatch.setattr("app.services.chat.llm_client.chat_completion", lambda *args, **kwargs: "ok")
    def _resolver(citations, max_pages=3, settings=None, db=None):
        return [
            {
                "doc_id": 1756,
                "page": 3,
                "snippet": citations[0]["snippet"],
                "bbox": [10, 20, 30, 40],
                "confidence": 0.95,
                "status": "ok",
                "error": None,
            }
        ]

    monkeypatch.setattr("app.services.chat.resolve_evidence_matches", _resolver)

    result = answer_question(settings, question="What changed?", top_k=3)
    assert isinstance(result, dict)
    citations = result["citations"]
    assert len(citations) == 1
    assert citations[0]["evidence_status"] == "ok"
    assert citations[0]["evidence_confidence"] == 0.95
    assert citations[0]["bbox"] == [10, 20, 30, 40]


def test_answer_question_skips_evidence_for_short_snippets(monkeypatch):
    settings = load_settings()

    monkeypatch.setattr("app.services.chat.ensure_text_llm_ready", lambda _settings: None)
    monkeypatch.setattr("app.services.chat.ensure_qdrant_ready", lambda _settings: None)
    monkeypatch.setattr("app.services.chat.embed_text", lambda _settings, _text: [0.1, 0.2])
    monkeypatch.setattr(
        "app.services.chat.search_points",
        lambda _settings, _vector, limit=18, **_kwargs: {
            "result": [
                {
                    "score": 0.9,
                    "payload": {
                        "doc_id": 1756,
                        "page": 1,
                        "source": "paperless_ocr",
                        "text": "short",
                        "quality_score": 90,
                        "bbox": None,
                    },
                }
            ]
        },
    )
    monkeypatch.setattr("app.services.chat._load_prompt", lambda _settings: "{question}\n{sources}\n{history}")
    monkeypatch.setattr("app.services.chat.llm_client.chat_completion", lambda *args, **kwargs: "ok")

    called = {"value": False}

    def _resolver(citations, max_pages=3, settings=None, db=None):
        called["value"] = True
        return []

    monkeypatch.setattr("app.services.chat.resolve_evidence_matches", _resolver)

    result = answer_question(settings, question="What changed?", top_k=3)
    assert isinstance(result, dict)
    assert called["value"] is False
    assert result["citations"][0].get("evidence_status") is None


def test_answer_question_uses_configured_evidence_limits(monkeypatch):
    monkeypatch.setenv("EVIDENCE_MIN_SNIPPET_CHARS", "5")
    monkeypatch.setenv("EVIDENCE_MAX_PAGES", "2")
    settings = load_settings()

    monkeypatch.setattr("app.services.chat.ensure_text_llm_ready", lambda _settings: None)
    monkeypatch.setattr("app.services.chat.ensure_qdrant_ready", lambda _settings: None)
    monkeypatch.setattr("app.services.chat.embed_text", lambda _settings, _text: [0.1, 0.2])
    monkeypatch.setattr(
        "app.services.chat.search_points",
        lambda _settings, _vector, limit=18, **_kwargs: {
            "result": [
                {
                    "score": 0.9,
                    "payload": {
                        "doc_id": 1756,
                        "page": 1,
                        "source": "paperless_ocr",
                        "text": "long enough snippet",
                        "quality_score": 90,
                        "bbox": None,
                    },
                },
                {
                    "score": 0.8,
                    "payload": {
                        "doc_id": 1756,
                        "page": 2,
                        "source": "paperless_ocr",
                        "text": "long enough snippet 2",
                        "quality_score": 90,
                        "bbox": None,
                    },
                },
                {
                    "score": 0.7,
                    "payload": {
                        "doc_id": 1756,
                        "page": 3,
                        "source": "paperless_ocr",
                        "text": "long enough snippet 3",
                        "quality_score": 90,
                        "bbox": None,
                    },
                },
            ]
        },
    )
    monkeypatch.setattr("app.services.chat._load_prompt", lambda _settings: "{question}\n{sources}\n{history}")
    monkeypatch.setattr("app.services.chat.llm_client.chat_completion", lambda *args, **kwargs: "ok")

    called = {"max_pages": None}

    def _resolver(citations, max_pages=3, settings=None, db=None):
        called["max_pages"] = max_pages
        return [
            {
                "doc_id": c["doc_id"],
                "page": c["page"],
                "snippet": c["snippet"],
                "bbox": None,
                "confidence": 0.0,
                "status": "no_match",
                "error": None,
            }
            for c in citations
        ]

    monkeypatch.setattr("app.services.chat.resolve_evidence_matches", _resolver)

    result = answer_question(settings, question="What changed?", top_k=3)
    assert isinstance(result, dict)
    assert called["max_pages"] == 2


def test_answer_question_renumbers_citations_after_filtering(monkeypatch):
    settings = load_settings()

    monkeypatch.setattr("app.services.chat.ensure_text_llm_ready", lambda _settings: None)
    monkeypatch.setattr("app.services.chat.ensure_qdrant_ready", lambda _settings: None)
    monkeypatch.setattr("app.services.chat.embed_text", lambda _settings, _text: [0.1, 0.2])
    monkeypatch.setattr(
        "app.services.chat.search_points",
        lambda _settings, _vector, limit=18, **_kwargs: {
            "result": [
                {
                    "score": 0.95,
                    "payload": {
                        "doc_id": 1,
                        "page": 1,
                        "source": "paperless_ocr",
                        "text": "first source",
                        "quality_score": 50,
                    },
                },
                {
                    "score": 0.90,
                    "payload": {
                        "doc_id": 2,
                        "page": 2,
                        "source": "paperless_ocr",
                        "text": "second source",
                        "quality_score": 90,
                    },
                },
                {
                    "score": 0.80,
                    "payload": {
                        "doc_id": 3,
                        "page": 3,
                        "source": "paperless_ocr",
                        "text": "third source",
                        "quality_score": 90,
                    },
                },
            ]
        },
    )
    monkeypatch.setattr("app.services.chat._load_prompt", lambda _settings: "{question}\n{sources}\n{history}")
    monkeypatch.setattr("app.services.chat.llm_client.chat_completion", lambda *args, **kwargs: "ok")
    monkeypatch.setattr("app.services.chat.resolve_evidence_matches", lambda *args, **kwargs: [])

    result = answer_question(settings, question="What changed?", top_k=3, min_quality=80)
    assert isinstance(result, dict)
    citation_ids = [item["id"] for item in result["citations"]]
    assert citation_ids == [1, 2]


def test_answer_question_generates_and_echoes_conversation_id(monkeypatch):
    settings = load_settings()
    monkeypatch.setattr("app.services.chat.ensure_text_llm_ready", lambda _settings: None)
    monkeypatch.setattr("app.services.chat.ensure_qdrant_ready", lambda _settings: None)
    monkeypatch.setattr("app.services.chat.embed_text", lambda _settings, _text: [0.1, 0.2])
    monkeypatch.setattr("app.services.chat.search_points", lambda *_args, **_kwargs: {"result": []})
    monkeypatch.setattr("app.services.chat._load_prompt", lambda _settings: "{question}\n{sources}\n{history}")
    monkeypatch.setattr("app.services.chat.llm_client.chat_completion", lambda *args, **kwargs: "ok")
    monkeypatch.setattr("app.services.chat.resolve_evidence_matches", lambda *args, **kwargs: [])

    generated = answer_question(settings, question="What changed?", top_k=3)
    assert isinstance(generated, dict)
    generated_id = generated.get("conversation_id")
    assert isinstance(generated_id, str)
    assert len(generated_id) >= 12

    echoed = answer_question(
        settings,
        question="And after that?",
        top_k=3,
        conversation_id="thread-123",
    )
    assert isinstance(echoed, dict)
    assert echoed["conversation_id"] == "thread-123"


def test_answer_question_limits_history_in_prompt(monkeypatch):
    settings = load_settings()
    monkeypatch.setattr("app.services.chat.ensure_text_llm_ready", lambda _settings: None)
    monkeypatch.setattr("app.services.chat.ensure_qdrant_ready", lambda _settings: None)
    monkeypatch.setattr("app.services.chat.embed_text", lambda _settings, _text: [0.1, 0.2])
    monkeypatch.setattr("app.services.chat.search_points", lambda *_args, **_kwargs: {"result": []})
    monkeypatch.setattr("app.services.chat._load_prompt", lambda _settings: "{question}\n{history}\n{sources}")
    monkeypatch.setattr("app.services.chat.resolve_evidence_matches", lambda *args, **kwargs: [])

    captured = {"prompt": ""}

    def _chat_completion(_settings, model, messages, timeout=120):
        captured["prompt"] = str(messages[0].get("content") or "")
        return "ok"

    monkeypatch.setattr("app.services.chat.llm_client.chat_completion", _chat_completion)

    history = []
    for i in range(MAX_HISTORY_TURNS + 5):
        history.append(
            {
                "question": f"Q{i} " + ("x" * (MAX_HISTORY_CHARS + 100)),
                "answer": f"A{i} " + ("y" * (MAX_HISTORY_CHARS + 100)),
            }
        )
    result = answer_question(settings, question="What changed?", top_k=3, history=history)
    assert isinstance(result, dict)
    prompt = captured["prompt"]
    assert "Q0 " not in prompt
    assert f"Q{MAX_HISTORY_TURNS + 4}" in prompt
    assert ("x" * (MAX_HISTORY_CHARS + 30)) not in prompt
