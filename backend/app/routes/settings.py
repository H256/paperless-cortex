from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from app.api_models import (
    ModelProviderDiscoveryRequest,
    ModelProviderDiscoveryResponse,
    ModelProviderSettingsResponse,
    ModelProviderSettingsUpdateRequest,
)
from app.config import load_settings
from app.deps import get_settings
from app.services.runtime.model_providers import (
    ROLE_NAMES,
    discover_models,
    role_payload,
    upsert_provider_override,
)

if TYPE_CHECKING:
    from app.config import Settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/model-providers", response_model=ModelProviderSettingsResponse)
def get_model_providers(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    return {"items": [role_payload(settings, role) for role in ROLE_NAMES]}


@router.put("/model-providers", response_model=ModelProviderSettingsResponse)
def update_model_providers(
    request: ModelProviderSettingsUpdateRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    valid_roles = set(ROLE_NAMES)
    for item in request.items:
        role = str(item.role or "").strip().lower()
        if role not in valid_roles:
            raise HTTPException(status_code=400, detail=f"Invalid role: {item.role}")
        try:
            upsert_provider_override(
                settings,
                role=role,  # type: ignore[arg-type]
                base_url=item.base_url,
                model=item.model,
                api_key=item.api_key,
                clear_api_key=bool(item.clear_api_key),
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    refreshed_settings = load_settings()
    return {"items": [role_payload(refreshed_settings, role) for role in ROLE_NAMES]}


@router.post("/model-providers/discover", response_model=ModelProviderDiscoveryResponse)
def discover_model_providers(
    request: ModelProviderDiscoveryRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    ok, detail, models = discover_models(
        base_url=request.base_url,
        api_key=request.api_key,
        verify_tls=settings.http.verify_tls,
    )
    return {"ok": ok, "detail": detail, "models": models}
