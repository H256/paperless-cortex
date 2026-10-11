from __future__ import annotations

from typing import Any

from app.services.runtime.model_providers import validate_provider_base_url


def test_validate_provider_base_url_accepts_http_and_https() -> None:
    assert validate_provider_base_url("http://llm.elysium.lan:8000/") == "http://llm.elysium.lan:8000"
    assert validate_provider_base_url("https://api.openai.com/v1") == "https://api.openai.com/v1"


def test_validate_provider_base_url_accepts_public_ip_host() -> None:
    assert validate_provider_base_url("http://192.168.1.10:8000") == "http://192.168.1.10:8000"


def test_validate_provider_base_url_rejects_none_and_empty() -> None:
    assert validate_provider_base_url(None) is None
    assert validate_provider_base_url("   ") is None


def test_validate_provider_base_url_rejects_non_http_schemes() -> None:
    for url in ("file:///etc/passwd", "ftp://host", "gopher://host"):
        try:
            validate_provider_base_url(url)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {url}")


def test_validate_provider_base_url_rejects_loopback_and_link_local() -> None:
    for url in (
        "http://127.0.0.1:5432",
        "http://localhost:5432",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]:8000",
        "http://0.0.0.0:8000",
    ):
        try:
            validate_provider_base_url(url)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {url}")


def test_validate_provider_base_url_rejects_missing_host() -> None:
    try:
        validate_provider_base_url("http://")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for missing host")


def test_discover_route_rejects_loopback_without_server_request(api_client: Any) -> None:
    response = api_client.post(
        "/settings/model-providers/discover",
        json={"base_url": "http://127.0.0.1:5432", "api_key": "secret"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert "blocked" in payload["detail"] or "loopback" in payload["detail"].lower()


def test_discover_route_rejects_non_http_scheme(api_client: Any) -> None:
    response = api_client.post(
        "/settings/model-providers/discover",
        json={"base_url": "file:///etc/passwd"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False


def test_put_route_rejects_loopback_base_url(api_client: Any, monkeypatch: Any) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "http://llm-default")

    response = api_client.put(
        "/settings/model-providers",
        json={
            "items": [
                {
                    "role": "chat",
                    "base_url": "http://127.0.0.1:8000",
                    "model": "gpt-live",
                    "api_key": "super-secret-key",
                }
            ]
        },
    )

    assert response.status_code == 400
    assert "blocked" in response.json()["detail"] or "loopback" in response.json()["detail"].lower()


def test_put_route_rejects_non_http_scheme(api_client: Any, monkeypatch: Any) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "http://llm-default")

    response = api_client.put(
        "/settings/model-providers",
        json={
            "items": [
                {
                    "role": "chat",
                    "base_url": "ftp://host",
                    "model": "gpt-live",
                }
            ]
        },
    )

    assert response.status_code == 400


def test_put_route_still_accepts_valid_public_url(api_client: Any, monkeypatch: Any) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "http://llm-default")

    response = api_client.put(
        "/settings/model-providers",
        json={
            "items": [
                {
                    "role": "chat",
                    "base_url": "https://api.example.com/v1",
                    "model": "gpt-live",
                    "api_key": "super-secret-key",
                }
            ]
        },
    )

    assert response.status_code == 200
    chat_item = next(item for item in response.json()["items"] if item["role"] == "chat")
    assert chat_item["base_url"] == "https://api.example.com/v1"
