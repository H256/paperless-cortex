from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, load_settings
from app.services.connections import run_all
from app.api_models import ConnectionStatus

router = APIRouter(prefix="/connections", tags=["connections"])


def settings_dep() -> Settings:
    return load_settings()


@router.get("/", response_model=list[ConnectionStatus])
def connections(settings: Settings = Depends(settings_dep)):
    return run_all(settings)
