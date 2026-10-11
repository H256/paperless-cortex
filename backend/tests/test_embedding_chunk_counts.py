from __future__ import annotations

from app.models import DocumentEmbedding
from app.services.search.embeddings import (
    parse_chunk_counts,
    per_source_counts,
    record_source_chunk_count,
)


def test_parse_chunk_counts_returns_empty_for_missing_or_malformed() -> None:
    assert parse_chunk_counts(None) == {}
    assert parse_chunk_counts("") == {}
    assert parse_chunk_counts("not-json") == {}
    assert parse_chunk_counts("[1, 2]") == {}
    assert parse_chunk_counts('{"vision": "x"}') == {}


def test_parse_chunk_counts_filters_non_positive_counts() -> None:
    assert parse_chunk_counts('{"vision": 3, "paperless": 0, "bad": "5"}') == {
        "vision": 3,
        "bad": 5,
    }


def test_record_source_chunk_count_records_and_sums() -> None:
    row = DocumentEmbedding(doc_id=1)
    record_source_chunk_count(row, source="vision", count=4)
    assert row.chunk_count == 4
    assert parse_chunk_counts(row.chunk_counts_json) == {"vision": 4}
    record_source_chunk_count(row, source="paperless", count=2)
    assert row.chunk_count == 6
    assert parse_chunk_counts(row.chunk_counts_json) == {"vision": 4, "paperless": 2}


def test_record_source_chunk_count_seeds_legacy_both() -> None:
    row = DocumentEmbedding(doc_id=1, embedding_source="both", chunk_count=8)
    record_source_chunk_count(
        row, source="vision", count=5, both=True, previous_total=8
    )
    counts = parse_chunk_counts(row.chunk_counts_json)
    assert counts["vision"] == 5
    assert counts["paperless"] == 8
    assert row.chunk_count == 13


def test_per_source_counts_prefers_blob_over_legacy() -> None:
    row = DocumentEmbedding(doc_id=1, embedding_source="both", chunk_count=4)
    row.chunk_counts_json = '{"vision": 4, "paperless": 2}'
    assert per_source_counts(row, source_hint="both") == {"vision": 4, "paperless": 2}


def test_per_source_counts_falls_back_to_legacy_single_count() -> None:
    row = DocumentEmbedding(doc_id=1, embedding_source="both", chunk_count=4)
    assert per_source_counts(row, source_hint="both") == {"vision": 4, "paperless": 4}
    assert per_source_counts(row, source_hint="vision") == {"vision": 4}
