from __future__ import annotations

import json
from dataclasses import asdict

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from apps.api.schemas import ChatRequest, ChatResponse
from rag.types import JobSearchFilters
from services.job_workflow_graph import respond_to_chat_with_graph, stream_chat_with_graph


router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> dict:
    result = respond_to_chat_with_graph(
        message=request.message,
        history=[message.model_dump() for message in request.history],
        target_profile_id=str(request.target_profile_id) if request.target_profile_id else None,
        profile_id=str(request.profile_id) if request.profile_id else None,
        filters=JobSearchFilters(**request.filters.model_dump()),
        limit=request.limit,
    )
    return asdict(result)


@router.post("/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(_chat_event_stream(request), media_type="text/event-stream")


def _chat_event_stream(request: ChatRequest):
    try:
        for event in stream_chat_with_graph(
            message=request.message,
            history=[message.model_dump() for message in request.history],
            target_profile_id=str(request.target_profile_id) if request.target_profile_id else None,
            profile_id=str(request.profile_id) if request.profile_id else None,
            filters=JobSearchFilters(**request.filters.model_dump()),
            limit=request.limit,
        ):
            yield f"data: {json.dumps(event, default=str)}\n\n"
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, default=str)}\n\n"
