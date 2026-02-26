from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from app.config import load_settings
from app.models import TaskRun
from app.services.pipeline_planner import (
    PipelineOptions,
    collect_pipeline_cache,
    evaluate_doc_pipeline,
    post_sync_followup_tasks,
)


def _base_cache(doc_id: int) -> dict:
    return {
        "embeddings": {doc_id: "paperless"},
        "embedded_at_by_doc": {},
        "similarity_indexed_at_by_doc": {},
        "suggestions": set(),
        "vision_latest": {},
        "vision_pages_by_doc": {},
        "page_notes_by_doc_source": {},
        "anchors_by_doc": {},
        "hier_summaries": {},
    }


def test_evaluate_doc_pipeline_marks_similarity_index_missing():
    settings = load_settings()
    doc = SimpleNamespace(id=11, page_count=1, content="sample text")
    cache = _base_cache(doc.id)

    result = evaluate_doc_pipeline(
        doc=doc,
        settings=settings,
        cache=cache,
        options=PipelineOptions(
            include_sync=False,
            include_evidence_index=False,
            include_vision_ocr=False,
            include_embeddings=False,
            include_suggestions_paperless=False,
            include_suggestions_vision=False,
            include_page_notes=False,
            include_summary_hierarchical=False,
            include_doc_similarity_index=True,
        ),
    )

    assert result["needs_doc_similarity_index"] is True
    assert any(str(task.get("task")) == "similarity_index" for task in result["tasks"])


def test_evaluate_doc_pipeline_skips_similarity_index_when_step_disabled():
    settings = load_settings()
    doc = SimpleNamespace(id=12, page_count=1, content="sample text")
    cache = _base_cache(doc.id)
    result = evaluate_doc_pipeline(
        doc=doc,
        settings=settings,
        cache=cache,
        options=PipelineOptions(
            include_sync=False,
            include_evidence_index=False,
            include_vision_ocr=False,
            include_embeddings=False,
            include_suggestions_paperless=False,
            include_suggestions_vision=False,
            include_page_notes=False,
            include_summary_hierarchical=False,
            include_doc_similarity_index=False,
        ),
    )

    assert result["needs_doc_similarity_index"] is False
    assert all(str(task.get("task")) != "similarity_index" for task in result["tasks"])


def test_evaluate_doc_pipeline_skips_similarity_when_already_fresh():
    settings = load_settings()
    doc = SimpleNamespace(id=13, page_count=1, content="sample text")
    cache = _base_cache(doc.id)
    cache["embedded_at_by_doc"][doc.id] = datetime(2026, 2, 26, 10, 0, 0)
    cache["similarity_indexed_at_by_doc"][doc.id] = datetime(2026, 2, 26, 10, 1, 0)
    result = evaluate_doc_pipeline(
        doc=doc,
        settings=settings,
        cache=cache,
        options=PipelineOptions(
            include_sync=False,
            include_evidence_index=False,
            include_vision_ocr=False,
            include_embeddings=False,
            include_suggestions_paperless=False,
            include_suggestions_vision=False,
            include_page_notes=False,
            include_summary_hierarchical=False,
            include_doc_similarity_index=True,
        ),
    )

    assert result["needs_doc_similarity_index"] is False
    assert all(str(task.get("task")) != "similarity_index" for task in result["tasks"])


def test_post_sync_followup_tasks_include_similarity_index():
    settings = load_settings()
    tasks = post_sync_followup_tasks(
        42,
        settings=settings,
        options=PipelineOptions(
            include_sync=False,
            include_evidence_index=False,
            include_vision_ocr=False,
            include_embeddings=True,
            include_embeddings_paperless=True,
            include_embeddings_vision=False,
            include_page_notes=False,
            include_summary_hierarchical=False,
            include_suggestions_paperless=False,
            include_suggestions_vision=False,
            include_doc_similarity_index=True,
        ),
    )
    assert any(str(task.get("task")) == "similarity_index" for task in tasks)


def test_post_sync_followup_tasks_skip_similarity_when_embeddings_disabled():
    settings = load_settings()
    tasks = post_sync_followup_tasks(
        42,
        settings=settings,
        options=PipelineOptions(
            include_sync=False,
            include_evidence_index=False,
            include_vision_ocr=False,
            include_embeddings=False,
            include_embeddings_paperless=True,
            include_embeddings_vision=False,
            include_page_notes=False,
            include_summary_hierarchical=False,
            include_suggestions_paperless=False,
            include_suggestions_vision=False,
            include_doc_similarity_index=True,
        ),
    )
    assert all(str(task.get("task")) != "similarity_index" for task in tasks)


def test_collect_pipeline_cache_reads_completed_similarity_runs(session_factory):
    with session_factory() as db:
        db.add(
            TaskRun(
                doc_id=1971,
                task="similarity_index",
                source=None,
                status="completed",
                worker_id="worker:test",
                attempt=1,
                started_at="2026-02-26T20:05:00+00:00",
                finished_at="2026-02-26T20:05:10+00:00",
                created_at="2026-02-26T20:05:00+00:00",
                updated_at="2026-02-26T20:05:10+00:00",
            )
        )
        db.commit()

    with session_factory() as db:
        cache = collect_pipeline_cache(db, doc_ids={1971}, settings=load_settings())

    assert 1971 in cache["similarity_indexed_at_by_doc"]


def test_evaluate_doc_pipeline_marks_similarity_missing_when_embeddings_missing():
    settings = load_settings()
    doc = SimpleNamespace(id=17, page_count=1, content="sample text")
    cache = {
        "embeddings": {},
        "embedded_at_by_doc": {},
        "similarity_indexed_at_by_doc": {},
        "suggestions": set(),
        "vision_latest": {},
        "vision_pages_by_doc": {},
        "page_notes_by_doc_source": {},
        "anchors_by_doc": {},
        "hier_summaries": {},
    }

    result = evaluate_doc_pipeline(
        doc=doc,
        settings=settings,
        cache=cache,
        options=PipelineOptions(
            include_sync=False,
            include_evidence_index=False,
            include_vision_ocr=False,
            include_embeddings=True,
            include_embeddings_paperless=True,
            include_embeddings_vision=False,
            include_suggestions_paperless=False,
            include_suggestions_vision=False,
            include_page_notes=False,
            include_summary_hierarchical=False,
            include_doc_similarity_index=True,
            embeddings_mode="paperless",
        ),
    )

    assert result["needs_embeddings"] is True
    assert result["needs_doc_similarity_index"] is True
    task_names = [str(task.get("task")) for task in result["tasks"]]
    assert "embeddings_paperless" in task_names
    assert "similarity_index" in task_names
