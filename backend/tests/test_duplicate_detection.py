from __future__ import annotations

import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import load_settings
from app.models import Document, DocumentDuplicatePair
from app.services.documents import duplicates as dup
from app.services.documents.duplicate_scoring import (
    LEVEL_CHECK,
    LEVEL_VERY_LIKELY,
    cluster_pairs,
    extract_amounts,
    fingerprint_from_text,
    normalize_text,
    score_pair,
    shingle_set,
)

INVOICE = (
    "Rechnung Nr. RE-2026-001234 der Muster GmbH vom 12.03.2026. "
    "Gesamtbetrag 1.234,56 EUR inkl. 19% MwSt. Bitte überweisen Sie den Betrag "
    "innerhalb von 14 Tagen auf das angegebene Konto. Vielen Dank für Ihren Auftrag."
)
# Print-and-rescan: typical OCR damage (l/1, rn/m, dropped chars), same content.
INVOICE_SCAN = (
    "Rechnung Nr. RE-2026-001234 der Muster GmbH vom 12.03.2O26. "
    "Gesamtbetrag 1.234,56 EUR inkl. 19% MwSt. Bitte uberweisen Sie den Betrag "
    "innerha1b von 14 Tagen auf das angegebene Konto. Vielen Dank fur lhren Auftrag."
)
INVOICE_OTHER_NUMBER = INVOICE.replace("RE-2026-001234", "RE-2026-009999").replace(
    "1.234,56", "88,10"
)


def test_normalize_text_folds_case_accents_and_punctuation() -> None:
    assert normalize_text("  Größe: Ärger-Straße! ") == "grosse arger strasse"


def test_extract_amounts_normalizes_thousands_separator() -> None:
    assert extract_amounts("Summe 1.234,56 EUR und 7,00 EUR") == {"1234,56", "7,00"}


def test_shingle_set_empty_for_short_text() -> None:
    assert shingle_set("zu kurz") == frozenset()


def test_scan_vs_download_scores_very_likely() -> None:
    left = fingerprint_from_text(1, INVOICE, correspondent_id=5, page_count=1)
    right = fingerprint_from_text(2, INVOICE_SCAN, correspondent_id=5, page_count=1)
    result = score_pair(left, right, embedding_score=0.97)
    assert result.level == LEVEL_VERY_LIKELY
    assert result.text_score is not None and result.text_score > 0.6
    assert result.signals["key_conflict"] is False


def test_series_letter_with_other_numbers_is_capped_to_check() -> None:
    left = fingerprint_from_text(1, INVOICE, correspondent_id=5, page_count=1)
    right = fingerprint_from_text(2, INVOICE_OTHER_NUMBER, correspondent_id=5, page_count=1)
    result = score_pair(left, right, embedding_score=0.99)
    assert result.signals["key_conflict"] is True
    assert result.score <= 0.74
    assert result.level == LEVEL_CHECK


def test_score_without_text_uses_remaining_signals() -> None:
    left = fingerprint_from_text(1, None, correspondent_id=5)
    right = fingerprint_from_text(2, None, correspondent_id=5)
    result = score_pair(left, right, embedding_score=0.95)
    assert result.text_score is None
    assert result.score > 0.9


def test_cluster_pairs_connects_transitively_and_drops_singletons() -> None:
    assert cluster_pairs([(1, 2), (2, 3), (10, 11)]) == [[1, 2, 3], [10, 11]]
    assert cluster_pairs([]) == []


def _session() -> Session:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    return Session(engine)


def _seed_docs(db: Session) -> None:
    db.add_all(
        [
            Document(id=1, title="Rechnung A", content=INVOICE, correspondent_id=None),
            Document(id=2, title="Rechnung A (Scan)", content=INVOICE_SCAN),
            Document(id=3, title="Rechnung B", content=INVOICE_OTHER_NUMBER),
            Document(id=4, title="Anderes", content="Völlig anderer Inhalt " * 10),
        ]
    )
    db.commit()


def test_scan_stores_pairs_and_keeps_ignored(api_client: Any, monkeypatch: Any) -> None:
    with _session() as db:
        _seed_docs(db)
        monkeypatch.setattr(dup, "fetch_doc_point_vector", lambda _s, _d: [0.1, 0.2])
        monkeypatch.setattr(
            dup,
            "search_similar_doc_points",
            lambda _s, _v, **_k: [
                {"doc_id": 1, "score": 1.0},
                {"doc_id": 2, "score": 0.97},
                {"doc_id": 3, "score": 0.93},
            ],
        )
        settings = load_settings()
        stored = dup.scan_document_duplicates(
            settings, db, 1, is_cancel_requested_fn=lambda _s: False
        )
        assert stored == 2
        pair = db.get(DocumentDuplicatePair, (1, 2))
        assert pair is not None and pair.level == LEVEL_VERY_LIKELY and pair.ignored is False

        assert dup.set_pair_ignored(db, 2, 1, ignored=True) is True
        assert dup.set_pair_ignored(db, 8, 9, ignored=True) is False

        # Rescan: ignored flag survives, pair (1,3) vanishes once no longer a candidate.
        monkeypatch.setattr(
            dup,
            "search_similar_doc_points",
            lambda _s, _v, **_k: [{"doc_id": 2, "score": 0.97}],
        )
        dup.scan_document_duplicates(settings, db, 1, is_cancel_requested_fn=lambda _s: False)
        db.expire_all()
        assert db.get(DocumentDuplicatePair, (1, 2)).ignored is True  # type: ignore[union-attr]
        assert db.get(DocumentDuplicatePair, (1, 3)) is None

        assert dup.list_duplicate_groups(db)["total"] == 0
        ignored = dup.list_ignored_pairs(db)
        assert ignored["total"] == 1
        assert dup.set_pair_ignored(db, 1, 2, ignored=False) is True
        groups = dup.list_duplicate_groups(db)
        assert groups["total"] == 1
        assert groups["groups"][0]["doc_ids"] == [1, 2]


def test_scan_aborts_on_cancel(api_client: Any) -> None:
    with _session() as db:
        _seed_docs(db)
        assert (
            dup.scan_document_duplicates(
                load_settings(), db, 1, is_cancel_requested_fn=lambda _s: True
            )
            == 0
        )


def test_duplicate_routes_roundtrip(api_client: Any, monkeypatch: Any) -> None:
    with _session() as db:
        _seed_docs(db)
        db.add(
            DocumentDuplicatePair(
                doc_a_id=1, doc_b_id=2, score=0.95, level="very_likely", ignored=False
            )
        )
        db.commit()

    groups = api_client.get("/duplicates/groups").json()
    assert groups["total"] == 1
    assert groups["groups"][0]["level"] == "very_likely"

    assert api_client.get("/duplicates/groups?min_level=bogus").status_code == 422

    body = {"doc_a_id": 2, "doc_b_id": 1}
    assert api_client.post("/duplicates/ignore", json=body).json()["ignored"] is True
    assert api_client.get("/duplicates/groups").json()["total"] == 0
    assert api_client.get("/duplicates/ignored").json()["total"] == 1
    assert api_client.post("/duplicates/unignore", json=body).json()["ignored"] is False
    assert api_client.get("/duplicates/groups").json()["total"] == 1
    assert (
        api_client.post("/duplicates/ignore", json={"doc_a_id": 8, "doc_b_id": 9}).status_code
        == 404
    )


def test_scan_route_enqueues_one_task_per_document(api_client: Any, monkeypatch: Any) -> None:
    from app.routes import duplicates as routes

    with _session() as db:
        _seed_docs(db)
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(routes, "is_queue_enabled", lambda _s: True)
    monkeypatch.setattr(
        routes, "enqueue_task_sequence", lambda _s, tasks: captured.extend(tasks) or len(tasks)
    )
    payload = api_client.post("/duplicates/scan").json()
    assert payload == {"queued": True, "docs": 4, "enqueued": 4}
    assert {t["task"] for t in captured} == {"duplicate_scan"}


def test_dispatch_routes_duplicate_scan_task() -> None:
    from app.services.pipeline.worker_dispatch import build_dispatch_handler

    calls: list[int] = []
    noop = lambda *_a, **_k: None  # noqa: E731
    handler = build_dispatch_handler(
        settings=object(),
        db=None,  # type: ignore[arg-type]
        task_type="duplicate_scan",
        doc_id=7,
        task=None,
        run_id=None,
        process_sync_only_fn=noop,
        process_evidence_index_fn=noop,
        process_embeddings_paperless_fn=noop,
        process_embeddings_vision_fn=noop,
        process_similarity_index_fn=noop,
        process_cleanup_texts_fn=noop,
        process_page_notes_fn=noop,
        process_summary_hierarchical_fn=noop,
        process_suggestions_paperless_fn=noop,
        process_suggestions_vision_fn=noop,
        process_suggest_field_fn=noop,
        process_duplicate_scan_fn=lambda _s, _d, doc_id: calls.append(doc_id),
    )
    assert handler is not None
    handler()
    assert calls == [7]
