from __future__ import annotations

from types import SimpleNamespace

from app.config import load_settings
from app.services.pipeline_planner import PipelineOptions, evaluate_doc_pipeline, post_sync_followup_tasks


def _base_cache(doc_id: int) -> dict:
    return {
        "embeddings": {doc_id: "paperless"},
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
