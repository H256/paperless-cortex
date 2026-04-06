from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime
from functools import lru_cache
from typing import TYPE_CHECKING, Literal

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.config import ModelProviderRuntime, ModelProvidersRuntime

if TYPE_CHECKING:
    from app.config import Settings
    from app.models import RuntimeModelProviderOverride

Role = Literal["text", "chat", "embedding", "vision"]
ROLE_NAMES: tuple[Role, ...] = ("text", "chat", "embedding", "vision")
logger = logging.getLogger(__name__)


@lru_cache(maxsize=4)
def _get_session_factory(database_url: str) -> sessionmaker:
    engine = create_engine(database_url, pool_pre_ping=True)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _normalize_url(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return normalized.rstrip("/")


def _mask_api_key(value: str | None) -> str | None:
    if not value:
        return None
    trimmed = str(value).strip()
    if not trimmed:
        return None
    suffix = trimmed[-4:] if len(trimmed) >= 4 else trimmed
    return f"...{suffix}"


def _master_key(settings: Settings) -> str:
    key = str(settings.runtime_override.master_key or "").strip()
    if not key:
        raise RuntimeError("RUNTIME_SETTINGS_MASTER_KEY not set")
    return key


def _fernet(settings: Settings) -> Fernet:
    key = _master_key(settings)
    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Invalid RUNTIME_SETTINGS_MASTER_KEY") from exc


def encrypt_api_key(settings: Settings, api_key: str) -> str:
    return _fernet(settings).encrypt(api_key.encode("utf-8")).decode("utf-8")


def decrypt_api_key(settings: Settings, encrypted_api_key: str) -> str:
    try:
        return _fernet(settings).decrypt(encrypted_api_key.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError) as exc:
        raise RuntimeError("Failed to decrypt stored runtime API key") from exc


def _default_provider_for_role(settings: Settings, role: Role) -> ModelProviderRuntime:
    if role == "text":
        return ModelProviderRuntime(
            base_url=_normalize_url(settings.ocr_chat_base_url or settings.llm_base_url),
            api_key=settings.llm_api_key,
            model=settings.text_model,
        )
    if role == "chat":
        return ModelProviderRuntime(
            base_url=_normalize_url(settings.ocr_chat_base_url or settings.llm_base_url),
            api_key=settings.llm_api_key,
            model=settings.chat_model or settings.text_model,
        )
    if role == "embedding":
        return ModelProviderRuntime(
            base_url=_normalize_url(settings.llm_base_url),
            api_key=settings.llm_api_key,
            model=settings.embedding_model,
        )
    return ModelProviderRuntime(
        base_url=_normalize_url(settings.ocr_vision_base_url or settings.llm_base_url),
        api_key=settings.llm_api_key,
        model=settings.vision_model,
    )


def _load_override_rows(settings: Settings) -> dict[str, RuntimeModelProviderOverride]:
    if not settings.database_url:
        return {}
    try:
        from app.models import RuntimeModelProviderOverride

        factory = _get_session_factory(settings.database_url)
        with factory() as db:
            rows = db.query(RuntimeModelProviderOverride).all()
            return {str(row.role): row for row in rows}
    except SQLAlchemyError as exc:
        logger.warning("Runtime model overrides unavailable detail=%s", exc.__class__.__name__)
        return {}


def apply_runtime_model_overrides(settings: Settings) -> Settings:
    rows = _load_override_rows(settings)
    providers: dict[str, ModelProviderRuntime] = {}
    for role in ROLE_NAMES:
        default_provider = _default_provider_for_role(settings, role)
        row = rows.get(role)
        if row is None:
            providers[role] = default_provider
            continue
        api_key = default_provider.api_key
        if row.api_key_encrypted:
            try:
                api_key = decrypt_api_key(settings, row.api_key_encrypted)
            except RuntimeError:
                logger.warning("Runtime API key decrypt failed role=%s", role)
        providers[role] = ModelProviderRuntime(
            base_url=_normalize_url(row.base_url) if row.base_url is not None else default_provider.base_url,
            api_key=api_key,
            model=str(row.model).strip() if row.model is not None and str(row.model).strip() else default_provider.model,
            base_url_overridden=row.base_url is not None,
            api_key_overridden=row.api_key_encrypted is not None,
            model_overridden=row.model is not None,
            api_key_hint=row.api_key_hint or _mask_api_key(api_key),
        )

    runtime = ModelProvidersRuntime(
        text=providers["text"],
        chat=providers["chat"],
        embedding=providers["embedding"],
        vision=providers["vision"],
    )
    return replace(
        settings,
        llm=replace(
            settings.llm,
            base_url=runtime.text.base_url,
            api_key=runtime.text.api_key,
            text_model=runtime.text.model,
            chat_model=runtime.chat.model,
        ),
        embeddings=replace(settings.embeddings, model=runtime.embedding.model),
        vision=replace(
            settings.vision,
            model=runtime.vision.model,
            ocr_chat_base_url=runtime.chat.base_url,
            ocr_vision_base_url=runtime.vision.base_url,
        ),
        model_providers=runtime,
    )


def provider_state(settings: Settings, role: Role) -> ModelProviderRuntime:
    return getattr(settings.model_providers, role)


def provider_base_url(settings: Settings, role: Role) -> str | None:
    return provider_state(settings, role).base_url


def provider_api_key(settings: Settings, role: Role) -> str | None:
    return provider_state(settings, role).api_key


def provider_model(settings: Settings, role: Role) -> str | None:
    return provider_state(settings, role).model


def role_payload(settings: Settings, role: Role) -> dict[str, object]:
    provider = provider_state(settings, role)
    return {
        "role": role,
        "base_url": provider.base_url,
        "model": provider.model,
        "api_key_configured": bool(provider.api_key),
        "api_key_hint": provider.api_key_hint or _mask_api_key(provider.api_key),
        "base_url_overridden": provider.base_url_overridden,
        "model_overridden": provider.model_overridden,
        "api_key_overridden": provider.api_key_overridden,
    }


def upsert_provider_override(
    settings: Settings,
    *,
    role: Role,
    base_url: str | None,
    model: str | None,
    api_key: str | None = None,
    clear_api_key: bool = False,
) -> None:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL not set")
    from app.models import RuntimeModelProviderOverride

    factory = _get_session_factory(settings.database_url)
    with factory() as db:
        row = db.get(RuntimeModelProviderOverride, role)
        if row is None:
            row = RuntimeModelProviderOverride(role=role)
            db.add(row)
        row.base_url = _normalize_url(base_url)
        row.model = str(model).strip() if model is not None and str(model).strip() else None
        if clear_api_key:
            row.api_key_encrypted = None
            row.api_key_hint = None
        elif api_key is not None:
            normalized_key = str(api_key).strip()
            if normalized_key:
                row.api_key_encrypted = encrypt_api_key(settings, normalized_key)
                row.api_key_hint = _mask_api_key(normalized_key)
        row.updated_at = datetime.now(UTC).isoformat()
        db.commit()


def discover_models(
    *,
    base_url: str | None,
    api_key: str | None,
    verify_tls: bool,
) -> tuple[bool, str, list[str]]:
    normalized_base_url = _normalize_url(base_url)
    if not normalized_base_url:
        return False, "Base URL not set", []
    headers: dict[str, str] = {}
    normalized_api_key = str(api_key or "").strip()
    if normalized_api_key:
        headers["Authorization"] = f"Bearer {normalized_api_key}"
    try:
        with httpx.Client(timeout=10, verify=verify_tls) as client:
            response = client.get(f"{normalized_base_url}/v1/models", headers=headers)
            response.raise_for_status()
        payload = response.json()
        data = payload.get("data")
        if not isinstance(data, list):
            return False, "Invalid models payload", []
        models = sorted(
            {
                str(item.get("id")).strip()
                for item in data
                if isinstance(item, dict) and str(item.get("id") or "").strip()
            }
        )
        return True, "ok", models
    except httpx.HTTPStatusError as exc:
        return False, f"HTTP {exc.response.status_code}", []
    except httpx.HTTPError as exc:
        return False, exc.__class__.__name__, []
