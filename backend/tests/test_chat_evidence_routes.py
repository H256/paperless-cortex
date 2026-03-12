from __future__ import annotations

from typing import Any


def test_resolve_evidence_returns_matches(api_client: Any) -> None:
    payload = {
        "citations": [
            {"doc_id": 1756, "page": 1, "snippet": "foo"},
            {"doc_id": 1756, "page": 2, "snippet": "bar", "bbox": [1, 2, 3, 4]},
        ],
        "max_pages": 3,
    }
    response = api_client.post("/chat/resolve-evidence", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert len(data["matches"]) == 2
    assert data["matches"][0]["status"] in {"no_match", "ok", "error"}
    assert data["matches"][1]["status"] == "ok"
    assert data["matches"][1]["bbox"] == [1, 2, 3, 4]


def test_resolve_evidence_caps_to_max_pages(api_client: Any) -> None:
    payload = {
        "citations": [
            {"doc_id": 1, "page": 1, "snippet": "a"},
            {"doc_id": 1, "page": 2, "snippet": "b"},
            {"doc_id": 1, "page": 3, "snippet": "c"},
            {"doc_id": 1, "page": 4, "snippet": "d"},
        ],
        "max_pages": 2,
    }
    response = api_client.post("/chat/resolve-evidence", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2


def test_resolve_evidence_limits_unique_pages_not_raw_items(api_client: Any) -> None:
    payload = {
        "citations": [
            {"doc_id": 1, "page": 1, "snippet": "first"},
            {"doc_id": 1, "page": 1, "snippet": "same page duplicate"},
            {"doc_id": 1, "page": 2, "snippet": "second page"},
            {"doc_id": 1, "page": 3, "snippet": "third page"},
        ],
        "max_pages": 2,
    }
    response = api_client.post("/chat/resolve-evidence", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 3
    pages = [item["page"] for item in data["matches"]]
    assert pages == [1, 1, 2]


def test_resolve_evidence_marks_invalid_bbox(api_client: Any) -> None:
    payload = {
        "citations": [
            {"doc_id": 1, "page": 1, "snippet": "x", "bbox": [10, 10, 5, 5]},
        ],
        "max_pages": 3,
    }
    response = api_client.post("/chat/resolve-evidence", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["matches"][0]["status"] == "error"
    assert data["matches"][0]["error"] == "invalid_bbox"
