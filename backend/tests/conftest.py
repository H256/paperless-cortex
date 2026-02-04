from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base


@pytest.fixture()
def api_client(monkeypatch):
    db_path = Path("/tmp/paperless_intelligence_test.db")
    if db_path.exists():
        db_path.unlink()
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_path}"
    os.environ["QUEUE_ENABLED"] = "0"

    import app.main as main

    importlib.reload(main)

    engine = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    from app.db import get_db

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    main.api.dependency_overrides[get_db] = override_get_db

    from fastapi.testclient import TestClient

    return TestClient(main.api)
