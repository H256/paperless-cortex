from __future__ import annotations

from typing import Any


def test_queue_dlq_endpoints_disabled(api_client: Any) -> None:
    get_resp = api_client.get("/queue/dlq")
    assert get_resp.status_code == 200
    assert get_resp.json()["enabled"] is False

    clear_resp = api_client.post("/queue/dlq/clear")
    assert clear_resp.status_code == 200
    assert clear_resp.json()["enabled"] is False

    requeue_resp = api_client.post("/queue/dlq/requeue", json={"index": 0})
    assert requeue_resp.status_code == 200
    assert requeue_resp.json()["enabled"] is False
