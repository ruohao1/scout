from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

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
