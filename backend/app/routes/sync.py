from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import Settings, load_settings
from app.db import get_db
from app.models import (
    Correspondent,
    Document,
    DocumentEmbedding,
    DocumentNote,
    DocumentType,
    SyncState,
    Tag,
)
from app.schemas import CorrespondentIn, DocumentIn, DocumentTypeIn, TagIn
from app.services import paperless
from app.services.embeddings import (
    chunk_document_with_pages,
    delete_points_for_doc,
    embed_text,
    ensure_qdrant_collection,
    make_point_id,
    upsert_points,
)
from app.services.text_pages import get_page_text_layers
from app.services.page_text_store import upsert_page_texts
from app.services.queue import enqueue_task_sequence
from app.api_models import (
    SyncDocumentsResponse,
    SyncStatusResponse,
    SyncCancelResponse,
    SyncDocumentResponse,
    SyncSimpleResponse,
)

router = APIRouter(prefix="/sync", tags=["sync"])


def settings_dep() -> Settings:
    return load_settings()


@router.post("/documents", response_model=SyncDocumentsResponse)
def sync_documents(
    page_size: int = 50,
    incremental: bool = True,
    embed: bool | None = None,
    page: int = 1,
    page_only: bool = False,
    force_embed: bool = False,
    settings: Settings = Depends(settings_dep),
    db: Session = Depends(get_db),
):
    if embed is None:
        embed = settings.embed_on_sync
    modified_since: str | None = None
    if incremental:
        state = db.get(SyncState, "documents")
        modified_since = state.last_synced_at if state else None

    state = db.get(SyncState, "documents")
    if not state:
        state = SyncState(key="documents")
        db.add(state)
    state.status = "running"
    state.started_at = datetime.now(timezone.utc).isoformat()
    state.processed = 0
    state.total = None
    state.cancel_requested = False
    db.commit()

    upserted = 0
    cache = {"correspondents": set(), "document_types": set(), "tags": set()}
    page = max(1, page)
    total = 0
    embed_queue: list[Document] = []
    while True:
        payload = paperless.list_documents(
            settings,
            page=page,
            page_size=page_size,
            modified__gte=modified_since,
        )
        if page == 1:
            total = payload.get("count", 0)
            state.total = total
            db.commit()
        results = payload.get("results", [])
        if not results:
            break
        db.refresh(state)
        if state.cancel_requested:
            state.status = "cancelled"
            db.commit()
            return {
                "count": total,
                "upserted": upserted,
                "incremental": incremental,
                "embedded": 0,
                "status": "cancelled",
            }
        for raw in results:
            data = DocumentIn.model_validate(raw)
            _upsert_document(db, settings, data, cache)
            upserted += 1
            state.processed = upserted
        db.commit()
        if embed:
            ids = [DocumentIn.model_validate(raw).id for raw in results]
            embed_queue.extend(db.query(Document).filter(Document.id.in_(ids)).all())
        if not payload.get("next"):
            break
        if page_only:
            break
        page += 1

    state.last_synced_at = datetime.now(timezone.utc).isoformat()
    state.status = "idle"
    db.commit()
    embedded = 0
    if embed and embed_queue:
        if settings.queue_enabled:
            for doc in embed_queue:
                tasks = []
                if settings.enable_vision_ocr:
                    tasks.append({"doc_id": doc.id, "task": "vision_ocr"})
                    tasks.append({"doc_id": doc.id, "task": "embeddings_vision"})
                    tasks.append({"doc_id": doc.id, "task": "suggestions_paperless"})
                    tasks.append({"doc_id": doc.id, "task": "suggestions_vision"})
                else:
                    tasks.append({"doc_id": doc.id, "task": "embeddings_paperless"})
                    tasks.append({"doc_id": doc.id, "task": "suggestions_paperless"})
                enqueue_task_sequence(settings, tasks)
            embed_state = db.get(SyncState, "embeddings")
            if not embed_state:
                embed_state = SyncState(key="embeddings")
                db.add(embed_state)
            embed_state.status = "running"
            if not embed_state.started_at:
                embed_state.started_at = datetime.now(timezone.utc).isoformat()
            embed_state.last_synced_at = datetime.now(timezone.utc).isoformat()
            db.commit()
            embedded = 0
        else:
            embedded = _embed_documents(db, settings, embed_queue, force_embed=force_embed)
    return {
        "count": total,
        "upserted": upserted,
        "incremental": incremental,
        "embedded": embedded,
    }


@router.get("/documents", response_model=SyncStatusResponse)
def sync_status(db: Session = Depends(get_db)):
    state = db.get(SyncState, "documents")
    if not state:
        return {"last_synced_at": None, "status": "idle", "processed": 0, "total": 0}
    eta_seconds = None
    if state.started_at and state.processed and state.total:
        try:
            started = datetime.fromisoformat(state.started_at.replace("Z", "+00:00"))
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            rate = state.processed / max(1.0, elapsed)
            remaining = state.total - state.processed
            eta_seconds = int(max(0.0, remaining / rate)) if rate > 0 else None
        except Exception:
            eta_seconds = None
    return {
        "last_synced_at": state.last_synced_at,
        "status": state.status or "idle",
        "processed": state.processed or 0,
        "total": state.total or 0,
        "started_at": state.started_at,
        "cancel_requested": state.cancel_requested or False,
        "eta_seconds": eta_seconds,
    }


@router.post("/documents/cancel", response_model=SyncCancelResponse)
def cancel_sync(db: Session = Depends(get_db)):
    state = db.get(SyncState, "documents")
    if not state:
        return {"status": "idle"}
    state.cancel_requested = True
    db.commit()
    return {"status": "cancelling"}


def _upsert_document(
    db: Session,
    settings: Settings,
    data: DocumentIn,
    cache: dict[str, set[int]],
) -> None:
    doc = db.get(Document, data.id)
    if not doc:
        doc = Document(id=data.id)
        db.add(doc)
    doc.title = data.title
    doc.content = data.content
    doc.correspondent_id = data.correspondent
    doc.document_type_id = data.document_type
    doc.document_date = data.document_date
    doc.created = data.created
    doc.modified = data.modified
    doc.added = data.added
    doc.deleted_at = data.deleted_at
    doc.archive_serial_number = data.archive_serial_number
    doc.original_file_name = data.original_file_name
    doc.mime_type = data.mime_type
    doc.page_count = data.page_count
    doc.owner_id = data.owner
    doc.user_can_change = data.user_can_change
    doc.is_shared_by_requester = data.is_shared_by_requester

    if data.correspondent is not None:
        if data.correspondent not in cache["correspondents"]:
            correspondent = db.get(Correspondent, data.correspondent)
            if not correspondent:
                raw = paperless.get_correspondent(settings, data.correspondent)
                corr_data = CorrespondentIn.model_validate(raw)
                correspondent = Correspondent(
                    id=corr_data.id,
                    name=corr_data.name,
                    slug=corr_data.slug,
                    matching_algorithm=corr_data.matching_algorithm,
                    is_insensitive=corr_data.is_insensitive,
                )
                db.merge(correspondent)
            cache["correspondents"].add(data.correspondent)

    if data.document_type is not None:
        if data.document_type not in cache["document_types"]:
            doc_type = db.get(DocumentType, data.document_type)
            if not doc_type:
                raw = paperless.get_document_type(settings, data.document_type)
                doc_type_data = DocumentTypeIn.model_validate(raw)
                doc_type = DocumentType(
                    id=doc_type_data.id,
                    name=doc_type_data.name,
                    slug=doc_type_data.slug,
                    matching_algorithm=doc_type_data.matching_algorithm,
                    is_insensitive=doc_type_data.is_insensitive,
                )
                db.merge(doc_type)
            cache["document_types"].add(data.document_type)

    doc.notes.clear()
    for note in data.notes:
        user = note.user or {}
        doc.notes.append(
            DocumentNote(
                id=note.id,
                note=note.note,
                created=note.created,
                user_id=user.get("id"),
                user_username=user.get("username"),
                user_first_name=user.get("first_name"),
                user_last_name=user.get("last_name"),
            )
        )

    doc.tags.clear()
    for tag_id in data.tags or []:
        if tag_id in cache["tags"]:
            tag = db.get(Tag, tag_id)
            if tag:
                doc.tags.append(tag)
            continue
        tag = db.get(Tag, tag_id)
        if not tag:
            raw = paperless.get_tag(settings, tag_id)
            tag_data = TagIn.model_validate(raw)
            tag = Tag(
                id=tag_data.id,
                name=tag_data.name,
                color=tag_data.color,
                is_inbox_tag=tag_data.is_inbox_tag,
                slug=tag_data.slug,
                matching_algorithm=tag_data.matching_algorithm,
                is_insensitive=tag_data.is_insensitive,
            )
            db.merge(tag)
        cache["tags"].add(tag_id)
        doc.tags.append(tag)


@router.post("/documents/{doc_id}", response_model=SyncDocumentResponse)
def sync_document(
    doc_id: int,
    settings: Settings = Depends(settings_dep),
    db: Session = Depends(get_db),
    embed: bool | None = None,
    force_embed: bool = False,
):
    logger = __import__("logging").getLogger(__name__)
    if embed is None:
        embed = settings.embed_on_sync
    logger.info("Sync doc=%s embed=%s force_embed=%s", doc_id, embed, force_embed)
    raw = paperless.get_document(settings, doc_id)
    data = DocumentIn.model_validate(raw)
    cache = {"correspondents": set(), "document_types": set(), "tags": set()}
    _upsert_document(db, settings, data, cache)
    db.commit()
    embedded = 0
    if embed:
        doc = db.get(Document, doc_id)
        if doc:
            if settings.queue_enabled:
                tasks = []
                if settings.enable_vision_ocr:
                    tasks.append({"doc_id": doc.id, "task": "vision_ocr"})
                    tasks.append({"doc_id": doc.id, "task": "embeddings_vision"})
                    tasks.append({"doc_id": doc.id, "task": "suggestions_paperless"})
                    tasks.append({"doc_id": doc.id, "task": "suggestions_vision"})
                else:
                    tasks.append({"doc_id": doc.id, "task": "embeddings_paperless"})
                    tasks.append({"doc_id": doc.id, "task": "suggestions_paperless"})
                enqueue_task_sequence(settings, tasks)
                embed_state = db.get(SyncState, "embeddings")
                if not embed_state:
                    embed_state = SyncState(key="embeddings")
                    db.add(embed_state)
                embed_state.status = "running"
                if not embed_state.started_at:
                    embed_state.started_at = datetime.now(timezone.utc).isoformat()
                embed_state.last_synced_at = datetime.now(timezone.utc).isoformat()
                db.commit()
                embedded = 0
            else:
                embedded = _embed_documents(db, settings, [doc], force_embed=force_embed)
    logger.info("Sync doc=%s done embedded=%s", doc_id, embedded)
    return {"id": doc_id, "status": "synced", "embedded": embedded}


@router.post("/tags", response_model=SyncSimpleResponse)
def sync_tags(
    page: int = 1,
    page_size: int = 200,
    settings: Settings = Depends(settings_dep),
    db: Session = Depends(get_db),
):
    payload = paperless.list_tags(settings, page=page, page_size=page_size)
    results = payload.get("results", [])
    upserted = 0
    seen: set[int] = set()
    for raw in results:
        data = TagIn.model_validate(raw)
        if data.id in seen:
            continue
        seen.add(data.id)
        tag = db.get(Tag, data.id)
        if not tag:
            tag = Tag(id=data.id)
            db.add(tag)
        tag.name = data.name
        tag.color = data.color
        tag.is_inbox_tag = data.is_inbox_tag
        tag.slug = data.slug
        tag.matching_algorithm = data.matching_algorithm
        tag.is_insensitive = data.is_insensitive
        upserted += 1
    db.commit()
    return {"count": len(results), "upserted": upserted}


@router.post("/correspondents", response_model=SyncSimpleResponse)
def sync_correspondents(
    page: int = 1,
    page_size: int = 200,
    settings: Settings = Depends(settings_dep),
    db: Session = Depends(get_db),
):
    payload = paperless.list_correspondents(settings, page=page, page_size=page_size)
    results = payload.get("results", [])
    upserted = 0
    seen: set[int] = set()
    for raw in results:
        data = CorrespondentIn.model_validate(raw)
        if data.id in seen:
            continue
        seen.add(data.id)
        correspondent = db.get(Correspondent, data.id)
        if not correspondent:
            correspondent = Correspondent(id=data.id)
            db.add(correspondent)
            db.flush()
        correspondent.name = data.name
        correspondent.slug = data.slug
        correspondent.matching_algorithm = data.matching_algorithm
        correspondent.is_insensitive = data.is_insensitive
        upserted += 1
    db.commit()
    return {"count": len(results), "upserted": upserted}


@router.post("/document-types", response_model=SyncSimpleResponse)
def sync_document_types(
    page: int = 1,
    page_size: int = 200,
    settings: Settings = Depends(settings_dep),
    db: Session = Depends(get_db),
):
    payload = paperless.list_document_types(settings, page=page, page_size=page_size)
    results = payload.get("results", [])
    upserted = 0
    seen: set[int] = set()
    for raw in results:
        data = DocumentTypeIn.model_validate(raw)
        if data.id in seen:
            continue
        seen.add(data.id)
        doc_type = db.get(DocumentType, data.id)
        if not doc_type:
            doc_type = DocumentType(id=data.id)
            db.add(doc_type)
        doc_type.name = data.name
        doc_type.slug = data.slug
        doc_type.matching_algorithm = data.matching_algorithm
        doc_type.is_insensitive = data.is_insensitive
        upserted += 1
    db.commit()
    return {"count": len(results), "upserted": upserted}


def _embed_documents(
    db: Session,
    settings: Settings,
    documents: list[Document],
    force_embed: bool = False,
) -> int:
    if not documents:
        return 0
    if not settings.embedding_model:
        raise RuntimeError("EMBEDDING_MODEL not set")
    sample_embedding = embed_text(settings, "dimension probe")
    ensure_qdrant_collection(settings, vector_size=len(sample_embedding))
    points = []
    embedded = 0
    processed = 0
    state = db.get(SyncState, "embeddings")
    if not state:
        state = SyncState(key="embeddings")
        db.add(state)
    state.status = "running"
    state.started_at = datetime.now(timezone.utc).isoformat()
    state.processed = 0
    state.total = len(documents)
    db.commit()
    logger = __import__("logging").getLogger(__name__)
    logger.info("Embedding run docs=%s", len(documents))
    for doc in documents:
        content_value = doc.content or ""
        baseline_pages, vision_pages = get_page_text_layers(
            settings,
            doc.content,
            fetch_pdf_bytes=lambda: paperless.get_document_pdf(settings, doc.id),
            force_full_vision=bool(force_embed),
        )
        if vision_pages:
            upsert_page_texts(db, settings, doc.id, vision_pages, source_filter="vision_ocr")
        page_texts = baseline_pages + vision_pages
        if not content_value and not page_texts:
            processed += 1
            state.processed = processed
            continue
        if page_texts:
            hash_source = "\f".join(f"{page.source}:{page.text}" for page in page_texts)
        else:
            hash_source = content_value
        content_hash = sha256((hash_source or "").encode("utf-8")).hexdigest()
        existing = db.get(DocumentEmbedding, doc.id)
        if (not force_embed) and existing and existing.content_hash == content_hash and existing.embedding_model == settings.embedding_model:
            if existing.chunk_count:
                logger.info("Skip embed doc=%s (unchanged)", doc.id)
                processed += 1
                state.processed = processed
                if processed % 5 == 0 or processed == state.total:
                    db.commit()
                continue
        delete_points_for_doc(settings, doc.id)
        baseline_chunks = chunk_document_with_pages(settings, content_value, baseline_pages or None)
        vision_chunks = chunk_document_with_pages(settings, content_value, vision_pages or None) if vision_pages else []
        chunks = baseline_chunks + vision_chunks
        logger.info("Chunked doc=%s chunks=%s", doc.id, len(chunks))
        doc_points = []
        for idx, chunk in enumerate(chunks):
            chunk_text_value = str(chunk["text"])
            vector = embed_text(settings, chunk_text_value)
            doc_points.append(
                {
                    "id": make_point_id(doc.id, idx),
                    "vector": vector,
                    "payload": {
                        "doc_id": doc.id,
                        "chunk": idx,
                        "text": chunk_text_value,
                        "page": chunk.get("page"),
                        "source": chunk.get("source"),
                        "quality_score": chunk.get("quality_score"),
                    },
                }
            )
        if doc_points:
            upsert_points(settings, doc_points)
            points.extend(doc_points)
        if not existing:
            existing = DocumentEmbedding(doc_id=doc.id)
            db.add(existing)
        existing.content_hash = content_hash
        existing.embedding_model = settings.embedding_model
        existing.embedded_at = datetime.now(timezone.utc).isoformat()
        existing.chunk_count = len(chunks)
        embedded += 1
        processed += 1
        state.processed = processed
        if processed % 5 == 0 or processed == state.total:
            db.commit()
    if points:
        db.commit()
    state.status = "idle"
    state.last_synced_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    return embedded
