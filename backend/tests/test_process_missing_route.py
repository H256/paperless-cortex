from __future__ import annotations

from typing import Any


def test_process_missing_route_returns_disabled_when_queue_off(api_client: Any) -> None:
    response = api_client.post("/documents/process-missing")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["docs"] == 0
    assert payload["enqueued"] == 0
    assert payload["tasks"] == 0
    assert payload["dry_run"] is False


def test_process_missing_route_forwards_options(api_client: Any, monkeypatch: Any) -> None:
    from app.routes import documents_actions

    monkeypatch.setenv("QUEUE_ENABLED", "1")
    monkeypatch.setattr(documents_actions, "require_queue_enabled", lambda _settings: True)

    captured: dict[str, Any] = {}

    def _process_missing_documents(
        *,
        settings: Any,
        db: Any,
        options: Any,
        run_sync_documents: Any,
        enqueue_task_sequence: Any,
    ) -> dict[str, Any]:
        captured["settings"] = settings
        captured["db"] = db
        captured["options"] = options
        captured["run_sync_documents"] = run_sync_documents
        captured["enqueue_task_sequence"] = enqueue_task_sequence
        return {"enabled": True, "docs": 3, "missing_docs": 2, "selected": 2, "enqueued": 2, "tasks": 4, "dry_run": False}

    monkeypatch.setattr(documents_actions, "process_missing_documents", _process_missing_documents)

    response = api_client.post(
        "/documents/process-missing",
        params={
            "dry_run": "false",
            "include_sync": "false",
            "include_embeddings": "false",
            "include_embeddings_paperless": "false",
            "include_embeddings_vision": "true",
            "include_page_notes": "false",
            "include_summary_hierarchical": "false",
            "include_suggestions_paperless": "false",
            "include_suggestions_vision": "true",
            "embeddings_mode": "vision",
            "limit": 3,
        },
    )
    assert response.status_code == 200
    assert response.json()["tasks"] == 4

    options = captured["options"]
    assert options.dry_run is False
    assert options.include_sync is False
    assert options.include_embeddings is False
    assert options.include_embeddings_paperless is False
    assert options.include_embeddings_vision is True
    assert options.include_page_notes is False
    assert options.include_summary_hierarchical is False
    assert options.include_suggestions_paperless is False
    assert options.include_suggestions_vision is True
    assert options.embeddings_mode == "vision"
    assert options.limit == 3
    assert callable(captured["run_sync_documents"])
    assert callable(captured["enqueue_task_sequence"])


def test_process_missing_route_rejects_invalid_limit(api_client: Any, monkeypatch: Any) -> None:
    from app.routes import documents_actions

    monkeypatch.setenv("QUEUE_ENABLED", "1")
    monkeypatch.setattr(documents_actions, "require_queue_enabled", lambda _settings: True)

    response = api_client.post("/documents/process-missing", params={"limit": 0})
    assert response.status_code == 400
    assert response.json()["detail"] == "limit must be >= 1"

