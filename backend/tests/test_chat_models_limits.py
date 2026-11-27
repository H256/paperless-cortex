from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api_models import (
    CHAT_LIST_MAX,
    CHAT_QUESTION_MAX,
    CHAT_TEXT_MAX,
    ChatFollowupsRequest,
    ChatHistoryItem,
    ChatRequest,
)


def test_normal_chat_request_is_accepted() -> None:
    request = ChatRequest(
        question="What is the invoice total?",
        history=[ChatHistoryItem(question="q", answer="a")] * 12,
    )
    assert len(request.history or []) == 12


def test_oversized_question_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(question="x" * (CHAT_QUESTION_MAX + 1))


def test_oversized_history_is_rejected() -> None:
    item = ChatHistoryItem(question="q", answer="a")
    with pytest.raises(ValidationError):
        ChatRequest(question="q", history=[item] * (CHAT_LIST_MAX + 1))
    with pytest.raises(ValidationError):
        ChatHistoryItem(question="q", answer="a" * (CHAT_TEXT_MAX + 1))


def test_oversized_followup_answer_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ChatFollowupsRequest(question="q", answer="a" * (CHAT_TEXT_MAX + 1))
