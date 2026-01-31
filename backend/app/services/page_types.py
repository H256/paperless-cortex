from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WordBox:
    text: str
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class PageText:
    page: int
    text: str
    source: str
    quality_score: int | None = None
    words: list[WordBox] | None = None
