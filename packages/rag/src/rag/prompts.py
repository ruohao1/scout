from __future__ import annotations

import json
from typing import Any

from .types import RankedJob


def job_match_explanation_prompt(*, profile: dict[str, Any], ranked_job: RankedJob) -> str:
    payload = {
        "profile": {
            "name": profile.get("name") or "not specified",
            "cv_text": profile.get("cv_text") or "not specified",
            "target_roles": profile.get("target_roles") or [],
            "target_locations": profile.get("target_locations") or [],
            "skills": profile.get("skills") or [],
            "seniority": profile.get("seniority") or "not specified",
            "preferred_contract_types": profile.get("preferred_contract_types") or [],
            "remote_preference": profile.get("remote_preference") or "not specified",
        },
        "job": {
            "job_id": ranked_job.job_id,
            "title": ranked_job.title,
            "company": ranked_job.company or "not specified",
            "location": ranked_job.location or "not specified",
            "contract_type": ranked_job.contract_type or "not specified",
            "url": ranked_job.url or "not specified",
            "final_score": ranked_job.final_score,
            "score_components": {
                "vector_score": ranked_job.vector_score,
                "skill_overlap_score": ranked_job.skill_overlap_score,
                "text_skill_score": ranked_job.text_skill_score,
                "location_score": ranked_job.location_score,
                "contract_type_score": ranked_job.contract_type_score,
                "recency_score": ranked_job.recency_score,
            },
            "matched_skills": ranked_job.matched_skills,
            "matched_text_skills": ranked_job.matched_text_skills,
            "missing_skills": ranked_job.missing_skills,
            "evidence": [
                {
                    "section": item.section or "not specified",
                    "content": item.content,
                    "score": item.score,
                }
                for item in ranked_job.evidence
            ],
        },
    }
    return (
        "You are a job-matching assistant.\n"
        "Use only the provided job posting evidence.\n"
        "Do not invent salary, location, requirements, company facts, or skills.\n"
        "If a detail is missing, say \"not specified\".\n"
        "Explain the deterministic ranking; do not change or dispute the scores.\n"
        "Return strict JSON only, with this shape:\n"
        '{"why_match":"...","cv_suggestions":["..."]}\n\n'
        f"Data:\n{json.dumps(payload, indent=2, sort_keys=True)}"
    )
