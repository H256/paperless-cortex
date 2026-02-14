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


def test_resolve_evidence_caches_duplicate_lookup(monkeypatch):
    monkeypatch.setenv("EVIDENCE_VECTOR_LOOKUP_ENABLED", "1")
    monkeypatch.setenv("EMBEDDING_MODEL", "test-embed")
    monkeypatch.setenv("QDRANT_URL", "http://qdrant.local")
    settings = load_settings()

    calls = {"embed": 0, "search": 0}

    def _embed(_settings, _text):
        calls["embed"] += 1
        return [0.1, 0.2]

    def _search(_settings, _vector, limit=25):
        calls["search"] += 1
        return {
            "result": [
                {
                    "score": 0.8,
                    "payload": {"doc_id": 1756, "page": 5, "source": "paperless", "bbox": [1, 2, 3, 4]},
                }
            ]
        }

    monkeypatch.setattr("app.services.embeddings.embed_text", _embed)
    monkeypatch.setattr("app.services.embeddings.search_points", _search)

    matches = resolve_evidence_matches(
        [
            {"doc_id": 1756, "page": 5, "snippet": "same snippet", "source": "paperless_ocr", "bbox": None},
            {"doc_id": 1756, "page": 5, "snippet": "same snippet", "source": "paperless_ocr", "bbox": None},
        ],
        max_pages=3,
        settings=settings,
    )
    assert len(matches) == 2
    assert calls["embed"] == 1
    assert calls["search"] == 1


def test_resolve_evidence_respects_min_match_ratio(monkeypatch):
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
                    "score": 0.55,
                    "payload": {"doc_id": 1756, "page": 6, "source": "vision", "bbox": [1, 2, 3, 4]},
                }
            ]
        },
    )

    matches = resolve_evidence_matches(
        [{"doc_id": 1756, "page": 6, "snippet": "weak hit", "source": "vision_ocr", "bbox": None}],
        max_pages=3,
        min_match_ratio=0.8,
        settings=settings,
    )
    assert len(matches) == 1
    assert matches[0]["status"] == "no_match"
    assert matches[0]["bbox"] is None
