from __future__ import annotations

from types import SimpleNamespace

from app.services.embeddings import enforce_embedding_chunk_budget, split_text_for_embedding
from app.services.text_cleaning import estimate_tokens


def test_split_text_for_embedding_respects_token_budget():
    text = ("invoice amount due date customer " * 1200).strip()
    chunks = split_text_for_embedding(
        text,
        max_input_tokens=450,
        max_chunk_chars=3000,
        overlap_chars=120,
    )
    assert len(chunks) > 1
    assert all(estimate_tokens(chunk) <= 450 for chunk in chunks)


def test_enforce_embedding_chunk_budget_splits_oversized_chunks():
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
    normalized = enforce_embedding_chunk_budget(settings, chunks)
    assert len(normalized) > 1
    assert all(estimate_tokens(str(chunk["text"])) <= 400 for chunk in normalized)
    assert all(chunk.get("bbox") is None for chunk in normalized)
