from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import DocumentPageNote, DocumentSectionSummary
from app.services.documents import get_document_or_none
from app.services.ai.hierarchical_summary import (
    generate_global_summary,
    generate_section_summary,
    group_notes_into_sections,
    is_large_document,
    replace_section_summaries,
)
from app.services.queue import is_cancel_requested
from app.services.ai.suggestion_store import persist_suggestions
from app.services.worker_checkpoint import (
    get_task_run_checkpoint,
    resume_stage_current,
    set_task_checkpoint,
)

logger = logging.getLogger(__name__)


def _fallback_global_payload(exc: Exception) -> dict[str, Any]:
    return {
        "summary": "",
        "executive_summary": "",
        "key_facts": [],
        "key_dates": [],
        "key_entities": [],
        "key_numbers": [],
        "open_questions": [],
        "confidence_notes": [f"global_summary_error:{str(exc)[:200]}"],
    }


def _load_page_notes(
    db: Session,
    *,
    doc_id: int,
    source: str,
) -> tuple[str, list[tuple[int, dict[str, Any]]]]:
    note_rows = (
        db.query(DocumentPageNote)
        .filter(
            DocumentPageNote.doc_id == doc_id,
            DocumentPageNote.source == source,
            DocumentPageNote.status == "ok",
        )
        .order_by(DocumentPageNote.page.asc())
        .all()
    )
    resolved_source = source
    if not note_rows and source != "paperless_ocr":
        note_rows = (
            db.query(DocumentPageNote)
            .filter(
                DocumentPageNote.doc_id == doc_id,
                DocumentPageNote.source == "paperless_ocr",
                DocumentPageNote.status == "ok",
            )
            .order_by(DocumentPageNote.page.asc())
            .all()
        )
        resolved_source = "paperless_ocr"

    page_to_note: dict[int, dict[str, Any]] = {}
    for row in note_rows:
        raw = (row.notes_text or "").strip()
        if not raw:
            continue
        page_to_note[int(row.page)] = {"page": int(row.page), "text": raw}
    notes = sorted(page_to_note.items(), key=lambda item: item[0])
    return resolved_source, notes


def _load_persisted_sections(
    db: Session,
    *,
    doc_id: int,
    source: str,
) -> dict[str, dict[str, Any]]:
    persisted_rows = (
        db.query(DocumentSectionSummary)
        .filter(
            DocumentSectionSummary.doc_id == doc_id,
            DocumentSectionSummary.source == source,
            DocumentSectionSummary.status == "ok",
        )
        .all()
    )
    payloads: dict[str, dict[str, Any]] = {}
    for row in persisted_rows:
        raw_summary = (row.summary_text or "").strip()
        if not raw_summary:
            continue
        payloads[str(row.section_key)] = {
            "section": str(row.section_key),
            "text": raw_summary,
            "summary": raw_summary,
            "key_facts": [],
            "key_dates": [],
            "key_entities": [],
            "key_numbers": [],
            "open_questions": [],
            "confidence_notes": [],
        }
    return payloads


class HierarchicalSummaryPipeline:
    def __init__(self, settings: Settings, db: Session):
        self.settings = settings
        self.db = db

    def run(self, *, doc_id: int, source: str, run_id: int | None = None) -> None:
        if is_cancel_requested(self.settings):
            logger.info("Worker cancel requested; abort hierarchical summary doc=%s", doc_id)
            return

        doc = get_document_or_none(self.db, doc_id)
        if not doc:
            return
        if not is_large_document(
            page_count=doc.page_count,
            total_text=doc.content,
            threshold_pages=self.settings.large_doc_page_threshold,
        ):
            logger.info("Hierarchical summary skipped (small doc) doc=%s", doc_id)
            return

        resolved_source, notes = _load_page_notes(self.db, doc_id=doc_id, source=source)
        if not notes:
            logger.info("Hierarchical summary skipped (no page notes) doc=%s", doc_id)
            return

        sections = group_notes_into_sections(
            notes,
            max_pages=self.settings.summary_section_pages,
            max_input_tokens=self.settings.section_summary_max_input_tokens,
        )
        checkpoint = get_task_run_checkpoint(self.db, run_id=run_id)
        resume_current = resume_stage_current(
            checkpoint,
            stage="summary_sections",
            source=resolved_source,
            total=len(sections),
        )
        start_index = max(0, min(resume_current, len(sections)))

        persisted_by_key: dict[str, dict[str, Any]] = {}
        if start_index > 0:
            persisted_by_key = _load_persisted_sections(
                self.db,
                doc_id=doc_id,
                source=resolved_source,
            )
            required_keys = [str(sections[i][0]) for i in range(start_index)]
            if not all(key in persisted_by_key for key in required_keys):
                logger.info(
                    "Summary resume reset doc=%s source=%s reason=missing_persisted_sections",
                    doc_id,
                    resolved_source,
                )
                start_index = 0
                persisted_by_key = {}
            else:
                logger.info(
                    "Summary resume doc=%s source=%s start=%s total=%s",
                    doc_id,
                    resolved_source,
                    start_index,
                    len(sections),
                )

        set_task_checkpoint(
            self.db,
            run_id=run_id,
            stage="summary_sections",
            current=start_index,
            total=len(sections),
            extra={"source": resolved_source, "resumed": start_index > 0},
        )

        section_payloads: list[tuple[str, dict[str, Any]]] = []
        if start_index > 0:
            for section_key, _ in sections[:start_index]:
                cached = persisted_by_key.get(str(section_key))
                if cached is not None:
                    section_payloads.append((section_key, cached))

        for section_index, (section_key, page_notes) in enumerate(
            sections[start_index:],
            start=start_index + 1,
        ):
            if is_cancel_requested(self.settings):
                logger.info("Worker cancel requested; stop section summaries doc=%s", doc_id)
                return
            if not page_notes:
                continue
            try:
                section_summary = generate_section_summary(
                    self.settings,
                    section_key=section_key,
                    page_notes=page_notes,
                )
                section_payloads.append((section_key, section_summary))
            except Exception as exc:
                logger.warning("Section summary failed doc=%s section=%s error=%s", doc_id, section_key, exc)
            finally:
                set_task_checkpoint(
                    self.db,
                    run_id=run_id,
                    stage="summary_sections",
                    current=section_index,
                    total=len(sections),
                    extra={"source": resolved_source},
                )

        if not section_payloads:
            return

        replace_section_summaries(
            self.db,
            doc_id=doc_id,
            source=resolved_source,
            summaries=section_payloads,
            model_name=self.settings.text_model,
        )

        try:
            global_payload = generate_global_summary(
                self.settings,
                section_summaries=[payload for _, payload in section_payloads],
            )
        except Exception as exc:
            global_payload = _fallback_global_payload(exc)

        global_payload["source"] = resolved_source
        persist_suggestions(
            self.db,
            doc_id,
            "hier_summary",
            global_payload,
            model_name=self.settings.text_model,
            action="hierarchical_summary_generate",
        )
