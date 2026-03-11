from __future__ import annotations

from datetime import UTC, datetime


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format.

    Returns:
        ISO 8601 formatted timestamp string with timezone info.

    Example:
        >>> utc_now_iso()
        '2024-03-11T14:30:45.123456+00:00'
    """
    return datetime.now(UTC).isoformat()


def estimate_eta_seconds(
    started_at: str | None, processed: int | None, total: int | None
) -> int | None:
    """Estimate remaining time in seconds for a running task.

    Calculates ETA based on current progress rate. Returns None if
    insufficient data is available or if calculation fails.

    Args:
        started_at: ISO timestamp when task started
        processed: Number of items processed so far
        total: Total number of items to process

    Returns:
        Estimated seconds remaining, or None if cannot be calculated.

    Example:
        >>> estimate_eta_seconds("2024-03-11T14:00:00+00:00", 50, 100)
        60  # Approximately 60 seconds remaining
    """
    if not started_at or not processed or not total:
        return None
    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        elapsed = (datetime.now(UTC) - started).total_seconds()
        rate = processed / max(1.0, elapsed)
        remaining = total - processed
        return int(max(0.0, remaining / rate)) if rate > 0 else None
    except ValueError:
        return None
