from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
from sqlalchemy.orm import Session, joinedload

from app.api_models import WritebackDryRunCall
from app.config import Settings
from app.models import Correspondent, Document, DocumentPendingCorrespondent, Tag
from app.services.integrations import paperless


def resolve_paperless_tag_ids(
    settings: Settings,
    db: Session,
    local_tag_ids: list[int],
    pending_tag_names: list[str] | None = None,
) -> list[int]:
    local_tags = db.query(Tag).filter(Tag.id.in_(local_tag_ids)).all()
    local_names = [str(tag.name or "").strip() for tag in local_tags if str(tag.name or "").strip()]
    for name in (pending_tag_names or []):
        clean = str(name or "").strip()
        if clean and clean not in local_names:
            local_names.append(clean)
    if not local_names:
        return []
    remote_tags = paperless.list_all_tags(settings)
    remote_by_name = {
        str(tag.get("name") or "").strip().lower(): int(tag.get("id"))
        for tag in remote_tags
        if isinstance(tag.get("id"), int) and str(tag.get("name") or "").strip()
    }
    resolved_ids: list[int] = []
    for name in local_names:
        key = name.lower()
        existing_id = remote_by_name.get(key)
        if existing_id is None:
            created = paperless.create_tag(settings, name)
            created_id = created.get("id")
            if isinstance(created_id, int):
                existing_id = created_id
                remote_by_name[key] = created_id
        if isinstance(existing_id, int):
            resolved_ids.append(existing_id)
            local_tag = db.query(Tag).filter(Tag.id == existing_id).one_or_none()
            if not local_tag:
                db.add(Tag(id=existing_id, name=name))
            elif (local_tag.name or "").strip() != name:
                local_tag.name = name
    return sorted(set(resolved_ids))


def resolve_paperless_correspondent_id(
    settings: Settings,
    db: Session,
    local_correspondent_id: int | None,
    pending_correspondent_name: str | None = None,
) -> int | None:
    def _as_int(value: Any) -> int | None:
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            try:
                return int(raw)
            except Exception:
                return None
        return None

    def _migrate_local_references(old_id: int | None, new_id: int, name: str) -> None:
        local_corr = db.query(Correspondent).filter(Correspondent.id == int(new_id)).one_or_none()
        if not local_corr:
            db.add(Correspondent(id=int(new_id), name=name))
            # Ensure FK target row exists before remapping document references.
            db.flush()
        elif (local_corr.name or "").strip() != name:
            local_corr.name = name
            db.flush()
        if old_id and old_id != new_id:
            db.query(Document).filter(Document.correspondent_id == int(old_id)).update(
                {"correspondent_id": int(new_id)},
                synchronize_session=False,
            )

    local_name = str(pending_correspondent_name or "").strip()
    local_id = int(local_correspondent_id) if isinstance(local_correspondent_id, int) and local_correspondent_id > 0 else None
    if not local_name and local_id:
        local_row = db.query(Correspondent).filter(Correspondent.id == int(local_id)).one_or_none()
        local_name = str(local_row.name or "").strip() if local_row else ""

    remote_rows = paperless.list_all_correspondents(settings)
    remote_by_id = {
        int(row.get("id")): str(row.get("name") or "").strip()
        for row in remote_rows
        if _as_int(row.get("id")) is not None
    }
    if local_id and local_id in remote_by_id:
        return local_id

    remote_by_name = {
        str(row.get("name") or "").strip().lower(): _as_int(row.get("id"))
        for row in remote_rows
        if _as_int(row.get("id")) is not None and str(row.get("name") or "").strip()
    }
    if not local_name:
        return None
    existing_id = remote_by_name.get(local_name.lower())
    if existing_id is None:
        created = paperless.create_correspondent(settings, local_name)
        created_id = _as_int(created.get("id"))
        if created_id is not None:
            existing_id = created_id

    if isinstance(existing_id, int):
        _migrate_local_references(local_id, int(existing_id), local_name)
        return existing_id
    return None


def execute_writeback_call(settings: Settings, db: Session, call: WritebackDryRunCall) -> None:
    method = call.method.upper()
    if method == "PATCH":
        payload = dict(call.payload or {})
        had_tags = False
        had_correspondent = False
        resolved_correspondent_id: int | None = None
        raw_correspondent = payload.get("correspondent")
        pending_correspondent_name = payload.pop("pending_correspondent_name", None)
        if "correspondent" in payload:
            had_correspondent = True
            local_correspondent_id = int(raw_correspondent) if isinstance(raw_correspondent, int) else None
            resolved_correspondent_id = resolve_paperless_correspondent_id(
                settings,
                db,
                local_correspondent_id,
                str(pending_correspondent_name or "").strip() or None,
            )
            if resolved_correspondent_id is None and str(pending_correspondent_name or "").strip():
                raise RuntimeError(
                    f"Unable to resolve/create correspondent: {str(pending_correspondent_name).strip()}"
                )
            if resolved_correspondent_id is None:
                payload.pop("correspondent", None)
            else:
                payload["correspondent"] = resolved_correspondent_id
        raw_tags = payload.get("tags")
        if isinstance(raw_tags, list):
            had_tags = True
            local_tag_ids = [int(tag_id) for tag_id in raw_tags if isinstance(tag_id, int)]
            pending_names_raw = payload.pop("pending_tag_names", [])
            pending_names = [str(name).strip() for name in pending_names_raw if str(name).strip()] if isinstance(pending_names_raw, list) else []
            payload["tags"] = resolve_paperless_tag_ids(settings, db, local_tag_ids, pending_names)
            db.flush()
        if payload.get("created") in (None, ""):
            payload.pop("created", None)
        if payload.get("title") is None:
            payload.pop("title", None)
        if not payload:
            return
        try:
            paperless.update_document(settings, int(call.doc_id), payload)
        except httpx.HTTPStatusError as exc:
            response_text = ""
            try:
                response_text = str(exc.response.text or "").strip()
            except Exception:
                response_text = ""
            status_code = int(exc.response.status_code) if exc.response is not None else 0
            # Paperless often rejects null/invalid created fields; retry once without created.
            if status_code == 400 and "created" in payload:
                retry_payload = dict(payload)
                retry_payload.pop("created", None)
                if retry_payload:
                    try:
                        paperless.update_document(settings, int(call.doc_id), retry_payload)
                        payload = retry_payload
                    except httpx.HTTPStatusError as retry_exc:
                        retry_text = ""
                        try:
                            retry_text = str(retry_exc.response.text or "").strip()
                        except Exception:
                            retry_text = ""
                        raise RuntimeError(
                            f"Paperless PATCH failed doc={int(call.doc_id)} status={int(retry_exc.response.status_code)} "
                            f"payload={retry_payload} response={retry_text[:500]}"
                        ) from retry_exc
                else:
                    raise RuntimeError(
                        f"Paperless PATCH failed doc={int(call.doc_id)} status={status_code} "
                        f"payload={payload} response={response_text[:500]}"
                    ) from exc
            else:
                raise RuntimeError(
                    f"Paperless PATCH failed doc={int(call.doc_id)} status={status_code} "
                    f"payload={payload} response={response_text[:500]}"
                ) from exc
        if had_tags:
            local_doc = (
                db.query(Document)
                .options(joinedload(Document.tags))
                .filter(Document.id == int(call.doc_id))
                .one_or_none()
            )
            if local_doc:
                resolved_ids_raw = payload.get("tags")
                resolved_ids: list[object] = resolved_ids_raw if isinstance(resolved_ids_raw, list) else []
                resolved_ids_int: list[int] = [tag_id for tag_id in resolved_ids if isinstance(tag_id, int)]
                existing_tags = db.query(Tag).filter(Tag.id.in_(resolved_ids_int)).all() if resolved_ids_int else []
                by_id = {tag.id: tag for tag in existing_tags}
                local_doc.tags = [by_id[tag_id] for tag_id in resolved_ids_int if tag_id in by_id]
        if had_correspondent:
            local_doc = db.query(Document).filter(Document.id == int(call.doc_id)).one_or_none()
            if local_doc:
                local_doc.correspondent_id = resolved_correspondent_id
            pending_corr_row = (
                db.query(DocumentPendingCorrespondent)
                .filter(DocumentPendingCorrespondent.doc_id == int(call.doc_id))
                .one_or_none()
            )
            if pending_corr_row:
                db.delete(pending_corr_row)
        return
    if method == "POST":
        payload = dict(call.payload or {})
        note = str(payload.get("note") or "")
        paperless.add_document_note(settings, int(call.doc_id), note)
        return
    if method == "DELETE":
        path = str(call.path or "")
        note_id: int | None = None
        parsed = urlsplit(path)
        query_id = parse_qs(parsed.query).get("id")
        if query_id and query_id[0]:
            try:
                note_id = int(query_id[0])
            except Exception:
                note_id = None
        if note_id is None:
            try:
                segment = parsed.path.rstrip("/").split("/")[-1]
                note_id = int(segment)
            except Exception:
                note_id = None
        if note_id is None:
            raise RuntimeError(f"Cannot parse note id from path: {path}")
        paperless.delete_document_note(settings, int(call.doc_id), note_id)
        return
    raise RuntimeError(f"Unsupported writeback method: {method}")
