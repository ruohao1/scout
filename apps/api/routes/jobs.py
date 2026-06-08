from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from psycopg.errors import UniqueViolation

from apps.api.schemas import JobCreate, JobDescriptionRefreshRead, JobIndexResult, JobRead, TailoredCVRead, TailoredCVRequest
from db.jobs import JobRepository
from services.application_materials import (
    CandidateEvidenceUnavailableError,
    JobForApplicationNotFoundError,
    TailoredCVGenerationError,
    draft_tailored_cv,
)
from services.job_description_refresh import (
    JobDescriptionRefreshNotFoundError,
    JobDescriptionUnavailableError,
    has_weak_job_description,
    refresh_job_description,
)
from services.job_indexing import JobNotFoundError, index_job
from services.job_skills import enrich_job_skills


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobRead)
def create_job(job: JobCreate, index: bool = Query(default=False)) -> dict:
    repository = JobRepository()
    try:
        created = repository.create(enrich_job_skills(job.model_dump()))
    except UniqueViolation as exc:
        raise HTTPException(status_code=409, detail="Job URL already exists") from exc
    if index:
        try:
            index_job(str(created["id"]), jobs=repository)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
    return repository.get(str(created["id"])) or created


@router.get("", response_model=list[JobRead])
def list_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    source: str | None = Query(default=None),
    indexed: bool | None = Query(default=None),
) -> list[dict]:
    return JobRepository().list(limit=limit, source=source, indexed=indexed)


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: UUID) -> dict:
    job = JobRepository().get(str(job_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/tailored-cv", response_model=TailoredCVRead)
def tailor_cv_for_job(job_id: UUID, request: TailoredCVRequest) -> dict:
    try:
        return draft_tailored_cv(
            str(job_id),
            target_profile_id=str(request.target_profile_id) if request.target_profile_id else None,
            instruction=request.instruction,
            evidence_limit=request.evidence_limit,
        )
    except JobForApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    except CandidateEvidenceUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TailoredCVGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{job_id}/refresh-description", response_model=JobDescriptionRefreshRead)
def refresh_job_description_route(job_id: UUID) -> dict:
    repository = JobRepository()
    existing = repository.get(str(job_id))
    if existing is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if not has_weak_job_description(existing):
        return {"job": existing, "refreshed": False, "description_length": len(existing.get("description") or "")}
    try:
        refreshed = refresh_job_description(str(job_id), jobs=repository)
    except JobDescriptionRefreshNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    except JobDescriptionUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"job": refreshed, "refreshed": True, "description_length": len(refreshed.get("description") or "")}


@router.post("/{job_id}/index", response_model=JobIndexResult)
def index_job_route(job_id: UUID) -> dict:
    try:
        chunks_indexed = index_job(str(job_id))
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    return {"job_id": job_id, "chunks_indexed": chunks_indexed}
