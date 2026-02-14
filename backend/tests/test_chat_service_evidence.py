from __future__ import annotations

from app.config import load_settings
from app.services.chat import answer_question


def test_answer_question_enriches_citations_with_evidence(monkeypatch):
    settings = load_settings()

    monkeypatch.setattr("app.services.chat.ensure_text_llm_ready", lambda _settings: None)
    monkeypatch.setattr("app.services.chat.ensure_qdrant_ready", lambda _settings: None)
    monkeypatch.setattr("app.services.chat.embed_text", lambda _settings, _text: [0.1, 0.2])
    monkeypatch.setattr(
        "app.services.chat.search_points",
        lambda _settings, _vector, limit=18: {
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
    called = {"min_match_ratio": None}

    def _resolver(citations, max_pages=3, min_match_ratio=0.8, settings=None):
        called["min_match_ratio"] = min_match_ratio
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
    assert called["min_match_ratio"] == settings.evidence_min_match_ratio
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
        lambda _settings, _vector, limit=18: {
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

    def _resolver(citations, max_pages=3, min_match_ratio=0.8, settings=None):
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
        lambda _settings, _vector, limit=18: {
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

    def _resolver(citations, max_pages=3, min_match_ratio=0.8, settings=None):
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
