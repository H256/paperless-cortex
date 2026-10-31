from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from app.services.search import vector_store
from app.services.search.embeddings import embed_text

if TYPE_CHECKING:
    from app.config import Settings

# Process-wide cache of probed embedding dimensions, keyed by
# (provider, collection, model). A re-index of N docs performs at most one
# LLM dimension probe per model instead of N. The probed size is passed to
# ensure_collection, so a changed embedding model still fails fast with the
# store's dimension-mismatch error. If the LLM endpoint is down, the probe
# falls back to the stored collection size so embedding work proceeds when the
# collection already exists.
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
    try:
        vector_size = _probe_dimension(settings)
    except Exception:
        # LLM endpoint down/rate-limited: fall back to the stored collection
        # size so embedding work proceeds when the collection already exists.
        stored = vector_store.collection_vector_size(settings)
        if stored is None:
            # Collection absent and LLM down: nothing to fall back to, so the
            # original probe error propagates.
            raise
        vector_size = stored
    vector_store.ensure_collection(settings, vector_size=vector_size)
