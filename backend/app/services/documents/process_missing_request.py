from __future__ import annotations

from app.services.pipeline.process_missing import ProcessMissingOptions


def build_process_missing_disabled_payload(*, dry_run: bool) -> dict[str, object]:
    return {
        "enabled": False,
        "docs": 0,
        "enqueued": 0,
        "tasks": 0,
        "dry_run": dry_run,
    }


def build_process_missing_options(
    *,
    dry_run: bool,
    include_sync: bool,
    include_evidence_index: bool,
    include_vision_ocr: bool,
    include_embeddings: bool,
    include_embeddings_paperless: bool,
    include_embeddings_vision: bool,
    include_doc_similarity_index: bool,
    include_page_notes: bool,
    include_summary_hierarchical: bool,
    include_suggestions_paperless: bool,
    include_suggestions_vision: bool,
    embeddings_mode: str,
    limit: int | None,
) -> ProcessMissingOptions:
    if embeddings_mode not in ("auto", "paperless", "vision", "both"):
        raise ValueError("Invalid embeddings_mode")
    if limit is not None and limit < 1:
        raise ValueError("limit must be >= 1")
    return ProcessMissingOptions(
        dry_run=dry_run,
        include_sync=include_sync,
        include_evidence_index=include_evidence_index,
        include_vision_ocr=include_vision_ocr,
        include_embeddings=include_embeddings,
        include_embeddings_paperless=include_embeddings_paperless,
        include_embeddings_vision=include_embeddings_vision,
        include_doc_similarity_index=include_doc_similarity_index,
        include_page_notes=include_page_notes,
        include_summary_hierarchical=include_summary_hierarchical,
        include_suggestions_paperless=include_suggestions_paperless,
        include_suggestions_vision=include_suggestions_vision,
        embeddings_mode=embeddings_mode,
        limit=limit,
    )
