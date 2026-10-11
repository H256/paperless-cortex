from __future__ import annotations

import importlib
import os
import shutil
import subprocess
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

import app.config as _app_config  # noqa: E402
from app.models import Base  # noqa: E402

# A developer `.env` in the repository root must not leak into the tests: it would set
# PAPERLESS_BASE_URL/API token, LLM and vector-store settings, so tests could take
# production code paths (or even talk to real services) instead of the mocked ones.
# `load_dotenv` never overrides variables that are already set, so everything the
# tests rely on is set explicitly in `_set_test_env` or by the individual test.
_app_config._load_env = lambda _repo_root: None


def _set_test_env(db_path: Path) -> None:
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_path}"
    os.environ["QUEUE_ENABLED"] = "0"
    os.environ["REDIS_HOST"] = "test-redis"
    os.environ["ENABLE_VISION_OCR"] = "1"
    os.environ["QDRANT_URL"] = "http://test-qdrant:6333"
    os.environ["RUNTIME_SETTINGS_MASTER_KEY"] = "xjFFDGjXcmcrwlFe0Vm9Dq4mOAcN2DERPslm9jqISqg="


_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "testserver"}


@pytest.fixture(autouse=True)
def _block_real_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail fast when a test would send a real HTTP request.

    Tests must stub the Paperless, LLM and vector-store clients. An unstubbed call used to
    reach whatever instance the environment points at (and was often swallowed as a 404).
    Loopback/in-process hosts stay allowed; `httpx.MockTransport` is unaffected.
    """
    import httpx

    original = httpx.HTTPTransport.handle_request

    def _guarded(self: Any, request: Any) -> Any:
        if request.url.host not in _LOOPBACK_HOSTS:
            raise RuntimeError(
                f"Real network access in a test: {request.method} {request.url}. "
                "Stub the client (e.g. monkeypatch the paperless/llm function)."
            )
        return original(self, request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _guarded)


def _bash_candidates() -> list[str]:
    candidates: list[str] = []
    found = shutil.which("bash")
    if found:
        candidates.append(found)
    if sys.platform == "win32":
        # `bash` on PATH is often the WSL launcher; Git for Windows ships a real one.
        for base in (
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("LOCALAPPDATA") and str(Path(os.environ["LOCALAPPDATA"]) / "Programs"),
        ):
            if not base:
                continue
            for relative in ("Git/bin/bash.exe", "Git/usr/bin/bash.exe"):
                path = Path(base) / relative
                if path.is_file():
                    candidates.append(str(path))
    return candidates


@pytest.fixture(scope="session")
def posix_bash() -> str:
    """Path of a working POSIX bash, or skip: the Docker entrypoint is a bash script."""
    for candidate in _bash_candidates():
        try:
            result = subprocess.run(
                [candidate, "-c", "echo ok"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0 and result.stdout.strip() == "ok":
            return candidate
    pytest.skip("no working POSIX bash available")


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
    from app.config import reset_settings_cache
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
    reset_settings_cache()
    return testing_session_local


@pytest.fixture()
def api_client(monkeypatch: Any) -> Any:
    db_path = Path(tempfile.gettempdir()) / f"paperless_intelligence_test_{uuid.uuid4().hex}.db"
    _set_test_env(db_path)

    import app.main as main

    importlib.reload(main)
    from app.config import reset_settings_cache
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
    reset_settings_cache()

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
