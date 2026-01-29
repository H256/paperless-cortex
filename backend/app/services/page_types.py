from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageText:
    page: int
    text: str
    source: str
    quality_score: int | None = None
