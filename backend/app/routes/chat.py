from __future__ import annotations

from fastapi import APIRouter, Depends
import logging

from app.config import Settings
from app.deps import get_settings
from app.services.chat import answer_question
from app.services.evidence import resolve_evidence_matches
from app.api_models import (
    ChatRequest,
    ChatResponse,
    EvidenceResolveRequest,
    EvidenceResolveResponse,
)

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest, settings: Settings = Depends(get_settings)):
    logger.info("Chat request question_len=%s top_k=%s", len(payload.question), payload.top_k)
    return answer_question(
        settings,
        question=payload.question,
        top_k=max(1, min(payload.top_k, 20)),
        source=payload.source,
        min_quality=payload.min_quality,
        history=payload.history or [],
    )


@router.post("/stream")
def chat_stream(payload: ChatRequest, settings: Settings = Depends(get_settings)):
    logger.info("Chat stream request question_len=%s top_k=%s", len(payload.question), payload.top_k)
    return answer_question(
        settings,
        question=payload.question,
        top_k=max(1, min(payload.top_k, 20)),
        source=payload.source,
        min_quality=payload.min_quality,
        history=payload.history or [],
        stream=True,
    )


@router.post("/resolve-evidence", response_model=EvidenceResolveResponse)
def resolve_evidence(payload: EvidenceResolveRequest):
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
    )
    return {"count": len(matches), "matches": matches}
