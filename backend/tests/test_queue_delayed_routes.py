from __future__ import annotations

import importlib
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base


def _build_api_client(queue_enabled: bool) -> Any:
    db_path = Path(tempfile.gettempdir()) / f"paperless_intelligence_test_{uuid.uuid4().hex}.db"
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_path}"
    os.environ["QUEUE_ENABLED"] = "1" if queue_enabled else "0"

    import app.main as main

    importlib.reload(main)

    engine = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    from app.db import get_db

    def override_get_db() -> Any:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    main.api.dependency_overrides[get_db] = override_get_db

    from fastapi.testclient import TestClient

    return TestClient(main.api)


def test_queue_delayed_disabled_returns_empty() -> None:
    client = _build_api_client(queue_enabled=False)
    response = client.get("/queue/delayed")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["items"] == []
