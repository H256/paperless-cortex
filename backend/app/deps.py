from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.config import Settings, load_settings


def get_settings() -> Settings:
    return load_settings()


def _extract_token(request: Request) -> str:
    """Return the candidate API token from the X-API-Token header or a Bearer header."""
    header_token = request.headers.get("x-api-token")
    if header_token:
        return header_token
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def verify_api_token(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> None:
    """Gate the /api sub-app behind a shared token when ``API_TOKEN`` is configured.

    When ``settings.api.token`` is empty the dependency is a no-op, preserving the
    intended open (single-user, LAN) posture. When it is set, a matching token is
    required via the ``X-API-Token`` header or ``Authorization: Bearer <token>``;
    otherwise the request is rejected with 401. The comparison is constant-time.
    """
    expected: str = settings.api.token
    if not expected:
        return
    provided = _extract_token(request)
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API token",
            headers={"WWW-Authenticate": "Bearer"},
        )
