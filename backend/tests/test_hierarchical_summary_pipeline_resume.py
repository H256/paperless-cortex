"""Test that completed sections are persisted in-loop and not re-billed on retry."""

from __future__ import annotations

from typing import Any

from app.models import Document, DocumentPageNote, TaskRun
from app.services.ai.hierarchical_summary_pipeline import HierarchicalSummaryPipeline


def _seed_doc_and_notes(session_factory: Any, *, doc_id: int, pages: list[int]) -> None:
    with session_factory() as db:
        db.add(Document(id=doc_id, title="Test", content="x" * 5000, page_count=len(pages)))
        for page in pages:
            db.add(
                DocumentPageNote(
                    doc_id=doc_id,
                    page=page,
                    source="paperless",
                    notes_text=f"note for page {page}",
                    status="ok",
                )
            )
        db.commit()


def _seed_task_run(session_factory: Any, *, run_id: int, doc_id: int) -> None:
    with session_factory() as db:
        db.add(
            TaskRun(
                id=run_id,
                doc_id=doc_id,
                task="hierarchical_summary",
                source="paperless",
                status="running",
            )
        )
        db.commit()


def test_sections_persisted_in_loop_and_resume_skips_completed(
    session_factory: Any, monkeypatch: Any
) -> None:
    """On first run, sections 1-2 succeed, section 3 fails.
    On retry, sections 1-2 are NOT re-billed (not called again)."""
    import app.services.ai.hierarchical_summary_pipeline as pipe_mod

    class FakeSettings:
        large_doc_page_threshold = 1
        summary_section_pages = 2
        section_summary_max_input_tokens = 99999
        text_model = "test-model"

    settings = FakeSettings()
    doc_id = 501
    run_id = 900
    # 6 pages -> 3 sections of 2 pages each
    _seed_doc_and_notes(session_factory, doc_id=doc_id, pages=[1, 2, 3, 4, 5, 6])
    _seed_task_run(session_factory, run_id=run_id, doc_id=doc_id)

    monkeypatch.setattr(
        pipe_mod, "is_cancel_requested", lambda *_a, **_k: False
    )

    call_log: list[str] = []

    def fake_generate_section(
        _settings: Any, *, section_key: str, page_notes: list[dict[str, Any]]
    ) -> dict[str, Any]:
        call_log.append(section_key)
        if section_key == "5-6":
            raise RuntimeError("provider 500")
        return {"text": f"summary for {section_key}", "section": section_key}

    monkeypatch.setattr(pipe_mod, "generate_section_summary", fake_generate_section)

    def fake_generate_global(
        _settings: Any, *, section_summaries: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return {"summary": "global", "source": "paperless"}

    monkeypatch.setattr(pipe_mod, "generate_global_summary", fake_generate_global)
    monkeypatch.setattr(pipe_mod, "persist_suggestions", lambda *_a, **_k: None)

    # --- First run ---
    with session_factory() as db:
        pipeline = HierarchicalSummaryPipeline(settings, db)
        pipeline.run(doc_id=doc_id, source="paperless", run_id=run_id)

    # Sections 1-2 succeeded, section 3 failed
    assert "1-2" in call_log
    assert "3-4" in call_log
    assert "5-6" in call_log

    # Verify persisted rows
    from app.models import DocumentSectionSummary

    with session_factory() as db:
        rows = (
            db.query(DocumentSectionSummary)
            .filter(
                DocumentSectionSummary.doc_id == doc_id,
                DocumentSectionSummary.source == "paperless",
            )
            .all()
        )
        by_key = {r.section_key: r for r in rows}
        assert by_key["1-2"].status == "ok"
        assert by_key["3-4"].status == "ok"
        assert by_key["5-6"].status == "failed"

    # Verify checkpoint was persisted (failed section 3 → checkpoint stays at 2)
    from app.services.pipeline.worker_checkpoint import get_task_run_checkpoint

    with session_factory() as db:
        cp = get_task_run_checkpoint(db, run_id=run_id)
        assert cp is not None, "checkpoint not persisted after first run"
        assert cp.get("stage") == "summary_sections"
        assert cp.get("current") == 2, f"expected current=2, got {cp.get('current')}"

    # --- Retry: clear call log, section 3 now succeeds ---
    call_log.clear()

    def fake_generate_section_retry(
        _settings: Any, *, section_key: str, page_notes: list[dict[str, Any]]
    ) -> dict[str, Any]:
        call_log.append(section_key)
        return {"text": f"retry summary for {section_key}", "section": section_key}

    monkeypatch.setattr(pipe_mod, "generate_section_summary", fake_generate_section_retry)

    with session_factory() as db:
        pipeline = HierarchicalSummaryPipeline(settings, db)
        pipeline.run(doc_id=doc_id, source="paperless", run_id=run_id)

    # Only section 5-6 should be re-billed (1-2 and 3-4 are already persisted)
    assert call_log == ["5-6"], f"Expected only 5-6 to be re-billed, got {call_log}"

    # Verify the failed section is now ok
    with session_factory() as db:
        row = (
            db.query(DocumentSectionSummary)
            .filter(
                DocumentSectionSummary.doc_id == doc_id,
                DocumentSectionSummary.section_key == "5-6",
                DocumentSectionSummary.source == "paperless",
            )
            .one()
        )
        assert row.status == "ok"
        assert row.summary_text == "retry summary for 5-6"
