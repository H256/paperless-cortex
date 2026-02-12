from __future__ import annotations

from app.worker import _resume_stage_current


def test_resume_stage_current_uses_resume_from_payload():
    checkpoint = {
        "stage": "resume",
        "resume_from": {
            "stage": "embedding_chunks",
            "source": "vision",
            "current": 24,
            "total": 100,
        },
    }
    assert _resume_stage_current(checkpoint, stage="embedding_chunks", source="vision", total=100) == 24


def test_resume_stage_current_rejects_mismatched_total():
    checkpoint = {
        "stage": "resume",
        "resume_from": {
            "stage": "page_notes",
            "source": "vision_ocr",
            "current": 18,
            "total": 30,
        },
    }
    assert _resume_stage_current(checkpoint, stage="page_notes", source="vision_ocr", total=37) == 0


def test_resume_stage_current_allows_exact_stage_payload():
    checkpoint = {"stage": "vision_ocr", "current": 7, "total": 20}
    assert _resume_stage_current(checkpoint, stage="vision_ocr", total=20) == 7

