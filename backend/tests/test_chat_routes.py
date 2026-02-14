from __future__ import annotations

from fastapi.responses import StreamingResponse


def test_chat_route_returns_conversation_id(api_client, monkeypatch):
    def _answer_question(*_args, **_kwargs):
        return {
            "question": "q",
            "answer": "a",
            "conversation_id": "conv-abc",
            "citations": [],
        }

    monkeypatch.setattr("app.routes.chat.answer_question", _answer_question)
    response = api_client.post("/chat", json={"question": "hello", "top_k": 3})
    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] == "conv-abc"


def test_chat_stream_route_emits_done_with_conversation_id(api_client, monkeypatch):
    def _stream():
        yield b'data: {"token":"a"}\n\n'
        yield b'event: done\ndata: {"answer":"ok","conversation_id":"conv-stream","citations":[]}\n\n'

    def _answer_question(*_args, **_kwargs):
        return StreamingResponse(_stream(), media_type="text/event-stream")

    monkeypatch.setattr("app.routes.chat.answer_question", _answer_question)
    response = api_client.post("/chat/stream", json={"question": "hello", "top_k": 3})
    assert response.status_code == 200
    body = response.text
    assert "event: done" in body
    assert '"conversation_id":"conv-stream"' in body

