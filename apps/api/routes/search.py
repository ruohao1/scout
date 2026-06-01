from __future__ import annotations

from fastapi import APIRouter, HTTPException

from apps.api.schemas import SearchRequest, SearchResult
from rag.types import JobSearchFilters, JobSearchResult
from services.job_search import EmptySearchQueryError, search_jobs


router = APIRouter(tags=["search"])


@router.post("/search", response_model=list[SearchResult])
def search(request: SearchRequest) -> list[JobSearchResult]:
    try:
        return search_jobs(
            request.query,
            filters=JobSearchFilters(**request.filters.model_dump()),
            limit=request.limit,
        )
    except EmptySearchQueryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
