from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING, Any

from app.api_models import CorrespondentIn, DocumentIn, DocumentTypeIn, TagIn
from app.config import Settings
from app.models import (
    Correspondent,
    Document,
    DocumentEmbedding,
    DocumentNote,
    DocumentType,
    SyncState,
    Tag,
)
from app.services.documents.note_ids import next_local_note_id
from app.services.documents.page_texts_merge import collect_page_texts
from app.services.integrations import paperless
from app.services.pipeline.sync_state import ensure_started, get_or_create_state, mark_running
from app.services.runtime.time_utils import estimate_eta_seconds
from app.services.search.embedding_init import ensure_embedding_collection
from app.services.search.embeddings import (
    chunk_document_with_pages,
    delete_points_for_doc,
    embed_text,
    make_point_id,
    upsert_points,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

ResponseDict = dict[str, object]
ReferenceCache = dict[str, set[int]]
TaskBuilder = Callable[..., list[dict[str, object]]]
TaskEnqueuer = Callable[[Settings, list[dict[str, object]]], object]
TaskFrontEnqueuer = Callable[[Settings, list[dict[str, object]]], object]
PaperlessListDocuments = Callable[..., dict[str, object]]
PaperlessGetDocument = Callable[[Settings, int], dict[str, object]]

logger = logging.getLogger(__name__)


def build_sync_status_payload(db: Session) -> ResponseDict:
    state = db.get(SyncState, "documents")
    if not state:
        return {"last_synced_at": None, "status": "idle", "processed": 0, "total": 0}
    eta_seconds = estimate_eta_seconds(state.started_at, state.processed, state.total)
    return {
        "last_synced_at": state.last_synced_at,
        "status": state.status or "idle",
        "processed": state.processed or 0,
        "total": state.total or 0,
        "started_at": state.started_at,
        "cancel_requested": state.cancel_requested or False,
        "eta_seconds": eta_seconds,
    }


def cancel_documents_sync(db: Session) -> ResponseDict:
    state = db.get(SyncState, "documents")
    if not state:
        return {"status": "idle"}
    state.cancel_requested = True
    db.commit()
    return {"status": "cancelling"}


def apply_note_fields(
    target: DocumentNote, *, note_body: str, created: str | None, user: dict[str, Any]
) -> None:
    target.note = note_body
    target.created = created
    target.user_id = user.get("id")
    target.user_username = user.get("username")
    target.user_first_name = user.get("first_name")
    target.user_last_name = user.get("last_name")


def merge_document_notes(db: Session, doc: Document, incoming_notes: Sequence[object]) -> None:
    existing_by_id: dict[int, DocumentNote] = {int(note.id): note for note in (doc.notes or [])}
    incoming_ids: set[int] = set()
    saw_malformed_id = False

    for note in incoming_notes:
        note_obj = note
        try:
            note_id = int(note_obj.id)  # type: ignore[attr-defined]
        except (TypeError, ValueError):
            saw_malformed_id = True
            logger.warning(
                "Skipping malformed note id during sync doc_id=%s note_id=%s",
                getattr(doc, "id", None),
                getattr(note_obj, "id", None),
            )
            continue
        if note_id in incoming_ids:
            continue
        incoming_ids.add(note_id)
        user = getattr(note_obj, "user", None)
        normalized_user = user if isinstance(user, dict) else {}
        existing = existing_by_id.get(note_id)
        if existing is None:
            global_note = db.get(DocumentNote, note_id)
            if global_note is not None:
                if int(global_note.document_id) != int(doc.id):
                    global_note.id = next_local_note_id(db)
                    db.flush()
                else:
                    existing = global_note
                    existing_by_id[note_id] = global_note
        if existing:
            apply_note_fields(
                existing,
                note_body=str(getattr(note_obj, "note", "")),
                created=getattr(note_obj, "created", None),
                user=normalized_user,
            )
            continue
        created = DocumentNote(id=note_id)
        apply_note_fields(
            created,
            note_body=str(getattr(note_obj, "note", "")),
            created=getattr(note_obj, "created", None),
            user=normalized_user,
        )
        doc.notes.append(created)
        existing_by_id[note_id] = created

    if saw_malformed_id:
        logger.warning(
            "Skipping stale note cleanup due to malformed note ids doc_id=%s",
            getattr(doc, "id", None),
        )
        return

    for stale in [note for note in list(doc.notes or []) if int(note.id) not in incoming_ids]:
        doc.notes.remove(stale)


def upsert_document(
    db: Session,
    settings: Settings,
    data: DocumentIn,
    cache: ReferenceCache,
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

    if data.correspondent is not None and data.correspondent not in cache["correspondents"]:
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

    if data.document_type is not None and data.document_type not in cache["document_types"]:
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

    merge_document_notes(db, doc, list(data.notes))

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


def embed_documents(
    db: Session,
    settings: Settings,
    documents: list[Document],
    force_embed: bool = False,
) -> int:
    if not documents:
        return 0
    if not settings.embedding_model:
        raise RuntimeError("EMBEDDING_MODEL not set")
    ensure_embedding_collection(settings)
    points: list[dict[str, object]] = []
    embedded = 0
    processed = 0
    state = get_or_create_state(db, "embeddings")
    mark_running(state, total=len(documents), processed=0, reset_cancel=False)
    db.commit()
    logger.info("Embedding run docs=%s", len(documents))
    for doc in documents:
        content_value = doc.content or ""
        baseline_pages, vision_pages, page_texts = collect_page_texts(
            settings,
            db,
            doc,
            force_vision=force_embed,
        )
        if not content_value and not page_texts:
            processed += 1
            state.processed = processed
            continue
        hash_source = (
            "\f".join(f"{page.source}:{page.text}" for page in page_texts)
            if page_texts
            else content_value
        )
        content_hash = sha256((hash_source or "").encode("utf-8")).hexdigest()
        existing = db.get(DocumentEmbedding, doc.id)
        if (
            (not force_embed)
            and existing
            and existing.content_hash == content_hash
            and existing.embedding_model == settings.embedding_model
            and existing.chunk_count
        ):
            logger.info("Skip embed doc=%s (unchanged)", doc.id)
            processed += 1
            state.processed = processed
            if processed % 5 == 0 or processed == state.total:
                db.commit()
            continue
        embedding_source = "vision" if vision_pages else "paperless"
        delete_points_for_doc(settings, doc.id, source=embedding_source)
        baseline_chunks = chunk_document_with_pages(settings, content_value, baseline_pages or None)
        vision_chunks = (
            chunk_document_with_pages(settings, content_value, vision_pages or None)
            if vision_pages
            else []
        )
        chunks = baseline_chunks + vision_chunks
        logger.info("Chunked doc=%s chunks=%s", doc.id, len(chunks))
        doc_points: list[dict[str, object]] = []
        for idx, chunk in enumerate(chunks):
            chunk_text_value = str(chunk["text"])
            vector = embed_text(settings, chunk_text_value)
            doc_points.append(
                {
                    "id": make_point_id(doc.id, idx, embedding_source),
                    "vector": vector,
                    "payload": {
                        "doc_id": doc.id,
                        "chunk": idx,
                        "text": chunk_text_value,
                        "page": chunk.get("page"),
                        "source": chunk.get("source"),
                        "quality_score": chunk.get("quality_score"),
                        "bbox": chunk.get("bbox"),
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
        existing.embedded_at = datetime.now(UTC).isoformat()
        previous_source = str(existing.embedding_source or "").strip().lower()
        if previous_source == "both" or (previous_source and previous_source != embedding_source):
            existing.embedding_source = "both"
        else:
            existing.embedding_source = embedding_source
        existing.chunk_count = len(chunks)
        embedded += 1
        processed += 1
        state.processed = processed
        if processed % 5 == 0 or processed == state.total:
            db.commit()
    if points:
        db.commit()
    state.status = "idle"
    state.last_synced_at = datetime.now(UTC).isoformat()
    db.commit()
    return embedded


def run_documents_sync(
    *,
    db: Session,
    settings: Settings,
    page_size: int,
    incremental: bool,
    embed: bool,
    page: int,
    page_only: bool,
    force_embed: bool,
    mark_missing: bool,
    insert_only: bool,
    list_documents_fn: PaperlessListDocuments,
    build_task_sequence_fn: TaskBuilder,
    enqueue_task_sequence_fn: TaskEnqueuer,
) -> ResponseDict:
    modified_since: str | None = None
    if incremental:
        state = db.get(SyncState, "documents")
        modified_since = state.last_synced_at if state else None

    state = get_or_create_state(db, "documents")
    mark_running(state, total=None, processed=0)
    db.commit()

    upserted = 0
    processed = 0
    seen_ids: set[int] = set()
    cache: ReferenceCache = {"correspondents": set(), "document_types": set(), "tags": set()}
    normalized_page = max(1, page)
    total = 0
    embed_queue: list[Document] = []
    while True:
        payload = list_documents_fn(
            settings,
            page=normalized_page,
            page_size=page_size,
            modified__gte=modified_since,
        )
        if normalized_page == 1:
            raw_total = payload.get("count", 0)
            total = int(raw_total) if isinstance(raw_total, int | str) else 0
            state.total = total
            db.commit()
        raw_results = payload.get("results", [])
        results = raw_results if isinstance(raw_results, list) else []
        if not results:
            break
        inserted_ids: list[int] = []
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
            if mark_missing and not incremental:
                seen_ids.add(data.id)
            if insert_only:
                existing = db.get(Document, data.id)
                if existing:
                    processed += 1
                    state.processed = processed
                    continue
            upsert_document(db, settings, data, cache)
            inserted_ids.append(data.id)
            upserted += 1
            processed += 1
            state.processed = processed
        db.commit()
        if embed:
            ids = inserted_ids if insert_only else [DocumentIn.model_validate(raw).id for raw in results]
            if ids:
                embed_queue.extend(db.query(Document).filter(Document.id.in_(ids)).all())
        if not payload.get("next") or page_only:
            break
        normalized_page += 1

    state.last_synced_at = datetime.now(UTC).isoformat()
    state.status = "idle"
    db.commit()
    marked_deleted = 0
    if mark_missing and not incremental:
        timestamp = datetime.now(UTC).isoformat()
        missing_docs = db.query(Document).filter(~Document.id.in_(list(seen_ids))).all()
        for doc in missing_docs:
            if doc.deleted_at and str(doc.deleted_at).startswith("DELETED in Paperless"):
                continue
            doc.deleted_at = f"DELETED in Paperless (copy kept) @ {timestamp}"
            marked_deleted += 1
        if marked_deleted:
            db.commit()
    embedded = 0
    if embed and embed_queue:
        if settings.queue_enabled:
            for doc in embed_queue:
                tasks = build_task_sequence_fn(
                    settings, doc.id, include_sync=False, force=bool(force_embed)
                )
                enqueue_task_sequence_fn(settings, tasks)
            embed_state = get_or_create_state(db, "embeddings")
            embed_state.status = "running"
            ensure_started(embed_state)
            embed_state.last_synced_at = datetime.now(UTC).isoformat()
            db.commit()
        else:
            embedded = embed_documents(db, settings, embed_queue, force_embed=force_embed)
    return {
        "count": total,
        "upserted": upserted,
        "incremental": incremental,
        "embedded": embedded,
        "marked_deleted": marked_deleted if mark_missing and not incremental else None,
    }


def run_single_document_sync(
    *,
    doc_id: int,
    db: Session,
    settings: Settings,
    embed: bool,
    force_embed: bool,
    priority: bool,
    get_document_fn: PaperlessGetDocument,
    build_task_sequence_fn: TaskBuilder,
    enqueue_task_sequence_fn: TaskEnqueuer,
    enqueue_task_sequence_front_fn: TaskFrontEnqueuer,
) -> ResponseDict:
    logger.info("Sync doc=%s embed=%s force_embed=%s", doc_id, embed, force_embed)
    raw = get_document_fn(settings, doc_id)
    data = DocumentIn.model_validate(raw)
    cache: ReferenceCache = {"correspondents": set(), "document_types": set(), "tags": set()}
    upsert_document(db, settings, data, cache)
    db.commit()
    embedded = 0
    if embed:
        doc = db.get(Document, doc_id)
        if doc:
            if settings.queue_enabled:
                tasks = build_task_sequence_fn(
                    settings, doc.id, include_sync=False, force=bool(force_embed)
                )
                if priority:
                    enqueue_task_sequence_front_fn(settings, tasks)
                else:
                    enqueue_task_sequence_fn(settings, tasks)
                embed_state = get_or_create_state(db, "embeddings")
                embed_state.status = "running"
                ensure_started(embed_state)
                embed_state.last_synced_at = datetime.now(UTC).isoformat()
                db.commit()
            else:
                embedded = embed_documents(db, settings, [doc], force_embed=force_embed)
    logger.info("Sync doc=%s done embedded=%s", doc_id, embedded)
    return {"id": doc_id, "status": "synced", "embedded": embedded}
