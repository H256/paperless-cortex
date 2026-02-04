from __future__ import annotations

import math
import re
import logging
from typing import Any

import httpx

from app.config import Settings
from app.services import ollama
from app.services.page_types import PageText, WordBox
from app.services.text_pages import score_text_quality

logger = logging.getLogger(__name__)


def make_point_id(doc_id: int, chunk: int) -> int:
    return doc_id * 1_000_000 + chunk


def embed_text(settings: Settings, text: str) -> list[float]:
    if not settings.ollama_base_url:
        raise RuntimeError("OLLAMA_BASE_URL not set")
    if not settings.embedding_model:
        raise RuntimeError("EMBEDDING_MODEL not set")
    ollama.ensure_model(settings, settings.embedding_model)
    base = ollama.base_url(settings)
    logger.info("Ollama embeddings model=%s chars=%s", settings.embedding_model, len(text))
    with ollama.client(settings, timeout=60) as http:
        response = http.post(
            f"{base}/api/embeddings",
            json={"model": settings.embedding_model, "prompt": text},
        )
        response.raise_for_status()
        payload = response.json()
        embedding = payload.get("embedding")
        if not isinstance(embedding, list):
            raise RuntimeError("Invalid embedding response")
        if settings.ollama_base_url and settings.embedding_model:
            if __import__("os").getenv("OLLAMA_DEBUG") == "1":
                sample = embedding[:5]
                logger.info(
                    "Ollama embed model=%s len=%s sample=%s",
                    settings.embedding_model,
                    len(embedding),
                    sample,
                )
        return embedding


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
            if current_len + len(sentence) + 2 > max_chars:
                flush()
            current.append(sentence)
            current_len += len(sentence) + 2
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
    if not settings.qdrant_url:
        raise RuntimeError("QDRANT_URL not set")
    if not settings.qdrant_collection:
        raise RuntimeError("QDRANT_COLLECTION not set")
    base = settings.qdrant_url.rstrip("/")
    headers: dict[str, str] = {}
    if settings.qdrant_api_key:
        headers["api-key"] = settings.qdrant_api_key
    with httpx.Client(timeout=30, verify=settings.httpx_verify_tls) as client:
        resp = client.get(f"{base}/collections/{settings.qdrant_collection}", headers=headers)
        if resp.status_code == 200:
            info = resp.json()
            config = info.get("result", {}).get("config", {}).get("params", {}).get("vectors", {})
            size = config.get("size")
            if size and int(size) != vector_size:
                raise RuntimeError(
                    f"Qdrant collection '{settings.qdrant_collection}' has size {size}, "
                    f"but embedding size is {vector_size}. Delete or use a new collection."
                )
            return
        if resp.status_code != 404:
            resp.raise_for_status()
        create_payload = {"vectors": {"size": vector_size, "distance": distance}}
        create = client.put(
            f"{base}/collections/{settings.qdrant_collection}",
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
    if not settings.qdrant_url or not settings.qdrant_collection:
        raise RuntimeError("QDRANT_URL/QDRANT_COLLECTION not set")
    base = settings.qdrant_url.rstrip("/")
    headers: dict[str, str] = {}
    if settings.qdrant_api_key:
        headers["api-key"] = settings.qdrant_api_key
    logger.info("Qdrant upsert points=%s", len(points))
    with httpx.Client(timeout=60, verify=settings.httpx_verify_tls) as client:
        # Qdrant payload limit is 32MB; keep chunks below ~30MB to be safe.
        batches = _chunk_points_by_size(points, max_bytes=30 * 1024 * 1024)
        for batch in batches:
            response = client.put(
                f"{base}/collections/{settings.qdrant_collection}/points",
                headers=headers,
                json={"points": batch},
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                detail = response.text[:500]
                raise RuntimeError(f"Qdrant upsert failed: {detail}") from exc
    logger.info("Qdrant upsert ok")


def delete_points_for_doc(settings: Settings, doc_id: int) -> None:
    if not settings.qdrant_url or not settings.qdrant_collection:
        raise RuntimeError("QDRANT_URL/QDRANT_COLLECTION not set")
    base = settings.qdrant_url.rstrip("/")
    headers: dict[str, str] = {}
    if settings.qdrant_api_key:
        headers["api-key"] = settings.qdrant_api_key
    payload = {"filter": {"must": [{"key": "doc_id", "match": {"value": doc_id}}]}}
    with httpx.Client(timeout=30, verify=settings.httpx_verify_tls) as client:
        response = client.post(
            f"{base}/collections/{settings.qdrant_collection}/points/delete",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()


def search_points(settings: Settings, vector: list[float], limit: int = 5) -> dict[str, Any]:
    if not settings.qdrant_url or not settings.qdrant_collection:
        raise RuntimeError("QDRANT_URL/QDRANT_COLLECTION not set")
    base = settings.qdrant_url.rstrip("/")
    headers: dict[str, str] = {}
    if settings.qdrant_api_key:
        headers["api-key"] = settings.qdrant_api_key
    with httpx.Client(timeout=30, verify=settings.httpx_verify_tls) as client:
        response = client.post(
            f"{base}/collections/{settings.qdrant_collection}/points/search",
            headers=headers,
            json={"vector": vector, "limit": limit, "with_payload": True},
        )
        response.raise_for_status()
        return response.json()
