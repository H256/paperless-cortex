from __future__ import annotations

import json
import logging
from typing import Any, Iterable
from pathlib import Path
from uuid import uuid4
from datetime import datetime
from sqlalchemy.orm import Session

from fastapi.responses import StreamingResponse

from app.config import Settings
from app.models import Document
from app.services import llm_client
from app.services.guard import ensure_text_llm_ready, ensure_qdrant_ready
from app.services.embeddings import embed_text, search_points
from app.services.evidence import resolve_evidence_matches
from app.services.json_utils import parse_json_object
from app.services.string_list_json import parse_string_list_json

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "chat.txt"
CHRONO_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "chat_chrono.txt"
FOLLOWUPS_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "chat_followups.txt"
_prompt_cache: dict[str, str] = {}
MAX_HISTORY_TURNS = 12
MAX_HISTORY_CHARS = 1600


def _load_prompt_from(path: Path) -> str:
    key = str(path)
    if key in _prompt_cache:
        return _prompt_cache[key]
    if not path.is_file():
        raise RuntimeError(f"Chat prompt file not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"Chat prompt file empty: {path}")
    _prompt_cache[key] = text
    return text


def _load_prompt(settings: Settings) -> str:
    return _load_prompt_from(DEFAULT_PROMPT_PATH)


def _load_chrono_prompt(settings: Settings) -> str:
    return _load_prompt_from(CHRONO_PROMPT_PATH)


def _load_followups_prompt(settings: Settings) -> str:
    return _load_prompt_from(FOLLOWUPS_PROMPT_PATH)


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


def _renumber_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for idx, item in enumerate(sources, start=1):
        item["id"] = idx
    return sources


def _format_sources(sources: list[dict[str, Any]]) -> str:
    lines = []
    for source in sources:
        lines.append(
            f"[{source['id']}] doc_id={source.get('doc_id')} page={source.get('page')} "
            f"source={source.get('source')} text={source.get('text')}"
        )
    return "\n".join(lines)


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _sort_sources_chrono(
    sources: list[dict[str, Any]],
    *,
    db: Session | None,
) -> list[dict[str, Any]]:
    if not sources or db is None:
        return sources
    doc_ids = {item.get("doc_id") for item in sources if item.get("doc_id")}
    if not doc_ids:
        return sources
    rows = (
        db.query(Document.id, Document.document_date, Document.created)
        .filter(Document.id.in_(list(doc_ids)))
        .all()
    )
    dates: dict[int, tuple[datetime | None, datetime | None]] = {}
    for row in rows:
        doc_date = _parse_date(row.document_date)
        created = _parse_date(row.created)
        dates[int(row.id)] = (doc_date, created)

    def sort_key(item: dict[str, Any]) -> tuple[int, datetime | None, datetime | None, int]:
        doc_id = int(item.get("doc_id") or 0)
        doc_date, created = dates.get(doc_id, (None, None))
        missing = 1 if not doc_date and not created else 0
        page = int(item.get("page") or 0)
        return (missing, doc_date or created, created or doc_date, page)

    return sorted(sources, key=sort_key)

def _normalize_history(history: list[dict[str, str]] | list[Any]) -> list[tuple[str, str]]:
    if not history:
        return []
    items: list[tuple[str, str]] = []
    for item in history[-MAX_HISTORY_TURNS:]:
        if isinstance(item, dict):
            question = (item.get("question") or "").strip()
            answer = (item.get("answer") or "").strip()
        else:
            question = (getattr(item, "question", "") or "").strip()
            answer = (getattr(item, "answer", "") or "").strip()
        if len(question) > MAX_HISTORY_CHARS:
            question = question[:MAX_HISTORY_CHARS].strip()
        if len(answer) > MAX_HISTORY_CHARS:
            answer = answer[:MAX_HISTORY_CHARS].strip()
        if not question and not answer:
            continue
        items.append((question, answer))
    return items


def _format_history(history: list[dict[str, str]] | list[Any]) -> str:
    items = _normalize_history(history)
    if not items:
        return "None"
    blocks = []
    for question, answer in items:
        blocks.append(f"Q: {question}\nA: {answer}".strip())
    return "\n\n".join(blocks) if blocks else "None"


def _ensure_conversation_id(value: str | None) -> str:
    raw = (value or "").strip()
    if raw:
        return raw
    return uuid4().hex


def _resolve_evidence_for_sources(
    settings: Settings,
    sources: list[dict[str, Any]],
    *,
    db: Session | None = None,
) -> None:
    candidates: list[dict[str, Any]] = []
    for source in sources:
        snippet = str(source.get("snippet") or "").strip()
        if len(snippet) < settings.evidence_min_snippet_chars:
            continue
        candidates.append(
            {
                "doc_id": source.get("doc_id"),
                "page": source.get("page"),
                "snippet": snippet,
                "source": source.get("source"),
                "bbox": source.get("bbox"),
            }
        )
    if not candidates:
        return
    matches = resolve_evidence_matches(
        candidates,
        max_pages=settings.evidence_max_pages,
        settings=settings,
        db=db,
    )
    index: dict[tuple[int, int, str], dict[str, Any]] = {}
    for match in matches:
        key = (
            int(match.get("doc_id") or 0),
            int(match.get("page") or 0),
            str(match.get("snippet") or "").strip(),
        )
        index[key] = match
    for source in sources:
        key = (
            int(source.get("doc_id") or 0),
            int(source.get("page") or 0),
            str(source.get("snippet") or "").strip(),
        )
        resolved = index.get(key)
        if not resolved:
            continue
        source["evidence_status"] = resolved.get("status")
        source["evidence_confidence"] = float(resolved.get("confidence") or 0.0)
        source["evidence_error"] = resolved.get("error")
        resolved_bbox = resolved.get("bbox")
        if resolved_bbox is not None:
            source["bbox"] = resolved_bbox


def generate_followups(
    settings: Settings,
    *,
    question: str,
    answer: str,
    citations: list[dict[str, Any]],
    doc_id: int | None = None,
    relationship_mode: str | None = None,
) -> list[str]:
    ensure_text_llm_ready(settings)
    prompt = _load_followups_prompt(settings)
    trimmed_citations = [
        {
            "doc_id": c.get("doc_id"),
            "page": c.get("page"),
            "snippet": (c.get("snippet") or "")[:240],
        }
        for c in citations
    ]
    prompt = (
        prompt.replace("{question}", question.strip())
        .replace("{answer}", answer.strip())
        .replace("{citations}", json.dumps(trimmed_citations, ensure_ascii=False))
        .replace("{doc_id}", str(doc_id or ""))
        .replace("{relationship_mode}", str(relationship_mode or ""))
    )
    raw = llm_client.chat_completion(
        settings,
        model=settings.text_model or "",
        messages=[{"role": "user", "content": prompt}],
        timeout=60,
    )
    candidates = parse_string_list_json(raw)
    if candidates:
        return candidates[:5]
    parsed = parse_json_object(raw)
    if isinstance(parsed, dict):
        values = parsed.get("questions") or parsed.get("followups") or parsed.get("suggestions")
        if isinstance(values, list):
            normalized = [str(value).strip() for value in values if str(value).strip()]
            if normalized:
                return normalized[:5]
    return []


def answer_question(
    settings: Settings,
    question: str,
    top_k: int = 6,
    source: str | None = None,
    min_quality: int | None = None,
    doc_id: int | None = None,
    relationship_mode: str | None = None,
    history: list[dict[str, str]] | None = None,
    conversation_id: str | None = None,
    stream: bool = False,
    db: Session | None = None,
) -> dict[str, str | list[dict[str, Any]]] | StreamingResponse:
    ensure_text_llm_ready(settings)
    ensure_qdrant_ready(settings)
    vector = embed_text(settings, question)
    filter_payload: dict[str, Any] = {"must_not": [{"key": "type", "match": {"value": "doc"}}]}
    if doc_id is not None:
        filter_payload.setdefault("must", []).append({"key": "doc_id", "match": {"value": doc_id}})
    raw = search_points(settings, vector, limit=max(3, top_k * 3), filter_payload=filter_payload)
    hits = raw.get("result", []) or []
    if source:
        hits = [hit for hit in hits if (hit.get("payload") or {}).get("source") == source]
    sources = _build_sources(hits, min_quality=min_quality)
    sources = _dedupe_sources(sources)
    sources = sources[:top_k]
    if relationship_mode == "chrono":
        sources = _sort_sources_chrono(sources, db=db)
    sources = _renumber_sources(sources)
    if sources:
        sources_text = _format_sources(sources)
    else:
        sources_text = "No sources available."
    prompt = _load_chrono_prompt(settings) if relationship_mode == "chrono" else _load_prompt(settings)
    resolved_conversation_id = _ensure_conversation_id(conversation_id)
    prompt = (
        prompt.replace("{question}", question.strip())
        .replace("{sources}", sources_text)
        .replace("{history}", _format_history(history or []))
    )
    logger.info("Chat prompt chars=%s sources=%s", len(prompt), len(sources))
    if not stream:
        answer = llm_client.chat_completion(
            settings,
            model=settings.text_model or "",
            messages=[{"role": "user", "content": prompt}],
            timeout=120,
        )
        _resolve_evidence_for_sources(settings, sources, db=db)
        for source in sources:
            source.pop("text", None)
        return {
            "question": question,
            "answer": answer,
            "conversation_id": resolved_conversation_id,
            "citations": sources,
        }

    def event_stream() -> Iterable[bytes]:
        answer_chunks: list[str] = []
        for token in llm_client.stream_chat_completion(
            settings,
            model=settings.text_model or "",
            messages=[{"role": "user", "content": prompt}],
            timeout=None,
        ):
            answer_chunks.append(token)
            payload = json.dumps({"token": token})
            yield f"data: {payload}\n\n".encode("utf-8")
        answer = "".join(answer_chunks).strip()
        _resolve_evidence_for_sources(settings, sources, db=db)
        for source in sources:
            source.pop("text", None)
        done_payload = json.dumps(
            {
                "answer": answer,
                "conversation_id": resolved_conversation_id,
                "citations": sources,
            }
        )
        yield f"event: done\ndata: {done_payload}\n\n".encode("utf-8")

    return StreamingResponse(event_stream(), media_type="text/event-stream")
