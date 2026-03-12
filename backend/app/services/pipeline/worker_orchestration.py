from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from sqlalchemy.orm import Session

    from app.config import Settings
    from app.models import Document


def _baseline_suggestion_text(
    settings: Settings,
    db: Session,
    *,
    doc: Document,
    doc_id: int,
    is_large_doc_fn: Callable[[Settings, Document], bool],
    build_hier_summary_fn: Callable[..., str],
    build_page_notes_fn: Callable[..., str],
) -> str:
    baseline_text = doc.content or ""
    if not is_large_doc_fn(settings, doc):
        return baseline_text
    distilled = build_hier_summary_fn(
        db,
        doc_id=doc_id,
        source="paperless_ocr",
        max_chars=settings.worker_suggestions_max_chars,
    )
    if not distilled:
        distilled = build_page_notes_fn(
            db,
            doc_id=doc_id,
            source="paperless_ocr",
            max_chars=settings.worker_suggestions_max_chars,
        )
    return distilled or baseline_text


def _vision_suggestion_text(
    settings: Settings,
    db: Session,
    *,
    doc: Document,
    doc_id: int,
    vision_pages: Sequence[object],
    is_large_doc_fn: Callable[[Settings, Document], bool],
    build_hier_summary_fn: Callable[..., str],
    build_page_notes_fn: Callable[..., str],
    join_pages_fn: Callable[..., str],
) -> str:
    vision_text = ""
    if is_large_doc_fn(settings, doc):
        vision_text = build_hier_summary_fn(
            db,
            doc_id=doc_id,
            source="vision_ocr",
            max_chars=settings.worker_suggestions_max_chars,
        )
    if not vision_text:
        vision_text = build_page_notes_fn(
            db,
            doc_id=doc_id,
            source="vision_ocr",
            max_chars=settings.worker_suggestions_max_chars,
        )
    if not vision_text:
        vision_text = join_pages_fn(
            vision_pages,
            max_chars=settings.worker_suggestions_max_chars,
        )
    return vision_text


def process_full_document(
    settings: Settings,
    db: Session,
    doc_id: int,
    *,
    run_id: int | None = None,
    is_cancel_requested_fn: Callable[[Settings], bool],
    process_sync_only_fn: Callable[[Settings, Session, int], None],
    get_document_fn: Callable[[Settings, int], dict[str, Any]],
    get_local_document_fn: Callable[[Session, int], Document | None],
    process_evidence_index_fn: Callable[..., None],
    ensure_ocr_score_fn: Callable[..., object | None],
    collect_page_texts_fn: Callable[..., tuple[Sequence[object], Sequence[object], object]],
    embed_with_pages_fn: Callable[..., None],
    is_large_doc_fn: Callable[[Settings, Document], bool],
    process_page_notes_fn: Callable[..., None],
    process_summary_hierarchical_fn: Callable[..., None],
    get_tags_fn: Callable[[Settings], Sequence[object]],
    get_correspondents_fn: Callable[[Settings], Sequence[object]],
    build_hier_summary_fn: Callable[..., str],
    build_page_notes_fn: Callable[..., str],
    join_pages_fn: Callable[..., str],
    generate_suggestions_fn: Callable[..., dict[str, Any]],
    persist_suggestions_fn: Callable[..., None],
) -> None:
    """Run the full worker document pipeline from sync through embeddings and suggestions."""
    if is_cancel_requested_fn(settings):
        return

    process_sync_only_fn(settings, db, doc_id)
    raw = get_document_fn(settings, doc_id)
    doc = get_local_document_fn(db, doc_id)
    if not doc:
        return

    process_evidence_index_fn(settings, db, doc_id, run_id=run_id)
    ensure_ocr_score_fn(settings, db, doc, "paperless_ocr")

    baseline_pages, vision_pages, _unused = collect_page_texts_fn(
        settings,
        db,
        doc,
        force_vision=True,
    )
    if vision_pages:
        ensure_ocr_score_fn(settings, db, doc, "vision_ocr")
    embed_with_pages_fn(
        settings,
        db,
        doc,
        baseline_pages,
        vision_pages,
        "vision" if vision_pages else "paperless",
        run_id=run_id,
    )

    if is_large_doc_fn(settings, doc):
        process_page_notes_fn(settings, db, doc_id, source="paperless_ocr", run_id=run_id)
        if vision_pages:
            process_page_notes_fn(settings, db, doc_id, source="vision_ocr", run_id=run_id)
            process_summary_hierarchical_fn(
                settings,
                db,
                doc_id,
                source="vision_ocr",
                run_id=run_id,
            )
        else:
            process_summary_hierarchical_fn(
                settings,
                db,
                doc_id,
                source="paperless_ocr",
                run_id=run_id,
            )

    tags = get_tags_fn(settings)
    correspondents = get_correspondents_fn(settings)
    baseline_text = _baseline_suggestion_text(
        settings,
        db,
        doc=doc,
        doc_id=doc_id,
        is_large_doc_fn=is_large_doc_fn,
        build_hier_summary_fn=build_hier_summary_fn,
        build_page_notes_fn=build_page_notes_fn,
    )
    baseline_suggestions = generate_suggestions_fn(
        settings,
        raw,
        baseline_text,
        tags=tags,
        correspondents=correspondents,
    )
    persist_suggestions_fn(
        db,
        doc_id,
        "paperless_ocr",
        baseline_suggestions,
        model_name=settings.text_model,
    )

    if not vision_pages:
        return

    vision_text = _vision_suggestion_text(
        settings,
        db,
        doc=doc,
        doc_id=doc_id,
        vision_pages=vision_pages,
        is_large_doc_fn=is_large_doc_fn,
        build_hier_summary_fn=build_hier_summary_fn,
        build_page_notes_fn=build_page_notes_fn,
        join_pages_fn=join_pages_fn,
    )
    vision_suggestions = generate_suggestions_fn(
        settings,
        raw,
        vision_text,
        tags=tags,
        correspondents=correspondents,
    )
    persist_suggestions_fn(
        db,
        doc_id,
        "vision_ocr",
        vision_suggestions,
        model_name=settings.text_model,
    )
