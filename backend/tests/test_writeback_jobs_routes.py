from __future__ import annotations

import json
import os
from typing import Any

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models import (
    Document,
    DocumentNote,
    DocumentPendingTag,
    SuggestionAudit,
    Tag,
    WritebackJob,
)


def _insert_document(doc_id: int, title: str) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=doc_id, title=title))
        db.commit()


def _insert_tag(tag_id: int, name: str) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Tag(id=tag_id, name=name))
        db.commit()


def _insert_pending_tags(doc_id: int, names: list[str]) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(
            DocumentPendingTag(
                doc_id=doc_id,
                names_json=json.dumps(names, ensure_ascii=False),
                updated_at="2026-02-10T10:10:00+00:00",
            )
        )
        db.commit()


def test_writeback_job_create_and_execute_dry_run(api_client: Any, monkeypatch: Any) -> None:
    from app.services.integrations import paperless

    _insert_document(501, "Local title")

    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda _settings, doc_id: {
            "id": doc_id,
            "title": "Remote title",
            "document_date": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    create_resp = api_client.post("/writeback/jobs", json={"doc_ids": [501]})
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert created["status"] == "pending"
    assert created["docs_selected"] == 1
    assert created["docs_changed"] == 1
    assert created["calls_count"] >= 1

    job_id = int(created["id"])
    exec_resp = api_client.post(f"/writeback/jobs/{job_id}/execute", json={"dry_run": True})
    assert exec_resp.status_code == 200
    executed = exec_resp.json()
    assert executed["id"] == job_id
    assert executed["status"] == "completed"
    assert executed["dry_run"] is True


def test_writeback_job_execute_real_calls_paperless(api_client: Any, monkeypatch: Any) -> None:
    from app.services.integrations import paperless

    _insert_document(502, "Local title 502")

    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda _settings, doc_id: {
            "id": doc_id,
            "title": "Remote title 502",
            "document_date": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    calls: dict[str, int] = {"patch": 0}

    def _fake_patch(_settings: Any, doc_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        calls["patch"] += 1
        return {"id": doc_id, **payload}

    monkeypatch.setattr(paperless, "update_document", _fake_patch)
    monkeypatch.setattr(paperless, "add_document_note", lambda *args, **kwargs: {"id": 1})
    monkeypatch.setattr(paperless, "delete_document_note", lambda *args, **kwargs: None)
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    create_resp = api_client.post("/writeback/jobs", json={"doc_ids": [502]})
    assert create_resp.status_code == 200
    job_id = int(create_resp.json()["id"])

    exec_resp = api_client.post(f"/writeback/jobs/{job_id}/execute", json={"dry_run": False})
    assert exec_resp.status_code == 200
    executed = exec_resp.json()
    assert executed["status"] == "completed"
    assert executed["dry_run"] is False
    assert calls["patch"] >= 1


def test_writeback_job_create_deduplicates_pending(api_client: Any, monkeypatch: Any) -> None:
    from app.services.integrations import paperless

    _insert_document(503, "Local title 503")
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda _settings, doc_id: {
            "id": doc_id,
            "title": "Remote title 503",
            "document_date": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    first = api_client.post("/writeback/jobs", json={"doc_ids": [503]})
    second = api_client.post("/writeback/jobs", json={"doc_ids": [503]})
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_writeback_execute_pending_runs_all(api_client: Any, monkeypatch: Any) -> None:
    from app.services.integrations import paperless

    _insert_document(504, "Local title 504")
    _insert_document(505, "Local title 505")
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda _settings, doc_id: {
            "id": doc_id,
            "title": f"Remote title {doc_id}",
            "document_date": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    api_client.post("/writeback/jobs", json={"doc_ids": [504]})
    api_client.post("/writeback/jobs", json={"doc_ids": [505]})

    result = api_client.post("/writeback/jobs/execute-pending", json={"dry_run": True, "limit": 0})
    assert result.status_code == 200
    payload = result.json()
    assert payload["processed"] >= 2
    assert payload["completed"] >= 2
    assert payload["failed"] == 0


def test_writeback_job_delete_removes_pending_job(api_client: Any, monkeypatch: Any) -> None:
    from app.services.integrations import paperless

    _insert_document(530, "Local title 530")
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda _settings, doc_id: {
            "id": doc_id,
            "title": "Remote title 530",
            "document_date": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    create_resp = api_client.post("/writeback/jobs", json={"doc_ids": [530]})
    assert create_resp.status_code == 200
    job_id = int(create_resp.json()["id"])

    delete_resp = api_client.delete(f"/writeback/jobs/{job_id}")
    assert delete_resp.status_code == 200
    payload = delete_resp.json()
    assert payload["ok"] is True
    assert payload["removed"] is True
    assert int(payload["job_id"]) == job_id


def test_writeback_execute_now_executes_without_queue(api_client: Any, monkeypatch: Any) -> None:
    from app.services.integrations import paperless

    _insert_document(506, "Local title 506")
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda _settings, doc_id: {
            "id": doc_id,
            "title": "Remote title 506",
            "created": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )
    calls: dict[str, int] = {"patch": 0}

    def _fake_patch(_settings: Any, doc_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        calls["patch"] += 1
        return {"id": doc_id, **payload}

    monkeypatch.setattr(paperless, "update_document", _fake_patch)
    monkeypatch.setattr(paperless, "add_document_note", lambda *args, **kwargs: {"id": 1})
    monkeypatch.setattr(paperless, "delete_document_note", lambda *args, **kwargs: None)
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    result = api_client.post("/writeback/execute-now", json={"doc_ids": [506]})
    assert result.status_code == 200
    payload = result.json()
    assert payload["docs_selected"] == 1
    assert payload["docs_changed"] == 1
    assert payload["calls_count"] >= 1
    assert payload["errors"] == []
    assert payload["failed_doc_ids"] == []
    assert calls["patch"] >= 1


def test_writeback_execute_now_rejects_without_valid_doc_ids(api_client: Any, monkeypatch: Any) -> None:
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")
    result = api_client.post("/writeback/execute-now", json={"doc_ids": [0, -1]})
    assert result.status_code == 400
    assert "No valid doc_ids provided" in str(result.json().get("detail"))


def test_writeback_execute_now_updates_local_modified_and_review_timestamp(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.services.integrations import paperless

    _insert_document(510, "Local title 510")
    remote_modified = "2026-02-12T18:00:00+00:00"
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda _settings, doc_id: {
            "id": doc_id,
            "title": "Remote title 510",
            "created": "2026-02-01",
            "modified": remote_modified,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )
    monkeypatch.setattr(
        paperless,
        "update_document",
        lambda _settings, doc_id, payload: {"id": doc_id, **payload},
    )
    monkeypatch.setattr(paperless, "add_document_note", lambda *args, **kwargs: {"id": 1})
    monkeypatch.setattr(paperless, "delete_document_note", lambda *args, **kwargs: None)
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    result = api_client.post("/writeback/execute-now", json={"doc_ids": [510]})
    assert result.status_code == 200

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        doc = db.query(Document).filter(Document.id == 510).one()
        assert doc.modified == remote_modified
        audit = (
            db.query(SuggestionAudit)
            .filter(
                SuggestionAudit.doc_id == 510,
                SuggestionAudit.action == "apply_to_document:writeback",
            )
            .order_by(SuggestionAudit.id.desc())
            .first()
        )
        assert audit is not None
        assert audit.created_at == remote_modified


def test_writeback_direct_requires_resolution_when_modified_changed(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.services.integrations import paperless

    _insert_document(507, "Local title 507")
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda _settings, doc_id: {
            "id": doc_id,
            "title": "Remote title 507",
            "created": "2026-02-01",
            "modified": "2026-02-10T10:00:00Z",
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    result = api_client.post(
        "/writeback/documents/507/execute-direct",
        json={"known_paperless_modified": "2026-02-09T10:00:00Z", "resolutions": {}},
    )
    assert result.status_code == 200
    payload = result.json()
    assert payload["status"] == "conflicts"
    assert isinstance(payload["conflicts"], list)


def test_writeback_execute_now_creates_missing_paperless_tags(
    api_client: Any, monkeypatch: Any
) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.models import Document
    from app.services.integrations import paperless

    _insert_document(508, "Local title 508")
    _insert_tag(901, "Tag-New")
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        doc = db.query(Document).filter(Document.id == 508).first()
        tag = db.query(Tag).filter(Tag.id == 901).first()
        doc.tags = [tag]
        db.commit()

    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda _settings, doc_id: {
            "id": doc_id,
            "title": "Remote title 508",
            "created": "2026-02-01",
            "modified": "2026-02-10T10:00:00Z",
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    monkeypatch.setattr(paperless, "list_all_tags", lambda _settings: [])
    monkeypatch.setattr(paperless, "create_tag", lambda _settings, name: {"id": 777, "name": name})
    patch_payloads: list[dict[str, Any]] = []

    def _update_document(_settings: Any, doc_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        patch_payloads.append(dict(payload))
        return {"id": doc_id, **payload}

    monkeypatch.setattr(paperless, "update_document", _update_document)
    monkeypatch.setattr(paperless, "add_document_note", lambda *args, **kwargs: {"id": 1})
    monkeypatch.setattr(paperless, "delete_document_note", lambda *args, **kwargs: None)
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    result = api_client.post("/writeback/execute-now", json={"doc_ids": [508]})
    assert result.status_code == 200
    assert patch_payloads
    assert patch_payloads[0].get("tags") == [777]


def test_writeback_direct_executes_for_pending_tags_only(api_client: Any, monkeypatch: Any) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.models import Document
    from app.services.integrations import paperless

    _insert_document(509, "Doc 509")
    _insert_pending_tags(509, ["BrandNew"])
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda _settings, doc_id: {
            "id": doc_id,
            "title": "Doc 509",
            "created": "2026-02-01",
            "modified": "2026-02-10T10:00:00Z",
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )
    monkeypatch.setattr(paperless, "list_all_tags", lambda _settings: [])
    monkeypatch.setattr(paperless, "create_tag", lambda _settings, name: {"id": 778, "name": name})
    patch_payloads: list[dict[str, Any]] = []

    def _update_document(_settings: Any, doc_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        patch_payloads.append(dict(payload))
        return {"id": doc_id, **payload}

    monkeypatch.setattr(paperless, "update_document", _update_document)
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    result = api_client.post(
        "/writeback/documents/509/execute-direct",
        json={"known_paperless_modified": "2026-02-10T10:00:00Z", "resolutions": {}},
    )
    assert result.status_code == 200
    payload = result.json()
    assert payload["status"] == "completed"
    assert payload["calls_count"] >= 1
    assert patch_payloads
    assert patch_payloads[0].get("tags") == [778]
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        doc = db.query(Document).filter(Document.id == 509).one()
        assert [tag.id for tag in doc.tags] == [778]
        pending = db.query(DocumentPendingTag).filter(DocumentPendingTag.doc_id == 509).one_or_none()
        assert pending is None


def test_writeback_job_create_rejects_without_valid_doc_ids(api_client: Any) -> None:
    create_resp = api_client.post("/writeback/jobs", json={"doc_ids": [0, -5]})
    assert create_resp.status_code == 400
    assert "No valid doc_ids provided" in str(create_resp.json().get("detail"))


def test_writeback_job_create_rejects_when_no_changes_detected(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.services.integrations import paperless

    _insert_document(540, "Same title")
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda _settings, doc_id: {
            "id": doc_id,
            "title": "Same title",
            "document_date": None,
            "created": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    create_resp = api_client.post("/writeback/jobs", json={"doc_ids": [540]})
    assert create_resp.status_code == 400
    assert "No writeback changes detected" in str(create_resp.json().get("detail"))


def test_writeback_job_get_returns_404_for_missing_job(api_client: Any) -> None:
    response = api_client.get("/writeback/jobs/999999")
    assert response.status_code == 404
    assert "Writeback job not found" in str(response.json().get("detail"))


def test_writeback_job_delete_rejects_running_job(api_client: Any) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(
            WritebackJob(
                status="running",
                dry_run=True,
                docs_selected=1,
                docs_changed=1,
                calls_count=1,
                doc_ids_json="[550]",
                calls_json="[]",
                created_at="2026-02-20T10:00:00+00:00",
            )
        )
        db.commit()
        job_id = int(db.query(WritebackJob.id).order_by(WritebackJob.id.desc()).first()[0])

    response = api_client.delete(f"/writeback/jobs/{job_id}")
    assert response.status_code == 409
    assert "Cannot delete a running writeback job" in str(response.json().get("detail"))


def test_writeback_jobs_list_returns_503_when_table_missing(api_client: Any) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE writeback_jobs"))

    response = api_client.get("/writeback/jobs")
    assert response.status_code == 503
    assert "Writeback jobs table is missing" in str(response.json().get("detail"))


def test_writeback_job_execute_rejects_real_execution_when_disabled(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.services.integrations import paperless

    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "0")
    _insert_document(560, "Local title 560")
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda _settings, doc_id: {
            "id": doc_id,
            "title": "Remote title 560",
            "document_date": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )
    create_resp = api_client.post("/writeback/jobs", json={"doc_ids": [560]})
    assert create_resp.status_code == 200
    job_id = int(create_resp.json()["id"])

    exec_resp = api_client.post(f"/writeback/jobs/{job_id}/execute", json={"dry_run": False})
    assert exec_resp.status_code == 400
    assert "WRITEBACK_EXECUTE_ENABLED=1" in str(exec_resp.json().get("detail"))


def test_writeback_execute_pending_rejects_real_execution_when_disabled(
    api_client: Any, monkeypatch: Any
) -> None:
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "0")
    result = api_client.post("/writeback/jobs/execute-pending", json={"dry_run": False, "limit": 1})
    assert result.status_code == 400
    assert "WRITEBACK_EXECUTE_ENABLED=1" in str(result.json().get("detail"))


def test_writeback_job_execute_returns_503_when_table_missing(api_client: Any) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE writeback_jobs"))

    response = api_client.post("/writeback/jobs/1/execute", json={"dry_run": True})
    assert response.status_code == 503
    assert "Writeback jobs table is missing" in str(response.json().get("detail"))


def test_writeback_history_limit_zero_clamps_and_filters_statuses(api_client: Any) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(
            WritebackJob(
                status="pending",
                dry_run=True,
                docs_selected=1,
                docs_changed=1,
                calls_count=1,
                doc_ids_json="[1]",
                calls_json="[]",
                created_at="2026-02-20T10:00:00+00:00",
            )
        )
        db.add(
            WritebackJob(
                status="completed",
                dry_run=True,
                docs_selected=1,
                docs_changed=1,
                calls_count=1,
                doc_ids_json="[2]",
                calls_json="[]",
                created_at="2026-02-20T10:00:00+00:00",
            )
        )
        db.add(
            WritebackJob(
                status="failed",
                dry_run=True,
                docs_selected=1,
                docs_changed=1,
                calls_count=1,
                doc_ids_json="[3]",
                calls_json="[]",
                created_at="2026-02-20T10:00:00+00:00",
            )
        )
        db.commit()

    response = api_client.get("/writeback/history", params={"limit": 0})
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("items"), list)
    statuses = {str(item.get("status") or "") for item in payload["items"]}
    assert "pending" not in statuses
    assert statuses.issubset({"completed", "failed"})


def test_writeback_history_returns_503_when_table_missing(api_client: Any) -> None:
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE writeback_jobs"))

    response = api_client.get("/writeback/history")
    assert response.status_code == 503
    assert "Writeback jobs table is missing" in str(response.json().get("detail"))


def test_writeback_job_lifecycle_execute_pending_and_history_with_failure(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.services.integrations import paperless

    _insert_document(571, "Local title 571")
    _insert_document(572, "Local title 572")
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda _settings, doc_id: {
            "id": doc_id,
            "title": f"Remote title {doc_id}",
            "created": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")
    monkeypatch.setattr(paperless, "add_document_note", lambda *args, **kwargs: {"id": 1})
    monkeypatch.setattr(paperless, "delete_document_note", lambda *args, **kwargs: None)

    def _patch(_settings: Any, doc_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        if int(doc_id) == 572:
            raise RuntimeError("forced patch failure for lifecycle test")
        return {"id": doc_id, **payload}

    monkeypatch.setattr(paperless, "update_document", _patch)

    first = api_client.post("/writeback/jobs", json={"doc_ids": [571]})
    second = api_client.post("/writeback/jobs", json={"doc_ids": [572]})
    assert first.status_code == 200
    assert second.status_code == 200

    pending_exec = api_client.post("/writeback/jobs/execute-pending", json={"dry_run": False, "limit": 0})
    assert pending_exec.status_code == 200
    payload = pending_exec.json()
    assert payload["processed"] >= 2
    assert payload["completed"] >= 1
    assert payload["failed"] >= 1
    statuses = {str(row.get("status") or "") for row in payload.get("results", [])}
    assert "completed" in statuses
    assert "failed" in statuses

    history = api_client.get("/writeback/history", params={"limit": 10})
    assert history.status_code == 200
    history_statuses = {str(item.get("status") or "") for item in history.json().get("items", [])}
    assert "completed" in history_statuses
    assert "failed" in history_statuses


def test_writeback_execute_now_reports_httpx_status_error_partial_failure(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.services.integrations import paperless

    _insert_document(581, "Shared title 581")
    _insert_document(582, "Local title 582")
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        doc = db.query(Document).filter(Document.id == 581).first()
        doc.notes = [DocumentNote(id=9101, note="Zusammenfassung 581\nKI-Zusammenfassung")]
        db.commit()

    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda _settings, doc_id: {
            "id": doc_id,
            "title": "Shared title 581" if int(doc_id) == 581 else "Remote title 582",
            "created": None,
            "modified": "2026-02-10T10:00:00Z",
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    def _note_with_status_error(*_args: Any, **_kwargs: Any) -> None:
        request = httpx.Request("POST", "http://paperless.local/api/documents/581/notes/")
        response = httpx.Response(500, request=request)
        raise httpx.HTTPStatusError("Paperless 500", request=request, response=response)

    patch_calls: dict[int, int] = {}

    def _patch(_settings: Any, doc_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        patch_calls[int(doc_id)] = patch_calls.get(int(doc_id), 0) + 1
        return {"id": doc_id, **payload}

    monkeypatch.setattr(paperless, "add_document_note", _note_with_status_error)
    monkeypatch.setattr(paperless, "update_document", _patch)
    monkeypatch.setattr(paperless, "delete_document_note", lambda *args, **kwargs: None)
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    result = api_client.post("/writeback/execute-now", json={"doc_ids": [581, 582]})
    assert result.status_code == 200
    payload = result.json()
    assert payload["docs_selected"] == 2
    assert payload["docs_changed"] == 2
    assert payload["doc_ids"] == [582]
    assert payload["failed_doc_ids"] == [581]
    assert len(payload["errors"]) == 1
    assert payload["errors"][0]["doc_id"] == 581
    assert payload["errors"][0]["method"] == "POST"
    assert payload["errors"][0]["path"] == "/api/documents/581/notes/"
    assert "Paperless 500" in payload["errors"][0]["error"]
    assert patch_calls.get(582, 0) >= 1

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        audit_582 = (
            db.query(SuggestionAudit)
            .filter(
                SuggestionAudit.doc_id == 582,
                SuggestionAudit.action == "apply_to_document:writeback",
            )
            .one_or_none()
        )
        assert audit_582 is not None
        audit_581 = (
            db.query(SuggestionAudit)
            .filter(
                SuggestionAudit.doc_id == 581,
                SuggestionAudit.action == "apply_to_document:writeback",
            )
            .one_or_none()
        )
        assert audit_581 is None
        assert db.query(WritebackJob).all() == []


def test_writeback_execute_now_continues_after_httpx_connect_error(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.services.integrations import paperless

    _insert_document(591, "Local title 591")
    _insert_document(592, "Local title 592")
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda _settings, doc_id: {
            "id": doc_id,
            "title": f"Remote title {doc_id}",
            "created": None,
            "modified": "2026-02-10T10:00:00Z",
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    def _patch(_settings: Any, doc_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        if int(doc_id) == 591:
            raise httpx.ConnectError("connection refused")
        return {"id": doc_id, **payload}

    monkeypatch.setattr(paperless, "update_document", _patch)
    monkeypatch.setattr(paperless, "add_document_note", lambda *args, **kwargs: {"id": 1})
    monkeypatch.setattr(paperless, "delete_document_note", lambda *args, **kwargs: None)
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    result = api_client.post("/writeback/execute-now", json={"doc_ids": [591, 592]})
    assert result.status_code == 200
    payload = result.json()
    assert payload["doc_ids"] == [592]
    assert payload["failed_doc_ids"] == [591]
    assert len(payload["errors"]) == 1
    assert payload["errors"][0]["doc_id"] == 591
    assert payload["errors"][0]["method"] == "PATCH"
    assert payload["errors"][0]["path"] == "/api/documents/591/"
    assert "connection refused" in payload["errors"][0]["error"]

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        audit_592 = (
            db.query(SuggestionAudit)
            .filter(
                SuggestionAudit.doc_id == 592,
                SuggestionAudit.action == "apply_to_document:writeback",
            )
            .one_or_none()
        )
        assert audit_592 is not None
        audit_591 = (
            db.query(SuggestionAudit)
            .filter(
                SuggestionAudit.doc_id == 591,
                SuggestionAudit.action == "apply_to_document:writeback",
            )
            .one_or_none()
        )
        assert audit_591 is None
        assert db.query(WritebackJob).all() == []


def test_writeback_direct_execute_httpx_error_returns_400_not_500(
    api_client: Any, monkeypatch: Any
) -> None:
    from app.services.integrations import paperless

    _insert_document(593, "Shared title 593")
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        doc = db.query(Document).filter(Document.id == 593).first()
        doc.notes = [DocumentNote(id=9301, note="Zusammenfassung 593\nKI-Zusammenfassung")]
        db.commit()

    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda _settings, doc_id: {
            "id": doc_id,
            "title": "Shared title 593",
            "created": None,
            "modified": "2026-02-10T10:00:00Z",
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )
    monkeypatch.setattr(
        paperless,
        "update_document",
        lambda _settings, doc_id, payload: {"id": doc_id, **payload},
    )

    def _note_with_connect_error(*_args: Any, **_kwargs: Any) -> None:
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(paperless, "add_document_note", _note_with_connect_error)
    monkeypatch.setattr(paperless, "delete_document_note", lambda *args, **kwargs: None)
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    result = api_client.post(
        "/writeback/documents/593/execute-direct",
        json={"known_paperless_modified": "2026-02-10T10:00:00Z", "resolutions": {}},
    )
    assert result.status_code == 400
    assert "boom" in str(result.json().get("detail"))

    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        audit_593 = (
            db.query(SuggestionAudit)
            .filter(
                SuggestionAudit.doc_id == 593,
                SuggestionAudit.action == "apply_to_document:writeback",
            )
            .one_or_none()
        )
        assert audit_593 is None
