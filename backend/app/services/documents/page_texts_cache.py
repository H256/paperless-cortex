from __future__ import annotations

import copy
from collections.abc import Callable

from app.services.documents.cache import TtlLruCache

PageTextsBuilder = Callable[[], dict[str, object]]

_CACHE_TTL_SECONDS = 30
_CACHE_MAXSIZE = 1024
_CACHE = TtlLruCache(ttl_seconds=_CACHE_TTL_SECONDS, maxsize=_CACHE_MAXSIZE)


def invalidate_page_texts_cache(doc_id: int | None = None) -> None:
    if doc_id is None:
        _CACHE.clear()
        return
    _CACHE.invalidate(int(doc_id))


def get_cached_page_texts_payload(
    *,
    doc_id: int,
    build_payload: PageTextsBuilder,
) -> dict[str, object]:
    cache_key = int(doc_id)
    cached = _CACHE.get(cache_key)
    if isinstance(cached, dict):
        return copy.deepcopy(cached)

    payload = build_payload()
    _CACHE.put(cache_key, copy.deepcopy(payload))
    return copy.deepcopy(payload)
