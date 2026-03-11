from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.models import Document
from app.services.pipeline.pipeline_planner import (
    PipelineOptions,
    collect_pipeline_cache,
    evaluate_doc_pipeline,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session

    from app.config import Settings


@dataclass(frozen=True)
class ProcessMissingOptions:
    dry_run: bool
    include_sync: bool
    include_evidence_index: bool
    include_vision_ocr: bool
    include_embeddings: bool
    include_embeddings_paperless: bool
    include_embeddings_vision: bool
    include_doc_similarity_index: bool
    include_page_notes: bool
    include_summary_hierarchical: bool
    include_suggestions_paperless: bool
    include_suggestions_vision: bool
    embeddings_mode: str
    limit: int | None


def _should_skip_doc(doc: Document) -> bool:
    return bool(doc.deleted_at and str(doc.deleted_at).startswith("DELETED in Paperless"))


def process_missing_documents(
    *,
    settings: Settings,
    db: Session,
    options: ProcessMissingOptions,
    run_sync_documents: Callable[..., Any],
    enqueue_task_sequence: Callable[[Settings, list[dict[str, Any]]], int],
) -> dict[str, Any]:
    if options.include_sync:
        run_sync_documents(
            page_size=200,
            incremental=True,
            embed=False,
            page=1,
            page_only=False,
            force_embed=False,
            mark_missing=True,
            insert_only=True,
            settings=settings,
            db=db,
        )

    docs_query = db.query(Document)
    if options.include_vision_ocr:
        docs_query = docs_query.order_by(
            Document.page_count.is_(None).asc(),
            Document.page_count.asc(),
            Document.id.asc(),
        )
    else:
        docs_query = docs_query.order_by(Document.id.asc())
    pipeline_options = PipelineOptions(
        include_sync=options.include_sync,
        include_evidence_index=options.include_evidence_index,
        include_vision_ocr=options.include_vision_ocr,
        include_embeddings=options.include_embeddings,
        include_embeddings_paperless=options.include_embeddings_paperless,
        include_embeddings_vision=options.include_embeddings_vision,
        include_doc_similarity_index=options.include_doc_similarity_index,
        include_page_notes=options.include_page_notes,
        include_summary_hierarchical=options.include_summary_hierarchical,
        include_suggestions_paperless=options.include_suggestions_paperless,
        include_suggestions_vision=options.include_suggestions_vision,
        embeddings_mode=options.embeddings_mode,
    )

    enqueued_docs = 0
    enqueued_tasks = 0
    missing_docs = 0
    missing_vision = 0
    missing_embeddings = 0
    missing_embeddings_paperless = 0
    missing_embeddings_vision = 0
    missing_similarity_index = 0
    missing_page_notes = 0
    missing_summary_hier = 0
    missing_evidence_index = 0
    missing_sugg_p = 0
    missing_sugg_v = 0
    checked_docs = 0
    selected_for_run = 0
    missing_by_step = {"paperless": 0, "vision": 0, "large": 0, "similarity": 0}
    preview_docs: list[dict[str, Any]] = []
    preview_docs_limit = 20
    batch_docs: list[Document] = []
    batch_size = 250

    def _process_batch(docs_batch: list[Document]) -> None:
        nonlocal checked_docs
        nonlocal missing_docs
        nonlocal missing_vision
        nonlocal missing_embeddings
        nonlocal missing_embeddings_paperless
        nonlocal missing_embeddings_vision
        nonlocal missing_similarity_index
        nonlocal missing_page_notes
        nonlocal missing_summary_hier
        nonlocal missing_evidence_index
        nonlocal missing_sugg_p
        nonlocal missing_sugg_v
        nonlocal selected_for_run
        nonlocal enqueued_docs
        nonlocal enqueued_tasks
        if not docs_batch:
            return
        cache = collect_pipeline_cache(db, doc_ids={int(doc.id) for doc in docs_batch}, settings=settings)
        for doc in docs_batch:
            if _should_skip_doc(doc):
                continue
            checked_docs += 1
            evaluation = evaluate_doc_pipeline(
                doc=doc,
                settings=settings,
                cache=cache,
                options=pipeline_options,
            )
            tasks = evaluation["tasks"]
            if evaluation["needs_vision"]:
                missing_vision += 1
            if evaluation["needs_embeddings"]:
                missing_embeddings += 1
                if evaluation["needs_embeddings_vision"]:
                    missing_embeddings_vision += 1
                if evaluation["needs_embeddings_paperless"]:
                    missing_embeddings_paperless += 1
            if pipeline_options.include_page_notes and evaluation["needs_page_notes"]:
                missing_page_notes += 1
            if evaluation["needs_summary_hierarchical"]:
                missing_summary_hier += 1
            if evaluation["needs_evidence_index"]:
                missing_evidence_index += 1
            if evaluation["needs_suggestions_paperless"]:
                missing_sugg_p += 1
            if evaluation["needs_suggestions_vision"]:
                missing_sugg_v += 1
            if evaluation.get("needs_doc_similarity_index"):
                missing_similarity_index += 1
            missing_steps: list[str] = []
            if evaluation["needs_embeddings_paperless"] or evaluation["needs_suggestions_paperless"]:
                missing_steps.append("paperless")
                missing_by_step["paperless"] += 1
            if (
                evaluation["needs_vision"]
                or evaluation["needs_embeddings_vision"]
                or evaluation["needs_suggestions_vision"]
            ):
                missing_steps.append("vision")
                missing_by_step["vision"] += 1
            if evaluation["needs_page_notes"] or evaluation["needs_summary_hierarchical"]:
                missing_steps.append("large")
                missing_by_step["large"] += 1
            if evaluation.get("needs_doc_similarity_index"):
                missing_steps.append("similarity")
                missing_by_step["similarity"] = int(missing_by_step.get("similarity", 0)) + 1
            if tasks:
                missing_docs += 1
                if len(preview_docs) < preview_docs_limit:
                    preview_docs.append(
                        {
                            "doc_id": int(doc.id),
                            "title": str(doc.title or f"Document {doc.id}"),
                            "missing_steps": missing_steps,
                            "missing_tasks": [
                                str(task.get("task") or "")
                                for task in tasks
                                if isinstance(task, dict)
                            ],
                        }
                    )
            if options.limit is not None and selected_for_run >= options.limit:
                continue
            if tasks:
                selected_for_run += 1
                if not options.dry_run:
                    enqueued_docs += 1
                    enqueued_tasks += enqueue_task_sequence(settings, tasks)

    for doc in docs_query.yield_per(batch_size):
        batch_docs.append(doc)
        if len(batch_docs) >= batch_size:
            _process_batch(batch_docs)
            batch_docs = []
    _process_batch(batch_docs)

    return {
        "enabled": True,
        "docs": checked_docs,
        "missing_docs": missing_docs,
        "missing_vision_ocr": missing_vision,
        "missing_embeddings": missing_embeddings,
        "missing_embeddings_paperless": missing_embeddings_paperless,
        "missing_embeddings_vision": missing_embeddings_vision,
        "missing_doc_similarity_index": missing_similarity_index,
        "missing_page_notes": missing_page_notes,
        "missing_summary_hierarchical": missing_summary_hier,
        "missing_evidence_index": missing_evidence_index,
        "missing_suggestions_paperless": missing_sugg_p,
        "missing_suggestions_vision": missing_sugg_v,
        "missing_by_step": missing_by_step,
        "preview_docs": preview_docs,
        "selected": selected_for_run,
        "enqueued": enqueued_docs,
        "tasks": enqueued_tasks,
        "dry_run": options.dry_run,
    }
