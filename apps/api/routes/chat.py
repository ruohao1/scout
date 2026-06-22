from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from apps.api.schemas import ChatRequest, ChatResponse
from rag.types import JobSearchFilters
from services.job_workflow_graph import respond_to_chat_with_graph, stream_chat_with_graph


router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> dict:
    message = _strip_system_reminders(request.message)
    history = _strip_history_system_reminders([item.model_dump() for item in request.history])
    result = respond_to_chat_with_graph(
        message=message,
        history=history,
        target_profile_id=str(request.target_profile_id) if request.target_profile_id else None,
        profile_id=str(request.profile_id) if request.profile_id else None,
        filters=JobSearchFilters(**request.filters.model_dump()),
        limit=request.limit,
    )
    return _strip_system_reminders_recursive(asdict(result))


@router.post("/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(_chat_event_stream(request), media_type="text/event-stream")


def _chat_event_stream(request: ChatRequest):
    try:
        for event in stream_chat_with_graph(
            message=_strip_system_reminders(request.message),
            history=_strip_history_system_reminders([item.model_dump() for item in request.history]),
            target_profile_id=str(request.target_profile_id) if request.target_profile_id else None,
            profile_id=str(request.profile_id) if request.profile_id else None,
            filters=JobSearchFilters(**request.filters.model_dump()),
            limit=request.limit,
        ):
            yield f"data: {json.dumps(_strip_system_reminders_recursive(event), default=str)}\n\n"
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'message': _strip_system_reminders(str(exc))}, default=str)}\n\n"


def _strip_history_system_reminders(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stripped: list[dict[str, Any]] = []
    for item in history:
        content = item.get("content")
        if isinstance(content, str):
            stripped.append({**item, "content": _strip_system_reminders(content)})
        else:
            stripped.append(item)
    return stripped


def _strip_system_reminders_recursive(value: Any) -> Any:
    if isinstance(value, str):
        return _strip_system_reminders(value)
    if isinstance(value, list):
        return [_strip_system_reminders_recursive(item) for item in value]
    if isinstance(value, dict):
        return {key: _strip_system_reminders_recursive(item) for key, item in value.items()}
    return value


def _strip_system_reminders(text: str) -> str:
    return re.sub(r"<system-reminder>.*?</system-reminder>", " ", text, flags=re.IGNORECASE | re.DOTALL).strip()
