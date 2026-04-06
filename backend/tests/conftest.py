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


def _set_test_env(db_path: Path) -> None:
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_path}"
    os.environ["QUEUE_ENABLED"] = "0"
    os.environ["REDIS_HOST"] = "test-redis"
    os.environ["ENABLE_VISION_OCR"] = "1"
    os.environ["QDRANT_URL"] = "http://test-qdrant:6333"
    os.environ["RUNTIME_SETTINGS_MASTER_KEY"] = "xjFFDGjXcmcrwlFe0Vm9Dq4mOAcN2DERPslm9jqISqg="


@pytest.fixture()
def session_factory() -> Any:
    db_path = Path(tempfile.gettempdir()) / f"paperless_intelligence_test_{uuid.uuid4().hex}.db"
    _set_test_env(db_path)

    engine = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    from app.services.documents.dashboard_cache import invalidate_dashboard_cache
    from app.services.documents.document_stats_cache import invalidate_document_stats_cache
    from app.services.documents.documents_list_cache import invalidate_documents_list_cache
    from app.services.documents.local_document_cache import invalidate_local_document_cache
    from app.services.documents.page_texts_cache import invalidate_page_texts_cache
    from app.services.runtime.metrics import clear_metrics
    from app.services.writeback.writeback_preview_cache import invalidate_writeback_preview_cache

    invalidate_dashboard_cache()
    invalidate_local_document_cache()
    invalidate_page_texts_cache()
    invalidate_document_stats_cache()
    invalidate_documents_list_cache()
    invalidate_writeback_preview_cache()
    clear_metrics()
    return testing_session_local


@pytest.fixture()
def api_client(monkeypatch: Any) -> Any:
    db_path = Path(tempfile.gettempdir()) / f"paperless_intelligence_test_{uuid.uuid4().hex}.db"
    _set_test_env(db_path)

    import app.main as main

    importlib.reload(main)
    from app.services.documents.dashboard_cache import invalidate_dashboard_cache
    from app.services.documents.document_stats_cache import invalidate_document_stats_cache
    from app.services.documents.documents_list_cache import invalidate_documents_list_cache
    from app.services.documents.local_document_cache import invalidate_local_document_cache
    from app.services.documents.page_texts_cache import invalidate_page_texts_cache
    from app.services.runtime.metrics import clear_metrics
    from app.services.writeback.writeback_preview_cache import invalidate_writeback_preview_cache

    invalidate_dashboard_cache()
    invalidate_local_document_cache()
    invalidate_page_texts_cache()
    invalidate_document_stats_cache()
    invalidate_documents_list_cache()
    invalidate_writeback_preview_cache()
    clear_metrics()

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
