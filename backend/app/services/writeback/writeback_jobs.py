from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from fastapi import HTTPException
from pydantic import ValidationError

from app.api_models import WritebackDryRunCall, WritebackJobDetail, WritebackJobSummary
from app.services.runtime.json_utils import parse_json_list
from app.services.writeback.writeback_selection import parse_applied_call_indexes

if TYPE_CHECKING:
    from app.api_models import WritebackDryRunItem
    from app.models import WritebackJob


def preview_fingerprints(items: list[WritebackDryRunItem]) -> dict[str, str]:
    """Hash what the user was shown (original and proposed values) for each changed doc."""
    result: dict[str, str] = {}
    for item in items:
        if not item.changed:
            continue
        shown = {
            name: {"original": diff.original, "proposed": diff.proposed}
            for name in item.changed_fields
            if (diff := getattr(item, name, None)) is not None
        }
        blob = json.dumps(shown, sort_keys=True, default=str, ensure_ascii=False)
        result[str(item.doc_id)] = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return result


def changed_since_preview(job: WritebackJob, fresh_items: list[WritebackDryRunItem]) -> list[int]:
    """Doc ids whose previewed values differ now from when the job was created."""
    if not job.preview_fingerprint_json:
        return []  # job predates fingerprints: nothing to compare against
    try:
        stored = json.loads(job.preview_fingerprint_json)
    except ValueError:
        return []
    fresh = preview_fingerprints(fresh_items)
    return sorted(int(doc_id) for doc_id, digest in stored.items() if fresh.get(doc_id) != digest)


# A job that has been "running" longer than this was cut off (crash/restart) and will never finish.
STALE_RUNNING_JOB = timedelta(minutes=30)


def is_stale_running_job(job: WritebackJob) -> bool:
    if str(job.status or "") != "running":
        return False
    try:
        started = datetime.fromisoformat(str(job.started_at))
    except ValueError:
        return True
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    return datetime.now(UTC) - started > STALE_RUNNING_JOB


def missing_writeback_jobs_table(exc: Exception) -> bool:
    text = str(exc).lower()
    return "writeback_jobs" in text and (
        "no such table" in text
        or "does not exist" in text
        or "undefined table" in text
    )


def raise_missing_writeback_jobs_table() -> None:
    raise HTTPException(
        status_code=503,
        detail="Writeback jobs table is missing. Run database migrations (alembic upgrade head).",
    )


def job_summary(job: WritebackJob) -> WritebackJobSummary:
    return WritebackJobSummary(
        id=job.id,
        status=job.status,
        dry_run=bool(job.dry_run),
        docs_selected=int(job.docs_selected or 0),
        docs_changed=int(job.docs_changed or 0),
        calls_count=int(job.calls_count or 0),
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error=job.error,
    )


def deserialize_doc_ids(job: WritebackJob) -> list[int]:
    doc_ids: list[int] = []
    for item in parse_json_list(job.doc_ids_json):
        try:
            doc_ids.append(int(item))
        except (TypeError, ValueError):
            continue
    return doc_ids


def deserialize_calls(job: WritebackJob) -> list[WritebackDryRunCall]:
    calls: list[WritebackDryRunCall] = []
    for item in parse_json_list(job.calls_json):
        if not isinstance(item, dict):
            continue
        try:
            calls.append(WritebackDryRunCall(**item))
        except ValidationError:
            continue
    return calls


def job_detail(job: WritebackJob) -> WritebackJobDetail:
    return WritebackJobDetail(
        **job_summary(job).model_dump(),
        doc_ids=deserialize_doc_ids(job),
        calls=deserialize_calls(job),
        applied_calls_count=len(parse_applied_call_indexes(job.applied_call_indexes_json)),
    )
