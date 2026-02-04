from __future__ import annotations

import json
import logging
from typing import Any, Iterable
from pathlib import Path

from fastapi.responses import StreamingResponse

from app.config import Settings
from app.services import llm_client
from app.services.guard import ensure_text_llm_ready, ensure_qdrant_ready
from app.services.embeddings import embed_text, search_points

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "chat.txt"
_prompt_cache: dict[str, str] = {}


def _load_prompt(settings: Settings) -> str:
    prompt_path = DEFAULT_PROMPT_PATH
    key = str(prompt_path)
    if key in _prompt_cache:
        return _prompt_cache[key]
    if not prompt_path.is_file():
        raise RuntimeError(f"Chat prompt file not found: {prompt_path}")
    text = prompt_path.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"Chat prompt file empty: {prompt_path}")
    _prompt_cache[key] = text
    return text


def _build_sources(hits: list[dict[str, Any]], min_quality: int | None) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for idx, hit in enumerate(hits, start=1):
        payload = hit.get("payload") or {}
        quality_score = payload.get("quality_score")
        if quality_score is None:
            quality_score = 100
        if min_quality is not None and quality_score < min_quality:
            continue
        text = str(payload.get("text") or "")
        sources.append(
            {
                "id": idx,
                "doc_id": payload.get("doc_id"),
                "page": payload.get("page"),
                "source": payload.get("source"),
                "bbox": payload.get("bbox"),
                "score": hit.get("score"),
                "quality_score": quality_score,
                "snippet": text[:500],
                "text": text[:1200],
            }
        )
    return sources


def _dedupe_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[object, object, object], dict[str, Any]] = {}
    for item in sources:
        key = (item.get("doc_id"), item.get("page"), item.get("source"))
        current = deduped.get(key)
        if not current:
            deduped[key] = item
            continue
        current_score = float(current.get("score") or 0) * (float(current.get("quality_score") or 100) / 100.0)
        next_score = float(item.get("score") or 0) * (float(item.get("quality_score") or 100) / 100.0)
        if next_score > current_score:
            deduped[key] = item
    return list(deduped.values())


def _format_sources(sources: list[dict[str, Any]]) -> str:
    lines = []
    for source in sources:
        lines.append(
            f"[{source['id']}] doc_id={source.get('doc_id')} page={source.get('page')} "
            f"source={source.get('source')} text={source.get('text')}"
        )
    return "\n".join(lines)

def _format_history(history: list[dict[str, str]] | list[Any]) -> str:
    if not history:
        return "None"
    blocks = []
    for item in history[-6:]:
        if isinstance(item, dict):
            question = (item.get("question") or "").strip()
            answer = (item.get("answer") or "").strip()
        else:
            question = (getattr(item, "question", "") or "").strip()
            answer = (getattr(item, "answer", "") or "").strip()
        if not question and not answer:
            continue
        blocks.append(f"Q: {question}\nA: {answer}".strip())
    return "\n\n".join(blocks) if blocks else "None"


def answer_question(
    settings: Settings,
    question: str,
    top_k: int = 6,
    source: str | None = None,
    min_quality: int | None = None,
    history: list[dict[str, str]] | None = None,
    stream: bool = False,
) -> dict[str, str | list[dict[str, Any]]] | StreamingResponse:
    ensure_text_llm_ready(settings)
    ensure_qdrant_ready(settings)
    vector = embed_text(settings, question)
    raw = search_points(settings, vector, limit=max(3, top_k * 3))
    hits = raw.get("result", []) or []
    if source:
        hits = [hit for hit in hits if (hit.get("payload") or {}).get("source") == source]
    sources = _build_sources(hits, min_quality=min_quality)
    sources = _dedupe_sources(sources)
    sources = sources[:top_k]
    if sources:
        sources_text = _format_sources(sources)
    else:
        sources_text = "No sources available."
    prompt = _load_prompt(settings)
    prompt = (
        prompt.replace("{question}", question.strip())
        .replace("{sources}", sources_text)
        .replace("{history}", _format_history(history or []))
    )
    logger.info("Chat prompt chars=%s sources=%s", len(prompt), len(sources))
    base = llm_client.base_url(settings)
    if not stream:
        answer = llm_client.chat_completion(
            settings,
            base,
            model=settings.text_model or "",
            messages=[{"role": "user", "content": prompt}],
            timeout=120,
        )
        for source in sources:
            source.pop("text", None)
        return {
            "question": question,
            "answer": answer,
            "citations": sources,
        }

    def event_stream() -> Iterable[bytes]:
        answer_chunks: list[str] = []
        for token in llm_client.stream_chat_completion(
            settings,
            base,
            model=settings.text_model or "",
            messages=[{"role": "user", "content": prompt}],
            timeout=None,
        ):
            answer_chunks.append(token)
            payload = json.dumps({"token": token})
            yield f"data: {payload}\n\n".encode("utf-8")
        answer = "".join(answer_chunks).strip()
        for source in sources:
            source.pop("text", None)
        done_payload = json.dumps({"answer": answer, "citations": sources})
        yield f"event: done\ndata: {done_payload}\n\n".encode("utf-8")

    return StreamingResponse(event_stream(), media_type="text/event-stream")
