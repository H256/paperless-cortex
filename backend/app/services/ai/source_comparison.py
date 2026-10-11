from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

_TOKEN_RE = re.compile(r"[^\W_]{3,}")

# Readability is `100 - penalty`; two sources closer than this are treated as equal.
_MIN_READABILITY_GAP = 5.0
# Below this overlap the two OCR texts clearly disagree about the content.
LOW_AGREEMENT = 0.5


def token_agreement(first: str | None, second: str | None) -> float | None:
    """Share of distinct words (>= 3 chars, case-insensitive) that both texts contain.

    A cheap, LLM-free signal: two readable OCR runs of the same page share most words,
    a broken or scrambled run does not. ``None`` when either text has no words.
    """
    first_tokens = set(_TOKEN_RE.findall((first or "").lower()))
    second_tokens = set(_TOKEN_RE.findall((second or "").lower()))
    if not first_tokens or not second_tokens:
        return None
    union = first_tokens | second_tokens
    return len(first_tokens & second_tokens) / len(union)


def readability(quality_score: float | None) -> float | None:
    """Single 0-100 scale, higher is better, derived from the stored penalty score."""
    if quality_score is None:
        return None
    return max(0.0, min(100.0, 100.0 - float(quality_score)))


def recommend_source(
    scores: Iterable[dict[str, object]],
    agreement: float | None = None,
) -> dict[str, object]:
    """Pick the OCR source whose text reads better.

    ``scores`` rows carry ``source`` and ``quality_score`` (a penalty, lower is better).
    Returns ``{"source": str | None, "reason": str}``; no source when the two are too
    close to call or when nothing was scored.
    """
    rated: dict[str, float] = {}
    for row in scores:
        source = row.get("source")
        value = readability(row.get("quality_score"))  # type: ignore[arg-type]
        if isinstance(source, str) and value is not None:
            rated[source] = value
    if not rated:
        return {"source": None, "reason": "No OCR quality scores available yet."}
    if len(rated) == 1:
        (source, value), = rated.items()
        return {"source": source, "reason": f"Only source with a score (readability {value:.0f})."}
    best_source = max(rated, key=lambda key: rated[key])
    worst_source = min(rated, key=lambda key: rated[key])
    gap = rated[best_source] - rated[worst_source]
    if gap < _MIN_READABILITY_GAP:
        reason = "Both texts read about equally well."
        if agreement is not None and agreement < LOW_AGREEMENT:
            reason += " They differ a lot in content, compare them before trusting suggestions."
        return {"source": None, "reason": reason}
    return {
        "source": best_source,
        "reason": (
            f"Readability {rated[best_source]:.0f} vs {rated[worst_source]:.0f} "
            f"for the other text."
        ),
    }
