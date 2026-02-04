from __future__ import annotations

from app.config import Settings
from app.services.embeddings import embed_text, ensure_qdrant_collection


def ensure_embedding_collection(settings: Settings) -> None:
    sample_embedding = embed_text(settings, "dimension probe")
    ensure_qdrant_collection(settings, vector_size=len(sample_embedding))
