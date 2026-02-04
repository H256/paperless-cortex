from __future__ import annotations

import time
from typing import Any

from app.config import Settings
from app.services import llm_client
from app.services import paperless
from app.services import qdrant


def check_paperless(settings: Settings) -> tuple[bool, str]:
    try:
        paperless.list_documents(settings, page=1, page_size=1)
        return True, "ok"
    except Exception as exc:
        return False, exc.__class__.__name__


def check_qdrant(settings: Settings) -> tuple[bool, str]:
    if not settings.qdrant_url:
        return False, "QDRANT_URL not set"
    try:
        base = qdrant.base_url(settings)
        with qdrant.client(settings, timeout=5) as http:
            response = http.get(f"{base}/healthz", headers=qdrant.headers(settings))
            response.raise_for_status()
        return True, "ok"
    except Exception as exc:
        return False, exc.__class__.__name__


def check_llm(settings: Settings) -> tuple[bool, str]:
    if not settings.llm_base_url:
        return False, "LLM_BASE_URL not set"
    try:
        with llm_client.client(settings, timeout=10) as http:
            response = http.get(
                f"{settings.llm_base_url.rstrip('/')}/v1/models",
                headers=llm_client.headers(settings),
            )
            response.raise_for_status()
        return True, "ok"
    except Exception as exc:
        return False, exc.__class__.__name__


def run_all(settings: Settings) -> list[dict[str, Any]]:
    checks = [
        ("Paperless", check_paperless),
        ("Qdrant", check_qdrant),
        ("LLM", check_llm),
    ]
    results: list[dict[str, Any]] = []
    for name, check in checks:
        start = time.perf_counter()
        ok, detail = check(settings)
        results.append(
            {
                "service": name,
                "status": "UP" if ok else "DOWN",
                "detail": detail,
                "latency_ms": int((time.perf_counter() - start) * 1000),
            }
        )
    return results
