from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, load_settings
from app.services import paperless
from app.api_models import TagsPageResponse, CorrespondentsPageResponse, DocumentTypeResponse, CorrespondentResponse

router = APIRouter(tags=["meta"])


def settings_dep() -> Settings:
    return load_settings()


@router.get("/tags", response_model=TagsPageResponse)
def list_tags(page: int = 1, page_size: int = 50, settings: Settings = Depends(settings_dep)):
    return paperless.list_tags(settings, page=page, page_size=page_size)


@router.get("/correspondents", response_model=CorrespondentsPageResponse)
def list_correspondents(
    page: int = 1, page_size: int = 50, settings: Settings = Depends(settings_dep)
):
    return paperless.list_correspondents(settings, page=page, page_size=page_size)


@router.get("/document-types/{doc_type_id}", response_model=DocumentTypeResponse)
def get_document_type(doc_type_id: int, settings: Settings = Depends(settings_dep)):
    return paperless.get_document_type(settings, doc_type_id)


@router.get("/correspondents/{correspondent_id}", response_model=CorrespondentResponse)
def get_correspondent(correspondent_id: int, settings: Settings = Depends(settings_dep)):
    return paperless.get_correspondent(settings, correspondent_id)
