from __future__ import annotations

import math
import re
import logging
from typing import Any

import httpx

from app.config import Settings
from app.services import llm_client
from app.services import qdrant
from app.services.guard import ensure_embedding_llm_ready
from app.services.page_types import PageText, WordBox
from app.services.text_cleaning import estimate_tokens
from app.services.text_pages import score_text_quality

logger = logging.getLogger(__name__)


_SOURCE_ID_OFFSETS = {
    "paperless": 1,
    "vision": 2,
}


def _normalize_embedding_source(source: str | None) -> str | None:
    if not source:
        return None
    normalized = str(source).strip().lower()
    if normalized in {"paperless", "paperless_ocr"}:
        return "paperless"
    if normalized in {"vision", "vision_ocr"}:
        return "vision"
    return normalized


def make_point_id(doc_id: int, chunk: int, source: str | None = None) -> int:
    normalized_source = _normalize_embedding_source(source)
    source_offset = _SOURCE_ID_OFFSETS.get(normalized_source or "", 0)
    return doc_id * 1_000_000_000 + source_offset * 1_000_000 + chunk


def _is_context_overflow_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "exceed_context_size_error" in message
        or "exceeds the available context size" in message
        or "context size" in message and "exceed" in message
    )


def _average_vectors(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    width = len(vectors[0])
    if width == 0:
        return []
    totals = [0.0] * width
    for vector in vectors:
        if len(vector) != width:
            continue
        for index, value in enumerate(vector):
            totals[index] += float(value)
    denom = float(len(vectors))
    return [value / denom for value in totals]


def split_text_for_embedding(
    text: str,
    *,
    max_input_tokens: int,
    max_chunk_chars: int,
    overlap_chars: int = 0,
) -> list[str]:
    normalized = (text or "").strip()
    if not normalized:
        return []
    if estimate_tokens(normalized) <= max_input_tokens:
        return [normalized]

    token_safe_chars = max(200, int(max_input_tokens * 3.0))
    chunk_chars = max(200, min(max_chunk_chars, token_safe_chars))
    overlap = min(max(0, overlap_chars), max(0, chunk_chars // 4))
    chunks = semantic_chunks(normalized, max_chars=chunk_chars, overlap=overlap)

    final_chunks: list[str] = []
    hard_step = max(1, chunk_chars - overlap)
    for chunk in chunks:
        chunk_text = chunk.strip()
        if not chunk_text:
            continue
        if estimate_tokens(chunk_text) <= max_input_tokens:
            final_chunks.append(chunk_text)
            continue
        start = 0
        while start < len(chunk_text):
            piece = chunk_text[start : start + chunk_chars].strip()
            if piece:
                final_chunks.append(piece)
            if start + chunk_chars >= len(chunk_text):
                break
            start += hard_step
    return final_chunks


def enforce_embedding_chunk_budget(
    settings: Settings,
    chunks: list[dict[str, object]],
) -> list[dict[str, object]]:
    max_tokens = max(256, int(getattr(settings, "embedding_max_input_tokens", 3000)))
    max_chunk_chars = max(200, int(getattr(settings, "chunk_max_chars", 1200)))
    overlap_chars = max(0, int(getattr(settings, "chunk_overlap", 200)))

    normalized: list[dict[str, object]] = []
    expanded_count = 0
    for chunk in chunks:
        text = str(chunk.get("text") or "").strip()
        if not text:
            continue
        parts = split_text_for_embedding(
            text,
            max_input_tokens=max_tokens,
            max_chunk_chars=max_chunk_chars,
            overlap_chars=overlap_chars,
        )
        if len(parts) <= 1:
            normalized_chunk = dict(chunk)
            normalized_chunk["text"] = parts[0] if parts else text
            normalized.append(normalized_chunk)
            continue
        expanded_count += 1
        total_parts = len(parts)
        for index, part in enumerate(parts, start=1):
            normalized_chunk = dict(chunk)
            normalized_chunk["text"] = part
            normalized_chunk["split_part"] = index
            normalized_chunk["split_total"] = total_parts
            # The original bbox no longer maps to a partial split.
            if "bbox" in normalized_chunk:
                normalized_chunk["bbox"] = None
            normalized.append(normalized_chunk)
    if expanded_count:
        logger.warning(
            "Embedding chunk budget expanded oversized chunks=%s total_chunks=%s",
            expanded_count,
            len(normalized),
        )
    return normalized


def embed_text(settings: Settings, text: str) -> list[float]:
    if not settings.embedding_model:
        raise RuntimeError("EMBEDDING_MODEL not set")
    ensure_embedding_llm_ready(settings)
    logger.info("LLM embeddings model=%s chars=%s", settings.embedding_model, len(text))
    try:
        embedding = llm_client.embedding(
            settings,
            model=settings.embedding_model,
            text=text,
            timeout=settings.embedding_request_timeout_seconds,
        )
    except Exception as exc:
        if not _is_context_overflow_error(exc):
            raise
        fallback_tokens = max(256, int(getattr(settings, "embedding_max_input_tokens", 3000)) // 2)
        fallback_parts = split_text_for_embedding(
            text,
            max_input_tokens=fallback_tokens,
            max_chunk_chars=max(200, int(fallback_tokens * 2.5)),
            overlap_chars=0,
        )
        if len(fallback_parts) <= 1:
            raise
        logger.warning(
            "Embedding overflow fallback split parts=%s model=%s chars=%s",
            len(fallback_parts),
            settings.embedding_model,
            len(text),
        )
        vectors = [embed_text(settings, part) for part in fallback_parts]
        embedding = _average_vectors(vectors)
    if settings.llm_base_url and settings.embedding_model:
        if __import__("os").getenv("LLM_DEBUG") == "1":
            sample = embedding[:5]
            logger.info(
                "LLM embed model=%s len=%s sample=%s",
                settings.embedding_model,
                len(embedding),
                sample,
            )
    return embedding


def embed_texts(settings: Settings, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if not settings.embedding_model:
        raise RuntimeError("EMBEDDING_MODEL not set")
    ensure_embedding_llm_ready(settings)
    logger.info(
        "LLM embeddings batch model=%s items=%s total_chars=%s",
        settings.embedding_model,
        len(texts),
        sum(len(t) for t in texts),
    )
    try:
        return llm_client.embedding_many(
            settings,
            model=settings.embedding_model,
            texts=texts,
            timeout=settings.embedding_request_timeout_seconds,
        )
    except Exception as exc:
        logger.warning(
            "Batch embeddings failed; fallback to single requests items=%s error=%s",
            len(texts),
            exc,
        )
        return [embed_text(settings, text) for text in texts]


def semantic_chunks(text: str, max_chars: int = 1200, overlap: int = 200) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if current:
            chunks.append("\n\n".join(current).strip())
            current = []
            current_len = 0

    for para in paragraphs:
        if len(para) > max_chars:
            # split long paragraphs into sentences
            sentences = re.split(r"(?<=[.!?])\s+", para)
        else:
            sentences = [para]
        for sentence in sentences:
            if not sentence:
                continue
            start = 0
            while start < len(sentence):
                piece = sentence[start : start + max_chars] if len(sentence) > max_chars else sentence
                start += max_chars
                if not piece:
                    continue
                if current_len + len(piece) + 2 > max_chars:
                    flush()
                current.append(piece)
                current_len += len(piece) + 2
    flush()

    if overlap > 0 and len(chunks) > 1:
        overlapped: list[str] = []
        for i, chunk in enumerate(chunks):
            if i == 0:
                overlapped.append(chunk)
                continue
            prev_tail = chunks[i - 1][-overlap:]
            overlapped.append(f"{prev_tail}\n{chunk}")
        return overlapped
    return chunks


def sentence_chunks(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if s.strip()]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def semantic_merge_chunks(
    settings: Settings,
    text: str,
    max_chars: int,
    overlap: int,
    similarity_threshold: float,
) -> list[str]:
    sentences = sentence_chunks(text)
    if not sentences:
        return []
    sentence_vectors = [embed_text(settings, s) for s in sentences]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    last_vec: list[float] | None = None

    def flush() -> None:
        nonlocal current, current_len, last_vec
        if current:
            chunks.append(" ".join(current).strip())
            current = []
            current_len = 0
            last_vec = None

    for sentence, vec in zip(sentences, sentence_vectors):
        if not current:
            current.append(sentence)
            current_len = len(sentence)
            last_vec = vec
            continue
        sim = cosine_similarity(last_vec or vec, vec)
        if sim < similarity_threshold or current_len + len(sentence) + 1 > max_chars:
            flush()
            current.append(sentence)
            current_len = len(sentence)
            last_vec = vec
            continue
        current.append(sentence)
        current_len += len(sentence) + 1
        last_vec = vec
    flush()

    if overlap > 0 and len(chunks) > 1:
        overlapped: list[str] = []
        for i, chunk in enumerate(chunks):
            if i == 0:
                overlapped.append(chunk)
                continue
            prev_tail = chunks[i - 1][-overlap:]
            overlapped.append(f"{prev_tail}\n{chunk}")
        return overlapped
    return chunks


def chunk_text(settings: Settings, text: str) -> list[str]:
    mode = settings.chunk_mode.lower()
    if mode == "semantic":
        chunks = semantic_merge_chunks(
            settings,
            text,
            max_chars=settings.chunk_max_chars,
            overlap=settings.chunk_overlap,
            similarity_threshold=settings.chunk_similarity_threshold,
        )
        logger.info(
            "Chunking mode=semantic sentences=%s chunks=%s",
            len(sentence_chunks(text)),
            len(chunks),
        )
        return chunks
    chunks = semantic_chunks(text, max_chars=settings.chunk_max_chars, overlap=settings.chunk_overlap)
    logger.info("Chunking mode=heuristic chunks=%s", len(chunks))
    return chunks


def _chunk_word_boxes(
    settings: Settings,
    words: list[WordBox],
) -> list[dict[str, object]]:
    if not words:
        return []
    chunks: list[list[WordBox]] = []
    current: list[WordBox] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if current:
            chunks.append(current)
            current = []
            current_len = 0

    for word in words:
        add_len = len(word.text) + (1 if current else 0)
        if current and current_len + add_len > settings.chunk_max_chars:
            flush()
            if settings.chunk_overlap > 0 and chunks:
                tail: list[WordBox] = []
                tail_len = 0
                for prev_word in reversed(chunks[-1]):
                    tail_len += len(prev_word.text) + (1 if tail else 0)
                    tail.insert(0, prev_word)
                    if tail_len >= settings.chunk_overlap:
                        break
                current = tail
                current_len = sum(len(w.text) for w in current) + max(0, len(current) - 1)
        current.append(word)
        current_len += add_len
    flush()

    results: list[dict[str, object]] = []
    for group in chunks:
        if not group:
            continue
        text = " ".join(w.text for w in group).strip()
        if not text:
            continue
        x0 = min(w.bbox[0] for w in group)
        y0 = min(w.bbox[1] for w in group)
        x1 = max(w.bbox[2] for w in group)
        y1 = max(w.bbox[3] for w in group)
        results.append({"text": text, "bbox": [x0, y0, x1, y1]})
    return results


def chunk_document_with_pages(
    settings: Settings,
    content: str,
    pages: list[PageText] | None = None,
) -> list[dict[str, object]]:
    if pages:
        chunks: list[dict[str, object]] = []
        for page in pages:
            quality = score_text_quality(page.text, settings)
            if not page.text:
                continue
            words = getattr(page, "words", None)
            if words:
                for chunk in _chunk_word_boxes(settings, words):
                    chunks.append(
                        {
                            "text": chunk["text"],
                            "page": page.page,
                            "source": page.source,
                            "quality_score": quality.score,
                            "bbox": chunk.get("bbox"),
                        }
                    )
            else:
                for chunk in chunk_text(settings, page.text):
                    chunks.append(
                        {
                            "text": chunk,
                            "page": page.page,
                            "source": page.source,
                            "quality_score": quality.score,
                        }
                    )
        return chunks
    quality = score_text_quality(content, settings)
    return [
        {
            "text": chunk,
            "page": None,
            "source": "paperless_ocr",
            "quality_score": quality.score,
        }
        for chunk in chunk_text(settings, content)
    ]


def ensure_qdrant_collection(
    settings: Settings, vector_size: int, distance: str = "Cosine"
) -> None:
    base = qdrant.base_url(settings)
    collection = qdrant.collection_name(settings)
    headers = qdrant.headers(settings)
    with qdrant.client(settings, timeout=30) as client:
        resp = client.get(f"{base}/collections/{collection}", headers=headers)
        if resp.status_code == 200:
            info = resp.json()
            config = info.get("result", {}).get("config", {}).get("params", {}).get("vectors", {})
            size = config.get("size")
            if size and int(size) != vector_size:
                raise RuntimeError(
                    f"Qdrant collection '{collection}' has size {size}, "
                    f"but embedding size is {vector_size}. Delete or use a new collection."
                )
            return
        if resp.status_code != 404:
            resp.raise_for_status()
        create_payload = {"vectors": {"size": vector_size, "distance": distance}}
        create = client.put(
            f"{base}/collections/{collection}",
            headers=headers,
            json=create_payload,
        )
        create.raise_for_status()


def _chunk_points_by_size(points: list[dict[str, Any]], max_bytes: int) -> list[list[dict[str, Any]]]:
    if not points:
        return []
    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_size = 0
    for point in points:
        point_json = __import__("json").dumps(point, ensure_ascii=False)
        point_size = len(point_json.encode("utf-8"))
        if current and current_size + point_size > max_bytes:
            batches.append(current)
            current = []
            current_size = 0
        current.append(point)
        current_size += point_size
    if current:
        batches.append(current)
    return batches


def upsert_points(settings: Settings, points: list[dict[str, Any]]) -> None:
    base = qdrant.base_url(settings)
    collection = qdrant.collection_name(settings)
    headers = qdrant.headers(settings)
    logger.info("Qdrant upsert points=%s", len(points))
    with qdrant.client(settings, timeout=60) as client:
        # Qdrant payload limit is 32MB; keep chunks below ~30MB to be safe.
        batches = _chunk_points_by_size(points, max_bytes=30 * 1024 * 1024)
        for batch in batches:
            response = client.put(
                f"{base}/collections/{collection}/points",
                headers=headers,
                json={"points": batch},
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                detail = response.text[:500]
                raise RuntimeError(f"Qdrant upsert failed: {detail}") from exc
    logger.info("Qdrant upsert ok")


def delete_points_for_doc(settings: Settings, doc_id: int, source: str | None = None) -> None:
    base = qdrant.base_url(settings)
    collection = qdrant.collection_name(settings)
    headers = qdrant.headers(settings)
    must_filters: list[dict[str, object]] = [{"key": "doc_id", "match": {"value": doc_id}}]
    normalized_source = _normalize_embedding_source(source)
    if normalized_source:
        must_filters.append({"key": "source", "match": {"value": normalized_source}})
    payload = {"filter": {"must": must_filters}}
    with qdrant.client(settings, timeout=30) as client:
        response = client.post(
            f"{base}/collections/{collection}/points/delete",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()


def search_points(settings: Settings, vector: list[float], limit: int = 5) -> dict[str, Any]:
    return qdrant.search(settings, vector, limit=limit, with_payload=True)
