from __future__ import annotations

import importlib
import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from collections.abc import Generator

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.models import Base  # noqa: E402


@pytest.fixture()
def session_factory() -> Any:
    db_path = Path(tempfile.gettempdir()) / f"paperless_intelligence_test_{uuid.uuid4().hex}.db"
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_path}"
    os.environ["QUEUE_ENABLED"] = "0"

    engine = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return testing_session_local


@pytest.fixture()
def api_client(monkeypatch: Any) -> Any:
    db_path = Path(tempfile.gettempdir()) / f"paperless_intelligence_test_{uuid.uuid4().hex}.db"
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_path}"
    os.environ["QUEUE_ENABLED"] = "0"

    import app.main as main

    importlib.reload(main)

    engine = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    from app.db import get_db

    def override_get_db() -> Generator[Session]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    main.api.dependency_overrides[get_db] = override_get_db

    from fastapi.testclient import TestClient

    return TestClient(main.api)
