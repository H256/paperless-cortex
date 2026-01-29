from __future__ import annotations

import logging
from typing import Iterable

from app.config import Settings
from app.services import paperless

logger = logging.getLogger(__name__)

_cache: dict[str, list[str]] = {"tags": [], "correspondents": []}
_loaded = False


def _load_all_pages(fetch_page, page_size: int = 200) -> list[dict]:
    page = 1
    results: list[dict] = []
    while True:
        payload = fetch_page(page=page, page_size=page_size)
        page_results = payload.get("results", []) or []
        results.extend(page_results)
        if not payload.get("next"):
            break
        page += 1
    return results


def refresh_cache(settings: Settings) -> None:
    global _loaded
    try:
        tags = _load_all_pages(lambda **kw: paperless.list_tags(settings, **kw))
        correspondents = _load_all_pages(
            lambda **kw: paperless.list_correspondents(settings, **kw)
        )
        _cache["tags"] = sorted(
            {t.get("name") for t in tags if t.get("name")}, key=str.lower
        )
        _cache["correspondents"] = sorted(
            {c.get("name") for c in correspondents if c.get("name")}, key=str.lower
        )
        _loaded = True
        logger.info(
            "Meta cache loaded tags=%s correspondents=%s",
            len(_cache["tags"]),
            len(_cache["correspondents"]),
        )
    except Exception as exc:
        logger.warning("Meta cache refresh failed: %s", exc)
        _loaded = False


def ensure_cache(settings: Settings) -> None:
    if not _loaded:
        refresh_cache(settings)


def get_cached_tags(settings: Settings) -> list[str]:
    ensure_cache(settings)
    return list(_cache["tags"])


def get_cached_correspondents(settings: Settings) -> list[str]:
    ensure_cache(settings)
    return list(_cache["correspondents"])
