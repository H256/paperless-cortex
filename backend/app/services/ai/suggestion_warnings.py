"""Implausibility warnings for normalized suggestion payloads.

These are *advisory* hints, not validation: they never block a suggestion,
they only flag values that look wrong so the user can double-check before
applying. The checks are pure and side-effect free (no LLM, no I/O) so they
can run at read time against the freshest known-correspondent list and
reference date.

Three checks (issue #359):
- ``date``: the normalized date is in the future (strictly after the
  reference date). A same-day value is plausible and is not flagged.
- ``title``: the title looks like a filename (a recognized document/media/
  archive extension, or a path separator) rather than a human title.
- ``correspondent``: the correspondent is non-empty but not in the known
  correspondent list (case-insensitive).
"""

from __future__ import annotations

import datetime
from typing import Any

# Recognized document/media/archive extensions. A title ending in one of these
# (or containing a path separator) is treated as filename-like. Using a bounded
# set keeps the advisory check high-precision: a normal prose title that merely
# contains a period (e.g. "Section 3.5 of the contract") is not flagged.
_FILENAME_EXTENSIONS = frozenset(
    {
        "pdf", "png", "jpg", "jpeg", "gif", "tiff", "tif", "bmp", "webp",
        "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv", "rtf",
        "odt", "ods", "odp", "epub", "zip", "tar", "gz", "mp3", "mp4", "wav",
    }
)


def _is_future_date(raw: Any, reference_date: datetime.date) -> bool:
    if not isinstance(raw, str) or not raw.strip():
        return False
    try:
        parsed = datetime.date.fromisoformat(raw.strip()[:10])
    except ValueError:
        return False
    return parsed > reference_date


def _is_filename_like_title(raw: Any) -> bool:
    if not isinstance(raw, str):
        return False
    title = raw.strip()
    if not title:
        return False
    if "/" in title or "\\" in title:
        return True
    last_segment = title.lower().rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if "." not in last_segment:
        return False
    return last_segment.rsplit(".", 1)[-1] in _FILENAME_EXTENSIONS


def compute_suggestion_warnings(
    payload: dict[str, Any] | None,
    known_correspondents: list[str] | None,
    reference_date: datetime.date,
) -> list[str]:
    """Return the list of implausibility warnings for a normalized payload."""
    if not isinstance(payload, dict):
        return []
    warnings: list[str] = []

    if _is_future_date(payload.get("date"), reference_date):
        warnings.append(f"Date {payload.get('date')} is in the future")

    if _is_filename_like_title(payload.get("title")):
        warnings.append(f"Title {payload.get('title')!r} looks like a filename")

    correspondent = payload.get("correspondent")
    if isinstance(correspondent, str) and correspondent.strip():
        known = {
            str(name).strip().lower()
            for name in (known_correspondents or [])
            if isinstance(name, str) and name.strip()
        }
        if correspondent.strip().lower() not in known:
            warnings.append(f"Correspondent {correspondent!r} is not a known correspondent")

    return warnings
