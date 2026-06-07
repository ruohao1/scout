from __future__ import annotations

import json
from typing import Protocol

from db.profiles import ProfileRepository
from providers.openai_auth import OpenAIAuthProvider
from providers.types import GenerateRequest, ProviderMessage
from rag.prompts import job_match_explanation_prompt
from rag.types import ExplainedRankedJob, JobSearchFilters

from .job_ranking import ProfileNotFoundError, rank_jobs_for_profile


class ExplanationParseError(ValueError):
    pass


class ExplanationProvider(Protocol):
    def generate(self, request: GenerateRequest):
        ...


def explain_ranked_jobs(
    profile_id: str,
    *,
    filters: JobSearchFilters | None = None,
    limit: int = 5,
    model: str = "gpt-5.5",
    provider: ExplanationProvider | None = None,
    profiles: ProfileRepository | None = None,
) -> list[ExplainedRankedJob]:
    profile_repository = profiles or ProfileRepository()
    profile = profile_repository.get_with_enrichment(profile_id)
    if profile is None:
        raise ProfileNotFoundError(f"Profile not found: {profile_id}")

    ranked_jobs = rank_jobs_for_profile(profile_id, filters=filters, limit=limit, profiles=profile_repository)
    explanation_provider = provider or OpenAIAuthProvider()

    explained: list[ExplainedRankedJob] = []
    for ranked_job in ranked_jobs:
        prompt = job_match_explanation_prompt(profile=profile, ranked_job=ranked_job)
        response = explanation_provider.generate(
            GenerateRequest(
                model=model,
                messages=[ProviderMessage(role="user", content=prompt)],
                instructions="Return strict JSON only. Do not include markdown fences or prose outside JSON.",
            )
        )
        why_match, cv_suggestions = _parse_explanation(response.text)
        explained.append(
            ExplainedRankedJob(
                ranked_job=ranked_job,
                why_match=why_match,
                cv_suggestions=cv_suggestions,
            )
        )
    return explained


def _parse_explanation(text: str) -> tuple[str, list[str]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExplanationParseError("Model returned invalid explanation JSON") from exc

    if not isinstance(data, dict) or not isinstance(data.get("why_match"), str):
        raise ExplanationParseError("Model explanation JSON must include why_match")

    suggestions = data.get("cv_suggestions", [])
    if not isinstance(suggestions, list):
        suggestions = []
    return data["why_match"], [str(item) for item in suggestions if isinstance(item, str)]
