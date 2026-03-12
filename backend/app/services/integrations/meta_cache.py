from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

from app.services.documents.pagination import load_all_pages
from app.services.integrations import paperless

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

_cache: dict[str, list[str]] = {"tags": [], "correspondents": []}
_loaded = False


def refresh_cache(settings: Settings) -> None:
    global _loaded
    try:
        tags = load_all_pages(lambda **kw: paperless.list_tags(settings, **kw))
        correspondents = load_all_pages(
            lambda **kw: paperless.list_correspondents(settings, **kw)
        )
        _cache["tags"] = sorted(
            {str(t.get("name")) for t in tags if t.get("name")}, key=str.lower
        )
        _cache["correspondents"] = sorted(
            {str(c.get("name")) for c in correspondents if c.get("name")}, key=str.lower
        )
        _loaded = True
        logger.info(
            "Meta cache loaded tags=%s correspondents=%s",
            len(_cache["tags"]),
            len(_cache["correspondents"]),
        )
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
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
