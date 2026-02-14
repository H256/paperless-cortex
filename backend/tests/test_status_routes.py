from __future__ import annotations


def test_status_includes_evidence_runtime_config(api_client):
    response = api_client.get("/status")
    assert response.status_code == 200
    payload = response.json()
    assert "evidence_max_pages" in payload
    assert "evidence_min_snippet_chars" in payload
