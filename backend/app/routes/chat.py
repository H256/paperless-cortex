from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends

from app.api_models import (
    ChatFollowupsRequest,
    ChatFollowupsResponse,
    ChatRequest,
    ChatResponse,
    EvidenceResolveRequest,
    EvidenceResolveResponse,
)
from app.db import get_db
from app.deps import get_settings
from app.services.ai.chat import answer_question, generate_followups
from app.services.search.evidence import resolve_evidence_matches

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.config import Settings

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> Any:
    logger.info(
        "Chat request question_len=%s top_k=%s source=%s conversation_id=%s",
        len(payload.question),
        payload.top_k,
        payload.source or "all",
        (payload.conversation_id or "new"),
    )
    return answer_question(
        settings,
        question=payload.question,
        top_k=max(1, min(payload.top_k, 20)),
        source=payload.source,
        min_quality=payload.min_quality,
        doc_id=payload.doc_id,
        relationship_mode=payload.relationship_mode,
        history=payload.history or [],
        conversation_id=payload.conversation_id,
        db=db,
    )


@router.post("/stream")
def chat_stream(
    payload: ChatRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> Any:
    logger.info(
        "Chat stream request question_len=%s top_k=%s source=%s conversation_id=%s",
        len(payload.question),
        payload.top_k,
        payload.source or "all",
        (payload.conversation_id or "new"),
    )
    return answer_question(
        settings,
        question=payload.question,
        top_k=max(1, min(payload.top_k, 20)),
        source=payload.source,
        min_quality=payload.min_quality,
        doc_id=payload.doc_id,
        relationship_mode=payload.relationship_mode,
        history=payload.history or [],
        conversation_id=payload.conversation_id,
        stream=True,
        db=db,
    )


@router.post("/followups", response_model=ChatFollowupsResponse)
def chat_followups(
    payload: ChatFollowupsRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, list[str]]:
    logger.info("Chat followups question_len=%s", len(payload.question))
    questions = generate_followups(
        settings,
        question=payload.question,
        answer=payload.answer,
        citations=[item.model_dump() for item in (payload.citations or [])],
        doc_id=payload.doc_id,
        relationship_mode=payload.relationship_mode,
    )
    return {"questions": questions}


@router.post("/resolve-evidence", response_model=EvidenceResolveResponse)
def resolve_evidence(
    payload: EvidenceResolveRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    matches = resolve_evidence_matches(
        [
            {
                "doc_id": item.doc_id,
                "page": item.page,
                "snippet": item.snippet,
                "source": item.source,
                "bbox": item.bbox,
            }
            for item in payload.citations
        ],
        max_pages=payload.max_pages,
        settings=settings,
        db=db,
    )
    return {"count": len(matches), "matches": matches}
