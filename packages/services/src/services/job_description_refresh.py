from __future__ import annotations

from typing import Any

from db.jobs import JobRepository

from .job_description_enrichment import (
    JobDescriptionRefreshError,
    JobDescriptionUnavailableError,
    enrich_weak_job_description,
    extract_job_description_from_html,
    has_weak_job_description,
)
from .job_indexing import index_job
from .job_providers import _infer_remote_policy, _infer_seniority
from .job_skills import enrich_job_skills


class JobDescriptionRefreshNotFoundError(JobDescriptionRefreshError):
    pass


def refresh_job_description(
    job_id: str,
    *,
    jobs: JobRepository | None = None,
    should_index: bool = True,
) -> dict[str, Any]:
    repository = jobs or JobRepository()
    job = repository.get(job_id)
    if job is None:
        raise JobDescriptionRefreshNotFoundError(f"Job not found: {job_id}")
    refreshed = refresh_job_description_from_job(job, jobs=repository, should_index=should_index)
    if refreshed is None:
        raise JobDescriptionUnavailableError("Could not extract a useful description from the original posting")
    return refreshed


def refresh_job_description_from_job(
    job: dict[str, Any],
    *,
    jobs: JobRepository | None = None,
    should_index: bool = True,
) -> dict[str, Any] | None:
    enriched_job = enrich_weak_job_description(
        job,
        infer_seniority=_infer_seniority,
        infer_remote_policy=_infer_remote_policy,
    )
    if enriched_job is job or enriched_job.get("description") == job.get("description"):
        return None

    enriched = enrich_job_skills(enriched_job)
    repository = jobs or JobRepository()
    updated = repository.update_description(
        str(job["id"]),
        description=str(enriched_job["description"]),
        skills=enriched.get("skills") or [],
        seniority=enriched.get("seniority"),
        remote_policy=enriched.get("remote_policy"),
        raw_payload=enriched_job.get("raw_payload") or {},
    )
    if updated is None:
        return None
    if should_index:
        index_job(str(job["id"]), jobs=repository)
        updated = repository.get(str(job["id"])) or updated
    return updated
