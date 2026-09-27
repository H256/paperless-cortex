from __future__ import annotations

from typing import Any

from app.models import DocumentSectionSummary
from app.services.ai.hierarchical_storage import replace_section_summaries


def _section_text(
    db: Any, *, doc_id: int, section_key: str, source: str
) -> str | None:
    row = (
        db.query(DocumentSectionSummary)
        .filter(
            DocumentSectionSummary.doc_id == doc_id,
            DocumentSectionSummary.section_key == section_key,
            DocumentSectionSummary.source == source,
        )
        .one_or_none()
    )
    return row.summary_text if row is not None else None


def test_replace_section_summaries_keeps_previous_summary_for_failed_section(
    session_factory: Any,
) -> None:
    # Seed a previous run: two sections, both with summaries.
    with session_factory() as db:
        db.add(
            DocumentSectionSummary(
                doc_id=101,
                section_key="1-5",
                source="paperless",
                summary_text="previous one",
                status="ok",
            )
        )
        db.add(
            DocumentSectionSummary(
                doc_id=101,
                section_key="6-10",
                source="paperless",
                summary_text="previous two",
                status="ok",
            )
        )
        db.commit()

    # Re-run: only section "1-5" succeeded; "6-10" failed and is absent.
    with session_factory() as db:
        replace_section_summaries(
            db,
            doc_id=101,
            source="paperless",
            summaries=[("1-5", {"text": "new one"})],
        )

    # The failed section must retain its previous summary (no data loss),
    # while the successful section is updated.
    with session_factory() as db:
        assert _section_text(db, doc_id=101, section_key="1-5", source="paperless") == (
            "new one"
        )
        assert _section_text(
            db, doc_id=101, section_key="6-10", source="paperless"
        ) == "previous two"


def test_replace_section_summaries_replaces_all_provided_sections(session_factory: Any) -> None:
    # Baseline: both sections exist.
    with session_factory() as db:
        db.add(
            DocumentSectionSummary(
                doc_id=202,
                section_key="1-5",
                source="vision",
                summary_text="old one",
                status="ok",
            )
        )
        db.add(
            DocumentSectionSummary(
                doc_id=202,
                section_key="6-10",
                source="vision",
                summary_text="old two",
                status="ok",
            )
        )
        db.commit()

    # Re-run: both sections succeed and are both provided.
    with session_factory() as db:
        replace_section_summaries(
            db,
            doc_id=202,
            source="vision",
            summaries=[("1-5", {"text": "new one"}), ("6-10", {"text": "new two"})],
        )

    with session_factory() as db:
        assert _section_text(db, doc_id=202, section_key="1-5", source="vision") == (
            "new one"
        )
        assert _section_text(db, doc_id=202, section_key="6-10", source="vision") == (
            "new two"
        )
