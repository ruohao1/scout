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
    selected_evidence_score, background_evidence_score, matched_evidence = _evidence_scores(profile, best)
    keyword_score = _keyword_score(profile, best)
    penalty_score = _penalty_score(profile, best)
    final_score = _clamp01(
        0.35 * vector_score
        + 0.20 * skill_overlap_score
        + 0.10 * location_score
        + 0.05 * contract_type_score
        + 0.05 * recency_score
        + 0.15 * selected_evidence_score
        + 0.03 * background_evidence_score
        + 0.07 * keyword_score
        - 0.15 * penalty_score
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
        selected_evidence_score=round(selected_evidence_score, 6),
        background_evidence_score=round(background_evidence_score, 6),
        keyword_score=round(keyword_score, 6),
        penalty_score=round(penalty_score, 6),
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        matched_evidence=matched_evidence,
        evidence=evidence,
        company=best.company,
        location=best.location,
        contract_type=best.contract_type,
        url=best.url,
    )


def _skill_scores(profile: dict[str, Any], result: JobSearchResult) -> tuple[list[str], list[str], float]:
    profile_skills = {_normalize(value) for value in _profile_skill_values(profile) if _normalize(value)}
    job_skills = {_normalize(value) for value in result.skills if _normalize(value)}
    if not job_skills:
        return [], [], 0.0

    matched = sorted(profile_skills & job_skills)
    missing = sorted(job_skills - profile_skills)
    return matched, missing, len(matched) / len(job_skills)


def _profile_skill_values(profile: dict[str, Any]) -> list[str]:
    values = list(profile.get("skills") or [])
    values.extend(profile.get("must_have_keywords") or [])
    values.extend(profile.get("nice_to_have_keywords") or [])
    for evidence in profile.get("evidence") or []:
        values.extend(evidence.get("skills") or [])
    return values


def _evidence_scores(profile: dict[str, Any], result: JobSearchResult) -> tuple[float, float, list[dict[str, Any]]]:
    selected_scores: list[float] = []
    background_scores: list[float] = []
    matched_evidence: list[dict[str, Any]] = []
    for evidence in profile.get("evidence") or []:
        score, matched_skills = _single_evidence_score(evidence, result)
        weight = _weight(evidence.get("weight"))
        if weight >= 0.5:
            selected_scores.append(score * weight)
        else:
            background_scores.append(score * max(weight, 0.25))
        if score > 0:
            matched_evidence.append(
                {
                    "evidence_id": str(evidence.get("evidence_id") or ""),
                    "title": evidence.get("title"),
                    "weight": weight,
                    "matched_skills": matched_skills,
                    "score": round(score, 6),
                }
            )
    return _average(selected_scores), _average(background_scores), matched_evidence[:5]


def _single_evidence_score(evidence: dict[str, Any], result: JobSearchResult) -> tuple[float, list[str]]:
    job_text = _job_text(result)
    evidence_terms = [_normalize(evidence.get("title") or ""), _normalize(evidence.get("description") or "")]
    text_score = 1.0 if any(term and term in job_text for term in evidence_terms) else 0.0
    evidence_skills = {_normalize(value) for value in evidence.get("skills", []) if _normalize(value)}
    job_skills = {_normalize(value) for value in result.skills if _normalize(value)}
    matched_skills = sorted(evidence_skills & job_skills)
    skill_score = len(matched_skills) / len(evidence_skills) if evidence_skills else 0.0
    return max(text_score, skill_score), matched_skills


def _keyword_score(profile: dict[str, Any], result: JobSearchResult) -> float:
    keywords = [*_list(profile.get("must_have_keywords")), *_list(profile.get("nice_to_have_keywords"))]
    if not keywords:
        return 0.0
    text = _job_text(result)
    matched = sum(1 for keyword in keywords if _normalize(keyword) in text)
    return _clamp01(matched / len(keywords))


def _penalty_score(profile: dict[str, Any], result: JobSearchResult) -> float:
    avoid_keywords = _list(profile.get("avoid_keywords"))
    if not avoid_keywords:
        return 0.0
    text = _job_text(result)
    matched = sum(1 for keyword in avoid_keywords if _normalize(keyword) in text)
    return _clamp01(matched / len(avoid_keywords))


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


def _job_text(result: JobSearchResult) -> str:
    return _normalize(" ".join([result.title, result.content, " ".join(result.skills)]))


def _list(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str) and item.strip()] if isinstance(value, list) else []


def _weight(value: object) -> float:
    if isinstance(value, int | float):
        return _clamp01(float(value))
    return 1.0


def _average(values: list[float]) -> float:
    return _clamp01(sum(values) / len(values)) if values else 0.0


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
