from __future__ import annotations

import os

from sqlalchemy import text
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Document, DocumentPendingTag, SuggestionAudit, Tag, WritebackJob


def _insert_document(doc_id: int, title: str):
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Document(id=doc_id, title=title))
        db.commit()


def _insert_tag(tag_id: int, name: str):
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(Tag(id=tag_id, name=name))
        db.commit()


def _insert_pending_tags(doc_id: int, names: list[str]):
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with Session(engine) as db:
        db.add(
            DocumentPendingTag(
                doc_id=doc_id,
                names_json=__import__("json").dumps(names, ensure_ascii=False),
                updated_at="2026-02-10T10:10:00+00:00",
            )
        )
        db.commit()


def test_writeback_job_create_and_execute_dry_run(api_client, monkeypatch):
    from app.services.integrations import paperless

    _insert_document(501, "Local title")

    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
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


def test_writeback_job_execute_real_calls_paperless(api_client, monkeypatch):
    from app.services.integrations import paperless

    _insert_document(502, "Local title 502")

    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
            "id": doc_id,
            "title": "Remote title 502",
            "document_date": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    calls = {"patch": 0}

    def _fake_patch(settings, doc_id, payload):
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


def test_writeback_job_create_deduplicates_pending(api_client, monkeypatch):
    from app.services.integrations import paperless

    _insert_document(503, "Local title 503")
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
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


def test_writeback_execute_pending_runs_all(api_client, monkeypatch):
    from app.services.integrations import paperless

    _insert_document(504, "Local title 504")
    _insert_document(505, "Local title 505")
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
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


def test_writeback_job_delete_removes_pending_job(api_client, monkeypatch):
    from app.services.integrations import paperless

    _insert_document(530, "Local title 530")
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
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


def test_writeback_execute_now_executes_without_queue(api_client, monkeypatch):
    from app.services.integrations import paperless

    _insert_document(506, "Local title 506")
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
            "id": doc_id,
            "title": "Remote title 506",
            "created": None,
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )
    calls = {"patch": 0}

    def _fake_patch(settings, doc_id, payload):
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
    assert calls["patch"] >= 1


def test_writeback_execute_now_rejects_without_valid_doc_ids(api_client, monkeypatch):
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")
    result = api_client.post("/writeback/execute-now", json={"doc_ids": [0, -1]})
    assert result.status_code == 400
    assert "No valid doc_ids provided" in str(result.json().get("detail"))


def test_writeback_execute_now_updates_local_modified_and_review_timestamp(api_client, monkeypatch):
    from app.services.integrations import paperless

    _insert_document(510, "Local title 510")
    remote_modified = "2026-02-12T18:00:00+00:00"
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
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
        lambda settings, doc_id, payload: {"id": doc_id, **payload},
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


def test_writeback_direct_requires_resolution_when_modified_changed(api_client, monkeypatch):
    from app.services.integrations import paperless

    _insert_document(507, "Local title 507")
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
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


def test_writeback_execute_now_creates_missing_paperless_tags(api_client, monkeypatch):
    from app.services.integrations import paperless
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.models import Document

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
        lambda settings, doc_id: {
            "id": doc_id,
            "title": "Remote title 508",
            "created": "2026-02-01",
            "modified": "2026-02-10T10:00:00Z",
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )

    monkeypatch.setattr(paperless, "list_all_tags", lambda settings: [])
    monkeypatch.setattr(paperless, "create_tag", lambda settings, name: {"id": 777, "name": name})
    patch_payloads: list[dict] = []
    monkeypatch.setattr(
        paperless,
        "update_document",
        lambda settings, doc_id, payload: patch_payloads.append(payload) or {"id": doc_id, **payload},
    )
    monkeypatch.setattr(paperless, "add_document_note", lambda *args, **kwargs: {"id": 1})
    monkeypatch.setattr(paperless, "delete_document_note", lambda *args, **kwargs: None)
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "1")

    result = api_client.post("/writeback/execute-now", json={"doc_ids": [508]})
    assert result.status_code == 200
    assert patch_payloads
    assert patch_payloads[0].get("tags") == [777]


def test_writeback_direct_executes_for_pending_tags_only(api_client, monkeypatch):
    from app.services.integrations import paperless
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.models import Document

    _insert_document(509, "Doc 509")
    _insert_pending_tags(509, ["BrandNew"])
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
            "id": doc_id,
            "title": "Doc 509",
            "created": "2026-02-01",
            "modified": "2026-02-10T10:00:00Z",
            "correspondent": None,
            "tags": [],
            "notes": [],
        },
    )
    monkeypatch.setattr(paperless, "list_all_tags", lambda settings: [])
    monkeypatch.setattr(paperless, "create_tag", lambda settings, name: {"id": 778, "name": name})
    patch_payloads: list[dict] = []
    monkeypatch.setattr(
        paperless,
        "update_document",
        lambda settings, doc_id, payload: patch_payloads.append(payload) or {"id": doc_id, **payload},
    )
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


def test_writeback_job_create_rejects_without_valid_doc_ids(api_client):
    create_resp = api_client.post("/writeback/jobs", json={"doc_ids": [0, -5]})
    assert create_resp.status_code == 400
    assert "No valid doc_ids provided" in str(create_resp.json().get("detail"))


def test_writeback_job_create_rejects_when_no_changes_detected(api_client, monkeypatch):
    from app.services.integrations import paperless

    _insert_document(540, "Same title")
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
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


def test_writeback_job_get_returns_404_for_missing_job(api_client):
    response = api_client.get("/writeback/jobs/999999")
    assert response.status_code == 404
    assert "Writeback job not found" in str(response.json().get("detail"))


def test_writeback_job_delete_rejects_running_job(api_client):
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


def test_writeback_jobs_list_returns_503_when_table_missing(api_client):
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE writeback_jobs"))

    response = api_client.get("/writeback/jobs")
    assert response.status_code == 503
    assert "Writeback jobs table is missing" in str(response.json().get("detail"))


def test_writeback_job_execute_rejects_real_execution_when_disabled(api_client, monkeypatch):
    from app.services.integrations import paperless

    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "0")
    _insert_document(560, "Local title 560")
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
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


def test_writeback_execute_pending_rejects_real_execution_when_disabled(api_client, monkeypatch):
    monkeypatch.setenv("WRITEBACK_EXECUTE_ENABLED", "0")
    result = api_client.post("/writeback/jobs/execute-pending", json={"dry_run": False, "limit": 1})
    assert result.status_code == 400
    assert "WRITEBACK_EXECUTE_ENABLED=1" in str(result.json().get("detail"))


def test_writeback_job_execute_returns_503_when_table_missing(api_client):
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE writeback_jobs"))

    response = api_client.post("/writeback/jobs/1/execute", json={"dry_run": True})
    assert response.status_code == 503
    assert "Writeback jobs table is missing" in str(response.json().get("detail"))


def test_writeback_history_limit_zero_clamps_and_filters_statuses(api_client):
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


def test_writeback_history_returns_503_when_table_missing(api_client):
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE writeback_jobs"))

    response = api_client.get("/writeback/history")
    assert response.status_code == 503
    assert "Writeback jobs table is missing" in str(response.json().get("detail"))


def test_writeback_job_lifecycle_execute_pending_and_history_with_failure(api_client, monkeypatch):
    from app.services.integrations import paperless

    _insert_document(571, "Local title 571")
    _insert_document(572, "Local title 572")
    monkeypatch.setattr(
        paperless,
        "get_document",
        lambda settings, doc_id: {
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

    def _patch(settings, doc_id, payload):
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
