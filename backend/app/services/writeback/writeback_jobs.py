from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException
from pydantic import ValidationError

from app.api_models import WritebackDryRunCall, WritebackJobDetail, WritebackJobSummary
from app.services.runtime.json_utils import parse_json_list

if TYPE_CHECKING:
    from app.models import WritebackJob


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
    )
