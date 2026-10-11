"""Regression tests for source-scoped vector deletion (issue #157).

The real ``embeddings.delete_points_for_doc`` entry point runs end-to-end
against an in-memory fake adapter that implements real filter semantics
(doc_id equality plus stored-source set membership), so the mapping from
normalized embedding sources to stored payload values is exercised on the
delete path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.config import load_settings
from app.services.search import vector_store
from app.services.search.embeddings import delete_points_for_doc, make_point_id

if TYPE_CHECKING:
    from pytest import MonkeyPatch


class _FakeVectorStoreAdapter:
    def __init__(self) -> None:
        self.points: dict[int, dict[str, Any]] = {}

    def provider_name(self) -> str:
        return "fake"

    def display_name(self) -> str:
        return "Fake"

    def ensure_ready(self, settings: Any) -> None:
        return None

    def check_health(self, settings: Any) -> tuple[bool, str]:
        return True, "ok"

    def ensure_collection(
        self, settings: Any, *, vector_size: int, distance: str = "Cosine"
    ) -> None:
        return None

    def upsert_points(self, settings: Any, points: list[dict[str, Any]]) -> None:
        for point in points:
            self.points[int(point["id"])] = point

    def delete_all_chunk_points(self, settings: Any) -> None:
        self.points.clear()

    def delete_points_for_doc(
        self,
        settings: Any,
        *,
        doc_id: int,
        source: str | tuple[str, ...] | None = None,
    ) -> None:
        allowed_sources: set[str] | None = None
        if source is not None:
            allowed_sources = {source} if isinstance(source, str) else set(source)
        for point_id in list(self.points):
            payload = self.points[point_id]["payload"]
            if payload.get("doc_id") != doc_id:
                continue
            if allowed_sources is not None and payload.get("source") not in allowed_sources:
                continue
            del self.points[point_id]

    def delete_similarity_points(self, settings: Any, *, doc_id: int | None = None) -> None:
        return None

    def search_points(
        self,
        settings: Any,
        vector: list[float],
        *,
        limit: int = 5,
        with_payload: bool = True,
        filter_payload: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> dict[str, Any]:
        return {"result": []}

    def retrieve_points(
        self,
        settings: Any,
        ids: list[int],
        *,
        with_vector: bool = True,
        with_payload: bool = True,
    ) -> dict[str, Any]:
        return {"result": []}


def _chunk_point(doc_id: int, chunk: int, stored_source: str) -> dict[str, Any]:
    return {
        "id": make_point_id(doc_id, chunk, stored_source),
        "vector": [0.1, 0.2, 0.3],
        "payload": {
            "doc_id": doc_id,
            "chunk": chunk,
            "source": stored_source,
            "text": f"document {doc_id} chunk {chunk} ({stored_source})",
        },
    }


def _fake_adapter(monkeypatch: MonkeyPatch) -> _FakeVectorStoreAdapter:
    fake = _FakeVectorStoreAdapter()
    monkeypatch.setattr(vector_store, "get_vector_store_adapter", lambda _settings: fake)
    return fake


def test_shrunken_reembed_delete_keeps_fresh_chunks_and_vision(
    monkeypatch: MonkeyPatch,
) -> None:
    fake = _fake_adapter(monkeypatch)
    settings = load_settings()

    vision_point = _chunk_point(7, 0, "vision_ocr")
    fake.upsert_points(
        settings,
        [_chunk_point(7, chunk, "paperless_ocr") for chunk in range(3)],
    )
    fake.upsert_points(settings, [_chunk_point(7, chunk, "pdf_text") for chunk in (3, 4)])
    fake.upsert_points(settings, [vision_point])

    # Production pipeline order: delete stale source-scoped points first,
    # then re-embed and upsert the surviving chunks (see
    # worker_document_tasks.py / sync_operations.py).
    delete_points_for_doc(settings, 7, source="paperless")
    fake.upsert_points(settings, [_chunk_point(7, chunk, "paperless_ocr") for chunk in range(3)])

    fresh_ids = {make_point_id(7, chunk, "paperless_ocr") for chunk in range(3)}
    stale_ids = {make_point_id(7, chunk, "pdf_text") for chunk in (3, 4)}
    vision_id = make_point_id(7, 0, "vision_ocr")
    assert fresh_ids <= set(fake.points)
    assert stale_ids.isdisjoint(fake.points)
    assert fake.points[vision_id]["payload"] == vision_point["payload"]


def test_delete_paperless_source_keeps_vision_points(monkeypatch: MonkeyPatch) -> None:
    fake = _fake_adapter(monkeypatch)
    settings = load_settings()

    paperless_points = [_chunk_point(7, chunk, "paperless_ocr") for chunk in range(3)]
    paperless_points += [_chunk_point(7, chunk, "pdf_text") for chunk in range(3, 5)]
    vision_points = [_chunk_point(7, chunk, "vision_ocr") for chunk in range(3)]
    fake.upsert_points(settings, [*paperless_points, *vision_points])

    delete_points_for_doc(settings, 7, source="paperless")

    paperless_ids = {point["id"] for point in paperless_points}
    vision_ids = {point["id"] for point in vision_points}
    assert paperless_ids.isdisjoint(fake.points)
    assert set(fake.points) == vision_ids


def test_delete_without_source_removes_all_doc_points(monkeypatch: MonkeyPatch) -> None:
    fake = _fake_adapter(monkeypatch)
    settings = load_settings()

    other_doc_point = _chunk_point(8, 0, "paperless_ocr")
    fake.upsert_points(
        settings,
        [
            _chunk_point(7, 0, "paperless_ocr"),
            _chunk_point(7, 1, "pdf_text"),
            _chunk_point(7, 0, "vision_ocr"),
            other_doc_point,
        ],
    )

    delete_points_for_doc(settings, 7)

    assert set(fake.points) == {other_doc_point["id"]}


def test_raw_passthrough_source_deletes_only_matching_points(
    monkeypatch: MonkeyPatch,
) -> None:
    fake = _fake_adapter(monkeypatch)
    settings = load_settings()

    ocr_points = [_chunk_point(7, chunk, "paperless_ocr") for chunk in range(2)]
    text_points = [_chunk_point(7, chunk, "pdf_text") for chunk in range(2)]
    fake.upsert_points(settings, [*ocr_points, *text_points])

    delete_points_for_doc(settings, 7, source="pdf_text")

    assert set(fake.points) == {point["id"] for point in ocr_points}
