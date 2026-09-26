from __future__ import annotations

import copy
from collections.abc import Callable

from app.services.documents.cache import TtlLruCache

DocumentsPageBuilder = Callable[[], dict[str, object]]
DocumentsPageKey = tuple[
    int,
    int,
    str | None,
    int | None,
    int | None,
    str | None,
    str | None,
    str | None,
    bool,
    bool,
    str,
]

_CACHE_TTL_SECONDS = 15
_CACHE_MAXSIZE = 512
_CACHE = TtlLruCache(ttl_seconds=_CACHE_TTL_SECONDS, maxsize=_CACHE_MAXSIZE)


def invalidate_documents_list_cache() -> None:
    _CACHE.clear()


def get_cached_documents_page(
    *,
    cache_key: DocumentsPageKey,
    build_payload: DocumentsPageBuilder,
) -> dict[str, object]:
    cached = _CACHE.get(cache_key)
    if isinstance(cached, dict):
        return copy.deepcopy(cached)

    payload = build_payload()
    _CACHE.put(cache_key, copy.deepcopy(payload))
    return copy.deepcopy(payload)
