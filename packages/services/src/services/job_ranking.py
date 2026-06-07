from __future__ import annotations

from db.profiles import ProfileRepository
from rag.ranking import rank_search_results
from rag.types import JobSearchFilters, RankedJob

from .job_search import search_jobs


class ProfileNotFoundError(ValueError):
    pass


def rank_jobs_for_profile(
    profile_id: str,
    *,
    filters: JobSearchFilters | None = None,
    limit: int = 10,
    profiles: ProfileRepository | None = None,
) -> list[RankedJob]:
    profile_repository = profiles or ProfileRepository()
    profile = profile_repository.get_with_enrichment(profile_id)
    if profile is None:
        raise ProfileNotFoundError(f"Profile not found: {profile_id}")

    query = _profile_query(profile)
    results = search_jobs(query, filters=filters, limit=max(limit * 5, 20))
    return rank_search_results(profile=profile, results=results)[:limit]


def _profile_query(profile: dict) -> str:
    parts = [
        profile.get("cv_text") or "",
        " ".join(profile.get("target_roles") or []),
        " ".join(profile.get("skills") or []),
    ]
    for skill in profile.get("enriched_skills") or []:
        parts.extend([skill.get("name") or "", skill.get("category") or "", skill.get("proficiency") or ""])
    for experience in profile.get("experiences") or []:
        parts.extend(
            [
                experience.get("title") or "",
                experience.get("company") or "",
                experience.get("description") or "",
                " ".join(experience.get("skills") or []),
            ]
        )
    for project in profile.get("projects") or []:
        parts.extend(
            [
                project.get("name") or "",
                project.get("role") or "",
                project.get("description") or "",
                " ".join(project.get("skills") or []),
            ]
        )
    return " ".join(part for part in parts if part).strip()
