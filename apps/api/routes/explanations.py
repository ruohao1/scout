from __future__ import annotations

from fastapi import APIRouter, HTTPException

from apps.api.schemas import ExplainedRankedJobResult, ExplainRankedJobsRequest
from rag.types import ExplainedRankedJob, JobSearchFilters
from services.job_explanations import ExplanationParseError, explain_ranked_jobs
from services.job_ranking import ProfileNotFoundError


router = APIRouter(tags=["explanations"])


@router.post("/rank-jobs/explain", response_model=list[ExplainedRankedJobResult])
def explain_ranked_jobs_route(request: ExplainRankedJobsRequest) -> list[dict]:
    try:
        explained = explain_ranked_jobs(
            str(request.profile_id),
            filters=JobSearchFilters(**request.filters.model_dump()),
            limit=request.limit,
            model=request.model,
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Profile not found") from exc
    except ExplanationParseError as exc:
        raise HTTPException(status_code=502, detail="Model returned invalid explanation JSON") from exc
    return [_response_item(item) for item in explained]


def _response_item(item: ExplainedRankedJob) -> dict:
    ranked = item.ranked_job
    return {
        "job_id": ranked.job_id,
        "title": ranked.title,
        "final_score": ranked.final_score,
        "vector_score": ranked.vector_score,
        "skill_overlap_score": ranked.skill_overlap_score,
        "location_score": ranked.location_score,
        "contract_type_score": ranked.contract_type_score,
        "recency_score": ranked.recency_score,
        "text_skill_score": ranked.text_skill_score,
        "matched_skills": ranked.matched_skills,
        "matched_text_skills": ranked.matched_text_skills,
        "missing_skills": ranked.missing_skills,
        "why_match": item.why_match,
        "cv_suggestions": item.cv_suggestions,
        "evidence": ranked.evidence,
        "company": ranked.company,
        "location": ranked.location,
        "contract_type": ranked.contract_type,
        "url": ranked.url,
    }
