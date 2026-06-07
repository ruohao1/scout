from __future__ import annotations

from db.profiles import ProfileRepository
from rag.ranking import rank_search_results
from rag.types import JobSearchFilters, RankedJob

from .job_search import search_jobs
from .target_profiles import get_target_profile_with_evidence


class ProfileNotFoundError(ValueError):
    pass


class TargetProfileNotFoundError(ValueError):
    pass


def rank_jobs_for_target_profile(
    target_profile_id: str,
    *,
    filters: JobSearchFilters | None = None,
    limit: int = 10,
    user_query: str | None = None,
) -> list[RankedJob]:
    target_profile = get_target_profile_with_evidence(target_profile_id)
    if target_profile is None:
        raise TargetProfileNotFoundError(f"Target profile not found: {target_profile_id}")

    query = _combined_target_profile_query(target_profile, user_query=user_query)
    results = search_jobs(query, filters=filters, limit=max(limit * 5, 20))
    ranking_profile = dict(target_profile)
    if filters and filters.seniority:
        ranking_profile["_requested_seniority"] = filters.seniority
    return rank_search_results(profile=ranking_profile, results=results)[:limit]


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


def _target_profile_query(target_profile: dict) -> str:
    parts = [
        target_profile.get("name") or "",
        target_profile.get("summary") or "",
        " ".join(target_profile.get("target_roles") or []),
        " ".join(target_profile.get("must_have_keywords") or []),
        " ".join(target_profile.get("nice_to_have_keywords") or []),
    ]
    for evidence in target_profile.get("evidence") or []:
        evidence_text = " ".join(
            part
            for part in [
                evidence.get("title") or "",
                evidence.get("description") or "",
                " ".join(evidence.get("skills") or []),
            ]
            if part
        )
        if not evidence_text:
            continue
        weight = _weight(evidence.get("weight"))
        repeat = 3 if weight >= 0.75 else 2 if weight >= 0.5 else 1
        parts.extend([evidence_text] * repeat)
    return " ".join(part for part in parts if part).strip()


def _combined_target_profile_query(target_profile: dict, *, user_query: str | None) -> str:
    parts = [_target_profile_query(target_profile)]
    if isinstance(user_query, str) and user_query.strip():
        parts.extend([user_query.strip()] * 3)
    return " ".join(part for part in parts if part).strip()


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


def _weight(value: object) -> float:
    if isinstance(value, int | float):
        return max(0.0, min(1.0, float(value)))
    return 1.0
