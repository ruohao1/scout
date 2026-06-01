from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from .types import JobSearchResult, RankedJob


def rank_search_results(
    *,
    profile: dict[str, Any],
    results: list[JobSearchResult],
    now: datetime | None = None,
) -> list[RankedJob]:
    now = now or datetime.now(UTC)
    grouped: dict[str, list[JobSearchResult]] = defaultdict(list)
    for result in results:
        grouped[result.job_id].append(result)

    ranked = [_rank_job(profile=profile, results=job_results, now=now) for job_results in grouped.values()]
    return sorted(ranked, key=lambda job: job.final_score, reverse=True)


def _rank_job(*, profile: dict[str, Any], results: list[JobSearchResult], now: datetime) -> RankedJob:
    evidence = sorted(results, key=lambda result: result.score, reverse=True)[:3]
    best = evidence[0]

    vector_score = _clamp01(max(result.score for result in results))
    matched_skills, missing_skills, skill_overlap_score = _skill_scores(profile, best)
    location_score = _location_score(profile, best)
    contract_type_score = _contract_type_score(profile, best)
    recency_score = _recency_score(best.created_at, now)
    final_score = (
        0.45 * vector_score
        + 0.25 * skill_overlap_score
        + 0.15 * location_score
        + 0.10 * contract_type_score
        + 0.05 * recency_score
    )

    return RankedJob(
        job_id=best.job_id,
        title=best.title,
        final_score=round(final_score, 6),
        vector_score=round(vector_score, 6),
        skill_overlap_score=round(skill_overlap_score, 6),
        location_score=round(location_score, 6),
        contract_type_score=round(contract_type_score, 6),
        recency_score=round(recency_score, 6),
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        evidence=evidence,
        company=best.company,
        location=best.location,
        contract_type=best.contract_type,
        url=best.url,
    )


def _skill_scores(profile: dict[str, Any], result: JobSearchResult) -> tuple[list[str], list[str], float]:
    profile_skills = {_normalize(value) for value in profile.get("skills", []) if _normalize(value)}
    job_skills = {_normalize(value) for value in result.skills if _normalize(value)}
    if not job_skills:
        return [], [], 0.0

    matched = sorted(profile_skills & job_skills)
    missing = sorted(job_skills - profile_skills)
    return matched, missing, len(matched) / len(job_skills)


def _location_score(profile: dict[str, Any], result: JobSearchResult) -> float:
    targets = [_normalize(value) for value in profile.get("target_locations", []) if _normalize(value)]
    if not targets:
        return 0.5
    location = _normalize(result.location or "")
    return 1.0 if any(target in location for target in targets) else 0.0


def _contract_type_score(profile: dict[str, Any], result: JobSearchResult) -> float:
    preferred = {_normalize(value) for value in profile.get("preferred_contract_types", []) if _normalize(value)}
    if not preferred:
        return 0.5
    return 1.0 if _normalize(result.contract_type or "") in preferred else 0.0


def _recency_score(created_at: datetime | None, now: datetime) -> float:
    if created_at is None:
        return 0.5
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    days_old = max(0, (now - created_at).days)
    return _clamp01(1.0 - days_old / 30)


def _normalize(value: object) -> str:
    return str(value).strip().lower()


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
