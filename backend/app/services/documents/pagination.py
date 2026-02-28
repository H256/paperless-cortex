from __future__ import annotations

from collections.abc import Callable


def load_all_pages(fetch_page: Callable[..., dict], page_size: int = 200) -> list[dict]:
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
