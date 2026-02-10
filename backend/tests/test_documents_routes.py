from __future__ import annotations


def test_get_local_document_missing(api_client):
    response = api_client.get("/documents/999/local")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "missing"


def test_process_missing_queue_disabled(api_client):
    response = api_client.post("/documents/process-missing", params={"dry_run": True})
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["dry_run"] is True


def test_get_document_suggestions_empty(api_client, monkeypatch):
    from app.services import paperless
    from app.services import meta_cache

    monkeypatch.setattr(paperless, "get_document", lambda *args, **kwargs: {"content": ""})
    monkeypatch.setattr(meta_cache, "get_cached_tags", lambda *args, **kwargs: [])
    monkeypatch.setattr(meta_cache, "get_cached_correspondents", lambda *args, **kwargs: [])

    response = api_client.get("/documents/123/suggestions")
    assert response.status_code == 200
    payload = response.json()
    assert payload["doc_id"] == 123
    assert payload["suggestions"] == {}
    assert payload["suggestions_meta"] == {}


def test_cleanup_texts_queue_disabled(api_client):
    response = api_client.post(
        "/documents/cleanup-texts",
        json={"enqueue": True, "clear_first": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["queued"] is False
    assert payload["enqueued"] == 0
