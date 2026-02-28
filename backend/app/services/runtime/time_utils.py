from __future__ import annotations

from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def estimate_eta_seconds(
    started_at: str | None, processed: int | None, total: int | None
) -> int | None:
    if not started_at or not processed or not total:
        return None
    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        rate = processed / max(1.0, elapsed)
        remaining = total - processed
        return int(max(0.0, remaining / rate)) if rate > 0 else None
    except Exception:
        return None
