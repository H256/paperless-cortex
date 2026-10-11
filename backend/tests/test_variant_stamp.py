from __future__ import annotations

import json
import os
from types import SimpleNamespace
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Document, DocumentSuggestion
from app.services.ai.suggestion_operations import generate_field_variants_payload


def _queue_variant_request(db: Any, doc_id: int) -> dict[str, object]:
    return generate_field_variants_payload(
        doc_id=doc_id,
        source="paperless_ocr",
        field="title",
        count=1,
        priority=False,
        settings=SimpleNamespace(queue_enabled=True, enable_vision_ocr=False),  # type: ignore[arg-type]
        db=db,
        get_document_fn=lambda _s, did: {"id": did, "content": "text"},
        get_cached_tags_fn=lambda _s: [],
        get_cached_correspondents_fn=lambda _s: [],
        get_document_or_none_fn=lambda _db, _id: None,
        get_page_text_layers_fn=lambda *_a, **_k: ([], []),
        fetch_pdf_bytes_fn=lambda: b"",
        upsert_page_texts_fn=lambda *_a, **_k: None,
        ensure_document_ocr_score_fn=lambda *_a, **_k: None,
        generate_field_variants_fn=lambda *_a, **_k: {"variants": []},
        enqueue_task_front_fn=lambda _s, _task: 1,
    )


def test_queued_request_returns_the_stamp_of_the_existing_batch(session_factory: Any) -> None:
    with session_factory() as db:
        db.add(Document(id=901, title="d", content="text"))
        db.add(
            DocumentSuggestion(
                doc_id=901,
                source="pvar:title",
                payload=json.dumps({"variants": ["Old"]}),
                processed_at="2026-10-11T10:00:00+00:00",
            )
        )
        db.commit()

        result = _queue_variant_request(db, 901)

    assert result["queued"] is True
    assert result["updated_at"] == "2026-10-11T10:00:00+00:00"


def test_queued_request_without_a_batch_has_no_stamp(session_factory: Any) -> None:
    with session_factory() as db:
        db.add(Document(id=902, title="d", content="text"))
        db.commit()

        result = _queue_variant_request(db, 902)

    assert result["updated_at"] is None


def test_variants_endpoint_exposes_the_stamp(api_client: Any) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=903, title="d", content="text"))
        db.add(
            DocumentSuggestion(
                doc_id=903,
                source="pvar:title",
                payload=json.dumps({"variants": ["A", "B"]}),
                processed_at="2026-10-11T11:00:00+00:00",
            )
        )
        db.commit()

    response = api_client.get(
        "/documents/903/suggestions/field/variants",
        params={"source": "paperless_ocr", "field": "title"},
    )

    assert response.status_code == 200
    assert response.json()["variants"] == ["A", "B"]
    assert response.json()["updated_at"] == "2026-10-11T11:00:00+00:00"
    missing = api_client.get(
        "/documents/903/suggestions/field/variants",
        params={"source": "vision_ocr", "field": "title"},
    ).json()
    assert missing["variants"] == []
    assert missing["updated_at"] is None
