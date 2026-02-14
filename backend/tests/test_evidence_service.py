from __future__ import annotations

from app.config import load_settings
from app.services.evidence import resolve_evidence_matches


def test_resolve_evidence_vector_lookup_disabled_defaults_to_no_match(monkeypatch):
    monkeypatch.setenv("EVIDENCE_VECTOR_LOOKUP_ENABLED", "0")
    settings = load_settings()

    matches = resolve_evidence_matches(
        [{"doc_id": 1756, "page": 3, "snippet": "valid snippet for matching", "bbox": None}],
        max_pages=3,
        settings=settings,
    )
    assert len(matches) == 1
    assert matches[0]["status"] == "no_match"
    assert matches[0]["bbox"] is None


def test_resolve_evidence_vector_lookup_matches_bbox(monkeypatch):
    monkeypatch.setenv("EVIDENCE_VECTOR_LOOKUP_ENABLED", "1")
    monkeypatch.setenv("EMBEDDING_MODEL", "test-embed")
    monkeypatch.setenv("QDRANT_URL", "http://qdrant.local")
    settings = load_settings()

    monkeypatch.setattr("app.services.embeddings.embed_text", lambda _settings, _text: [0.1, 0.2])
    monkeypatch.setattr(
        "app.services.embeddings.search_points",
        lambda _settings, _vector, limit=25: {
            "result": [
                {
                    "score": 0.87,
                    "payload": {
                        "doc_id": 1756,
                        "page": 3,
                        "source": "vision",
                        "bbox": [10, 20, 50, 80],
                    },
                }
            ]
        },
    )

    matches = resolve_evidence_matches(
        [{"doc_id": 1756, "page": 3, "snippet": "valid snippet for matching", "source": "vision_ocr", "bbox": None}],
        max_pages=3,
        settings=settings,
    )
    assert len(matches) == 1
    assert matches[0]["status"] == "ok"
    assert matches[0]["bbox"] == [10.0, 20.0, 50.0, 80.0]
    assert matches[0]["confidence"] == 0.87
