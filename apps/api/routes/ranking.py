from __future__ import annotations

from fastapi import APIRouter, HTTPException

from apps.api.schemas import RankedJobResult, RankJobsRequest
from rag.types import JobSearchFilters, RankedJob
from services.job_ranking import ProfileNotFoundError, rank_jobs_for_profile


router = APIRouter(tags=["ranking"])


@router.post("/rank-jobs", response_model=list[RankedJobResult])
def rank_jobs(request: RankJobsRequest) -> list[RankedJob]:
    try:
        return rank_jobs_for_profile(
            str(request.profile_id),
            filters=JobSearchFilters(**request.filters.model_dump()),
            limit=request.limit,
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Profile not found") from exc
