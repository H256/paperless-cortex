from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.search import vector_store
from app.services.search.embeddings import embed_text

if TYPE_CHECKING:
    from app.config import Settings


def ensure_embedding_collection(settings: Settings) -> None:
    sample_embedding = embed_text(settings, "dimension probe")
    vector_store.ensure_collection(settings, vector_size=len(sample_embedding))
