from __future__ import annotations

import json
from queue import Queue
from threading import Thread
from typing import Any
from dataclasses import asdict

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from apps.api.schemas import ChatRequest, ChatResponse
from rag.types import JobSearchFilters
from services.job_workflow_graph import respond_to_chat_with_graph


router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> dict:
    result = respond_to_chat_with_graph(
        message=request.message,
        history=[message.model_dump() for message in request.history],
        profile_id=str(request.profile_id) if request.profile_id else None,
        filters=JobSearchFilters(**request.filters.model_dump()),
        limit=request.limit,
    )
    return asdict(result)


@router.post("/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(_chat_event_stream(request), media_type="text/event-stream")


def _chat_event_stream(request: ChatRequest):
    events: Queue[dict[str, Any] | None] = Queue()

    def emit(event: dict[str, Any]) -> None:
        events.put(event)

    def run() -> None:
        try:
            result = respond_to_chat_with_graph(
                message=request.message,
                history=[message.model_dump() for message in request.history],
                profile_id=str(request.profile_id) if request.profile_id else None,
                filters=JobSearchFilters(**request.filters.model_dump()),
                limit=request.limit,
                event_callback=emit,
            )
            emit({"type": "done", "response": asdict(result)})
        except Exception as exc:
            emit({"type": "error", "message": str(exc)})
        finally:
            events.put(None)

    Thread(target=run, daemon=True).start()
    while True:
        event = events.get()
        if event is None:
            break
        yield f"data: {json.dumps(event, default=str)}\n\n"
