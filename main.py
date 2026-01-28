from __future__ import annotations

import asyncio
import os
import time
from urllib.parse import urlparse
from typing import Any

import httpx
import psycopg
import redis
from dotenv import load_dotenv
from nicegui import ui


load_dotenv()


def _parse_host_port(value: str | None, default_port: int) -> tuple[str, int] | None:
    if not value:
        return None
    if "://" in value:
        value = value.split("://", 1)[1]
    host = value
    port = default_port
    if ":" in value:
        host, port_str = value.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            port = default_port
    return host, port


def _http_base(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("http://") or value.startswith("https://"):
        return value.rstrip("/")
    return f"http://{value}".rstrip("/")


def _paperless_api_base(value: str | None) -> str | None:
    base = _http_base(value)
    if not base:
        return None
    if base.endswith("/api"):
        return base
    return f"{base}/api"


def _get_database_url() -> str | None:
    return os.getenv("DATABASE_URL")


def _format_host_port_from_url(value: str) -> str:
    parsed = urlparse(value)
    host = parsed.hostname or "unknown"
    port = parsed.port or 5432
    return f"{host}:{port}"


def _check_postgres() -> tuple[bool, str]:
    database_url = _get_database_url()
    if not database_url:
        return False, "DATABASE_URL not set"
    try:
        with psycopg.connect(database_url, connect_timeout=4) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
        return True, _format_host_port_from_url(database_url)
    except Exception as exc:  # pragma: no cover - UI surface only
        return False, f"{_format_host_port_from_url(database_url)} ({exc.__class__.__name__})"


def _check_redis() -> tuple[bool, str]:
    host_value = os.getenv("REDIS_HOST")
    host_port = _parse_host_port(host_value, 6379)
    if not host_port:
        return False, "REDIS_HOST not set"
    host, port = host_port
    try:
        client = redis.Redis(host=host, port=port, socket_connect_timeout=4)
        client.ping()
        return True, f"{host}:{port}"
    except Exception as exc:  # pragma: no cover - UI surface only
        return False, f"{host}:{port} ({exc.__class__.__name__})"


def _check_qdrant() -> tuple[bool, str]:
    host_value = os.getenv("QDRANT_URL")
    base = _http_base(host_value)
    if not base:
        return False, "QDRANT_URL not set"
    headers: dict[str, str] = {}
    api_key = os.getenv("QDRANT_API_KEY")
    if api_key:
        headers["api-key"] = api_key
    try:
        with httpx.Client(timeout=4) as client:
            response = client.get(f"{base}/healthz", headers=headers)
            response.raise_for_status()
        return True, base
    except Exception as exc:  # pragma: no cover - UI surface only
        return False, f"{base} ({exc.__class__.__name__})"


def _check_paperless() -> tuple[bool, str]:
    host_value = os.getenv("PAPERLESS_BASE_URL")
    api_base = _paperless_api_base(host_value)
    if not api_base:
        return False, "PAPERLESS_BASE_URL not set"
    token = os.getenv("PAPERLESS_API_TOKEN")
    if not token:
        return False, "PAPERLESS_API_TOKEN not set"
    try:
        with httpx.Client(timeout=6) as client:
            response = client.get(
                f"{api_base}/documents/?page_size=1",
                headers={"Authorization": f"Token {token}"},
            )
            response.raise_for_status()
        return True, api_base
    except Exception as exc:  # pragma: no cover - UI surface only
        return False, f"{api_base} ({exc.__class__.__name__})"


def _check_ollama() -> tuple[bool, str]:
    base_value = os.getenv("OLLAMA_BASE_URL")
    base = _http_base(base_value)
    if not base:
        return False, "OLLAMA_BASE_URL not set"
    model = os.getenv("OLLAMA_MODEL")
    if not model:
        return False, "OLLAMA_MODEL not set"
    try:
        payload = {
            "model": model,
            "prompt": "warum ist der himmel blau?",
            "stream": False,
        }
        with httpx.Client(timeout=15) as client:
            response = client.post(f"{base}/api/generate", json=payload)
            response.raise_for_status()
        return True, base
    except Exception as exc:  # pragma: no cover - UI surface only
        return False, f"{base} ({exc.__class__.__name__})"


def _run_all_checks() -> list[dict[str, Any]]:
    checks: list[tuple[str, callable[[], tuple[bool, str]]]] = [
        ("Paperless", _check_paperless),
        ("PostgreSQL", _check_postgres),
        ("Qdrant", _check_qdrant),
        ("Redis", _check_redis),
        ("Ollama", _check_ollama),
    ]
    results: list[dict[str, Any]] = []
    for name, check in checks:
        started = time.perf_counter()
        ok, detail = check()
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        results.append(
            {
                "service": name,
                "status": "UP" if ok else "DOWN",
                "detail": detail,
                "latency_ms": elapsed_ms,
            }
        )
    return results


@ui.page("/")
def index_page() -> None:
    ui.label("Paperless Intelligence (Read-only UI)").classes("text-h4")
    ui.markdown(
        "- Browse documents\n"
        "- Inspect AI insights\n"
        "- Optional explicit writeback actions"
    )
    with ui.row().classes("gap-4"):
        ui.link("Documents", "/documents")
        ui.link("Chat", "/chat")
        ui.link("Connections", "/connections")


@ui.page("/documents")
def documents_page() -> None:
    ui.label("Documents").classes("text-h5")
    ui.markdown("This will list documents synced from Paperless.")
    ui.table(
        columns=[
            {"name": "id", "label": "ID", "field": "id"},
            {"name": "title", "label": "Title", "field": "title"},
            {"name": "date", "label": "Date", "field": "date"},
        ],
        rows=[],
        row_key="id",
    )


@ui.page("/documents/{doc_id}")
def document_detail_page(doc_id: str) -> None:
    ui.label(f"Document {doc_id}").classes("text-h5")
    ui.markdown("Placeholder for metadata, OCR, entities, and summary.")
    with ui.row().classes("gap-4"):
        ui.link("Analyze", f"/analyze/{doc_id}")
        ui.link("Back to documents", "/documents")


@ui.page("/analyze/{doc_id}")
def analyze_page(doc_id: str) -> None:
    ui.label(f"Analyze document {doc_id}").classes("text-h5")
    ui.markdown("This will trigger analysis and show entities + similar docs.")


@ui.page("/chat")
def chat_page() -> None:
    ui.label("Document chat").classes("text-h5")
    ui.markdown("Ask a question about your documents.")
    prompt = ui.textarea("Question").classes("w-full")
    with ui.row().classes("gap-4"):
        ui.button("Ask", on_click=lambda: ui.notify(f"Queued: {prompt.value}"))


@ui.page("/writeback")
def writeback_page() -> None:
    ui.label("Writeback actions").classes("text-h5")
    ui.markdown(
        "Writebacks are manual and per-field. This page will show explicit actions."
    )


@ui.page("/connections")
def connections_page() -> None:
    ui.label("Connections").classes("text-h5")
    ui.markdown("Check connectivity to Paperless, Postgres, Qdrant, and Redis.")
    table = ui.table(
        columns=[
            {"name": "service", "label": "Service", "field": "service"},
            {"name": "status", "label": "Status", "field": "status"},
            {"name": "detail", "label": "Detail", "field": "detail"},
            {"name": "latency_ms", "label": "Latency (ms)", "field": "latency_ms"},
        ],
        rows=[],
        row_key="service",
    )

    async def run_checks() -> None:
        rows = await asyncio.to_thread(_run_all_checks)
        table.rows = rows
        table.update()

    ui.button("Run checks", on_click=run_checks)


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="Paperless Intelligence", reload=False)
