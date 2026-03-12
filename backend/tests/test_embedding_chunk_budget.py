from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import patch

from app.services.documents.text_cleaning import estimate_tokens
from app.services.search.embeddings import (
    embed_text,
    enforce_embedding_chunk_budget,
    split_text_for_embedding,
    summarize_chunk_split_telemetry,
)

if TYPE_CHECKING:
    from app.config import Settings


def test_split_text_for_embedding_respects_token_budget() -> None:
    text = ("invoice amount due date customer " * 1200).strip()
    chunks = split_text_for_embedding(
        text,
        max_input_tokens=450,
        max_chunk_chars=3000,
        overlap_chars=120,
    )
    assert len(chunks) > 1
    assert all(estimate_tokens(chunk) <= 450 for chunk in chunks)


def test_enforce_embedding_chunk_budget_splits_oversized_chunks() -> None:
    settings = SimpleNamespace(
        embedding_max_input_tokens=400,
        chunk_max_chars=2200,
        chunk_overlap=120,
    )
    chunks = [
        {
            "text": ("very long ocr content " * 2500).strip(),
            "page": 2,
            "source": "vision_ocr",
            "quality_score": 80,
            "bbox": [0.1, 0.1, 0.9, 0.9],
        }
    ]
    normalized = enforce_embedding_chunk_budget(cast("Settings", settings), chunks)
    assert len(normalized) > 1
    assert all(estimate_tokens(str(chunk["text"])) <= 400 for chunk in normalized)
    assert all(chunk.get("bbox") is None for chunk in normalized)
    telemetry = summarize_chunk_split_telemetry(normalized)
    assert telemetry["split_chunks"] > 0
    assert telemetry["split_parts"] >= telemetry["split_chunks"]


def test_embed_text_tracks_overflow_fallback_telemetry() -> None:
    settings = SimpleNamespace(
        embedding_model="test-embed",
        embedding_request_timeout_seconds=10,
        llm_base_url=None,
        embedding_max_input_tokens=400,
    )
    text = ("overflow token chunk " * 2000).strip()
    telemetry: dict[str, int] = {}

    def fake_embed(*_args: Any, **kwargs: Any) -> list[float]:
        payload = str(kwargs.get("text") or "")
        if len(payload) > 1800:
            raise RuntimeError(
                "Error code: 400 - {'error': {'type': 'exceed_context_size_error', 'message': 'request exceeds the available context size'}}"
            )
        return [0.1, 0.2, 0.3]

    with (
        patch("app.services.search.embeddings.ensure_embedding_llm_ready", lambda _settings: None),
        patch("app.services.search.embeddings.llm_client.embedding", side_effect=fake_embed),
    ):
        vector = embed_text(cast("Settings", settings), text, telemetry=telemetry)

    assert len(vector) == 3
    assert telemetry["overflow_fallback_calls"] >= 1
    assert telemetry["overflow_fallback_parts"] >= 2
