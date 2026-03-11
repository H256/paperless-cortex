from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings


def build_task_sequence(
    settings: Settings,
    doc_id: int,
    *,
    include_sync: bool = False,
    include_vision_ocr: bool | None = None,
    force: bool = False,
) -> list[dict]:
    tasks: list[dict] = []
    normalized_id = int(doc_id)
    if include_sync:
        tasks.append({"doc_id": normalized_id, "task": "sync"})
    tasks.append({"doc_id": normalized_id, "task": "evidence_index"})
    use_vision = settings.enable_vision_ocr if include_vision_ocr is None else include_vision_ocr
    if use_vision:
        tasks.append({"doc_id": normalized_id, "task": "vision_ocr", "force": force})
        tasks.append({"doc_id": normalized_id, "task": "embeddings_vision"})
        tasks.append({"doc_id": normalized_id, "task": "similarity_index"})
        tasks.append({"doc_id": normalized_id, "task": "page_notes_vision"})
        tasks.append({"doc_id": normalized_id, "task": "summary_hierarchical", "source": "vision_ocr"})
        tasks.append({"doc_id": normalized_id, "task": "suggestions_paperless"})
        tasks.append({"doc_id": normalized_id, "task": "suggestions_vision"})
    else:
        tasks.append({"doc_id": normalized_id, "task": "embeddings_paperless"})
        tasks.append({"doc_id": normalized_id, "task": "similarity_index"})
        tasks.append({"doc_id": normalized_id, "task": "page_notes_paperless"})
        tasks.append({"doc_id": normalized_id, "task": "summary_hierarchical", "source": "paperless_ocr"})
        tasks.append({"doc_id": normalized_id, "task": "suggestions_paperless"})
    return tasks
