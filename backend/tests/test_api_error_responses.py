from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Query

from app.exceptions import DocumentNotFoundError


def test_domain_error_response_includes_error_code_and_request_context(
    api_client: Any,
) -> None:
    import app.main as main

    def _raise_domain_error() -> None:
        raise DocumentNotFoundError(999)

    main.api.add_api_route("/_test/domain-error", _raise_domain_error, methods=["GET"])

    response = api_client.get(
        "/_test/domain-error",
        headers={"X-Request-ID": "req-domain", "X-Correlation-ID": "corr-domain"},
    )

    assert response.status_code == 404
    assert response.headers["X-Error-Code"] == "DOCUMENT_NOT_FOUND"
    assert response.headers["X-Request-ID"] == "req-domain"
    assert response.headers["X-Correlation-ID"] == "corr-domain"
    assert response.json() == {
        "detail": "Document 999 not found",
        "error_code": "DOCUMENT_NOT_FOUND",
        "request_id": "req-domain",
        "correlation_id": "corr-domain",
    }


def test_http_error_response_includes_error_code_and_request_context(api_client: Any) -> None:
    import app.main as main

    def _raise_http_error() -> None:
        raise HTTPException(status_code=409, detail="writeback conflict")

    main.api.add_api_route("/_test/http-error", _raise_http_error, methods=["GET"])

    response = api_client.get(
        "/_test/http-error",
        headers={"X-Request-ID": "req-http", "X-Correlation-ID": "corr-http"},
    )

    assert response.status_code == 409
    assert response.headers["X-Error-Code"] == "CONFLICT"
    assert response.json() == {
        "detail": "writeback conflict",
        "error_code": "CONFLICT",
        "request_id": "req-http",
        "correlation_id": "corr-http",
    }


def test_validation_error_response_includes_error_code_and_request_context(
    api_client: Any,
) -> None:
    import app.main as main

    def _validation_route(limit: int = Query(..., ge=1)) -> dict[str, int]:
        return {"limit": limit}

    main.api.add_api_route("/_test/validation-error", _validation_route, methods=["GET"])

    response = api_client.get(
        "/_test/validation-error",
        params={"limit": 0},
        headers={"X-Request-ID": "req-validation", "X-Correlation-ID": "corr-validation"},
    )

    assert response.status_code == 422
    assert response.headers["X-Error-Code"] == "VALIDATION_ERROR"
    payload = response.json()
    assert payload["error_code"] == "VALIDATION_ERROR"
    assert payload["request_id"] == "req-validation"
    assert payload["correlation_id"] == "corr-validation"
    assert isinstance(payload["detail"], list)
