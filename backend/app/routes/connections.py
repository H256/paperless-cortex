from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from app.api_models import ConnectionStatus
from app.deps import get_settings
from app.services.integrations.connections import run_all

if TYPE_CHECKING:
    from app.config import Settings

router = APIRouter(prefix="/connections", tags=["connections"])


@router.get("/", response_model=list[ConnectionStatus])
def connections(settings: Settings = Depends(get_settings)) -> list[dict[str, object]]:
    return run_all(settings)
