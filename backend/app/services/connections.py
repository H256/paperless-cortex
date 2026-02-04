from __future__ import annotations

import time
from typing import Any

from app.config import Settings
from app.services import paperless
from app.services import ollama
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


def check_ollama(settings: Settings) -> tuple[bool, str]:
    if not settings.ollama_base_url or not settings.ollama_model:
        return False, "OLLAMA_BASE_URL/OLLAMA_MODEL not set"
    try:
        base = ollama.base_url(settings)
        with ollama.client(settings, timeout=15) as http:
            response = http.post(
                f"{base}/api/generate",
                json={"model": settings.ollama_model, "prompt": "warum ist der himmel blau?", "stream": False},
            )
            response.raise_for_status()
        return True, "ok"
    except Exception as exc:
        return False, exc.__class__.__name__


def run_all(settings: Settings) -> list[dict[str, Any]]:
    checks = [
        ("Paperless", check_paperless),
        ("Qdrant", check_qdrant),
        ("Ollama", check_ollama),
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
