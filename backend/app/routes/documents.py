from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, load_settings
from app.services import paperless

router = APIRouter(prefix="/documents", tags=["documents"])


def settings_dep() -> Settings:
    return load_settings()


@router.get("/")
def list_documents(
    page: int = 1,
    page_size: int = 20,
    ordering: str | None = None,
    correspondent__id: int | None = None,
    tags__id: int | None = None,
    document_date__gte: str | None = None,
    document_date__lte: str | None = None,
    settings: Settings = Depends(settings_dep),
):
    return paperless.list_documents(
        settings,
        page=page,
        page_size=page_size,
        ordering=ordering,
        correspondent__id=correspondent__id,
        tags__id=tags__id,
        document_date__gte=document_date__gte,
        document_date__lte=document_date__lte,
    )


@router.get("/{doc_id}")
def get_document(doc_id: int, settings: Settings = Depends(settings_dep)):
    return paperless.get_document(settings, doc_id)
