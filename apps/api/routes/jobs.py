from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from psycopg.errors import UniqueViolation

from apps.api.schemas import JobCreate, JobIndexResult, JobRead
from db.jobs import JobRepository
from services.job_indexing import JobNotFoundError, index_job


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobRead)
def create_job(job: JobCreate) -> dict:
    try:
        return JobRepository().create(job.model_dump())
    except UniqueViolation as exc:
        raise HTTPException(status_code=409, detail="Job URL already exists") from exc


@router.get("", response_model=list[JobRead])
def list_jobs(limit: int = Query(default=50, ge=1, le=200)) -> list[dict]:
    return JobRepository().list(limit=limit)


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: UUID) -> dict:
    job = JobRepository().get(str(job_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/index", response_model=JobIndexResult)
def index_job_route(job_id: UUID) -> dict:
    try:
        chunks_indexed = index_job(str(job_id))
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    return {"job_id": job_id, "chunks_indexed": chunks_indexed}
