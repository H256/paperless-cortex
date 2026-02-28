from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings
from app.deps import get_settings
from app.services.integrations.connections import run_all
from app.api_models import ConnectionStatus

router = APIRouter(prefix="/connections", tags=["connections"])


@router.get("/", response_model=list[ConnectionStatus])
def connections(settings: Settings = Depends(get_settings)):
    return run_all(settings)
