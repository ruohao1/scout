from __future__ import annotations

from fastapi import APIRouter, HTTPException

from apps.api.schemas import RankedJobResult, RankJobsRequest
from rag.types import JobSearchFilters, RankedJob
from services.job_ranking import TargetProfileNotFoundError, rank_jobs_for_target_profile


router = APIRouter(tags=["ranking"])


@router.post("/rank-jobs", response_model=list[RankedJobResult])
def rank_jobs(request: RankJobsRequest) -> list[RankedJob]:
    target_profile_id = request.target_profile_id or request.profile_id
    if target_profile_id is None:
        raise HTTPException(status_code=422, detail="target_profile_id is required")
    try:
        return rank_jobs_for_target_profile(
            str(target_profile_id),
            filters=JobSearchFilters(**request.filters.model_dump()),
            limit=request.limit,
        )
    except TargetProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Target profile not found") from exc
