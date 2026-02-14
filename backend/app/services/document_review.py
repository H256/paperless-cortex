from __future__ import annotations

from datetime import datetime


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def derive_review_status(
    *,
    local_overrides: bool,
    reviewed_at: str | None,
    remote_modified: str | None,
) -> str:
    reviewed_at_dt = parse_iso_datetime(reviewed_at)
    remote_modified_dt = parse_iso_datetime(remote_modified)
    if local_overrides:
        return "needs_review"
    if reviewed_at_dt is None:
        return "unreviewed"
    if remote_modified_dt and remote_modified_dt > reviewed_at_dt:
        return "needs_review"
    return "reviewed"


def derive_sync_status(*, local_modified: str | None, remote_modified: str | None) -> str:
    local_modified_dt = parse_iso_datetime(local_modified)
    remote_modified_dt = parse_iso_datetime(remote_modified)
    if local_modified_dt and remote_modified_dt and remote_modified_dt > local_modified_dt:
        return "stale"
    return "synced"
