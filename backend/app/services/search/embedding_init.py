from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from app.services.search import vector_store
from app.services.search.embeddings import embed_text

if TYPE_CHECKING:
    from app.config import Settings

# Process-wide cache of probed embedding dimensions, keyed by
# (provider, collection, model). Only used on the path where the collection
# must be created (no stored dimension to read back), so a re-index of N docs
# performs at most one LLM dimension probe instead of N.
_PROBE_LOCK = threading.Lock()
_PROBED_DIMENSIONS: dict[tuple[str, str, str], int] = {}


def _dimension_key(settings: Settings) -> tuple[str, str, str]:
    return (
        str(settings.vector_store.provider),
        str(settings.vector_store.collection),
        str(settings.embedding_model),
    )


def _probe_dimension(settings: Settings) -> int:
    key = _dimension_key(settings)
    with _PROBE_LOCK:
        cached = _PROBED_DIMENSIONS.get(key)
        if cached is not None:
            return cached
    probe = len(embed_text(settings, "dimension probe"))
    with _PROBE_LOCK:
        _PROBED_DIMENSIONS[key] = probe
    return probe


def ensure_embedding_collection(settings: Settings) -> None:
    stored = vector_store.collection_vector_size(settings)
    vector_size = stored if stored is not None else _probe_dimension(settings)
    vector_store.ensure_collection(settings, vector_size=vector_size)
