from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, cast

from app.services.search.vector_backends import qdrant_adapter

if TYPE_CHECKING:
    from app.config import Settings


class VectorStoreAdapter(Protocol):
    def provider_name(self) -> str: ...

    def display_name(self) -> str: ...

    def ensure_ready(self, settings: Settings) -> None: ...

    def check_health(self, settings: Settings) -> tuple[bool, str]: ...

    def ensure_collection(
        self, settings: Settings, *, vector_size: int, distance: str = "Cosine"
    ) -> None: ...

    def upsert_points(self, settings: Settings, points: list[dict[str, Any]]) -> None: ...

    def delete_points_for_doc(
        self, settings: Settings, *, doc_id: int, source: str | None = None
    ) -> None: ...

    def delete_similarity_points(self, settings: Settings, *, doc_id: int | None = None) -> None: ...

    def search_points(
        self,
        settings: Settings,
        vector: list[float],
        *,
        limit: int = 5,
        with_payload: bool = True,
        filter_payload: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> dict[str, Any]: ...

    def retrieve_points(
        self,
        settings: Settings,
        ids: list[int],
        *,
        with_vector: bool = True,
        with_payload: bool = True,
    ) -> dict[str, Any]: ...


def get_vector_store_adapter(settings: Settings) -> VectorStoreAdapter:
    provider = str(settings.vector_store.provider or "qdrant").strip().lower()
    if provider == "qdrant":
        return cast("VectorStoreAdapter", qdrant_adapter)
    raise RuntimeError(f"Unsupported vector store provider: {provider}")


def provider_name(settings: Settings) -> str:
    return get_vector_store_adapter(settings).provider_name()


def display_name(settings: Settings) -> str:
    return get_vector_store_adapter(settings).display_name()


def ensure_ready(settings: Settings) -> None:
    get_vector_store_adapter(settings).ensure_ready(settings)


def check_health(settings: Settings) -> tuple[bool, str]:
    return get_vector_store_adapter(settings).check_health(settings)


def ensure_collection(settings: Settings, *, vector_size: int, distance: str = "Cosine") -> None:
    get_vector_store_adapter(settings).ensure_collection(
        settings, vector_size=vector_size, distance=distance
    )


def upsert_points(settings: Settings, points: list[dict[str, Any]]) -> None:
    get_vector_store_adapter(settings).upsert_points(settings, points)


def delete_points_for_doc(settings: Settings, *, doc_id: int, source: str | None = None) -> None:
    get_vector_store_adapter(settings).delete_points_for_doc(
        settings, doc_id=doc_id, source=source
    )


def delete_similarity_points(settings: Settings, *, doc_id: int | None = None) -> None:
    get_vector_store_adapter(settings).delete_similarity_points(settings, doc_id=doc_id)


def search_points(
    settings: Settings,
    vector: list[float],
    *,
    limit: int = 5,
    with_payload: bool = True,
    filter_payload: dict[str, Any] | None = None,
    score_threshold: float | None = None,
) -> dict[str, Any]:
    return get_vector_store_adapter(settings).search_points(
        settings,
        vector,
        limit=limit,
        with_payload=with_payload,
        filter_payload=filter_payload,
        score_threshold=score_threshold,
    )


def retrieve_points(
    settings: Settings,
    ids: list[int],
    *,
    with_vector: bool = True,
    with_payload: bool = True,
) -> dict[str, Any]:
    return get_vector_store_adapter(settings).retrieve_points(
        settings,
        ids,
        with_vector=with_vector,
        with_payload=with_payload,
    )
