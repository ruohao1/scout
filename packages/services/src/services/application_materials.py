from __future__ import annotations

import json
from typing import Any, Protocol

from db.candidate import CandidateEvidenceChunkRepository, CandidateRepository
from db.jobs import JobRepository
from providers.openai_auth import OpenAIAuthProvider
from providers.types import GenerateRequest, ProviderMessage
from rag.embeddings import EmbeddingProvider, create_embedding_provider

from .job_description_refresh import refresh_job_description_from_job
from .target_profiles import get_target_profile_with_evidence


TAILORED_CV_MODEL = "gpt-5.5"
TAILORED_CV_TIMEOUT_SECONDS = 45


class CandidateEvidenceUnavailableError(ValueError):
    pass


class JobForApplicationNotFoundError(ValueError):
    pass


class TailoredCVGenerationError(ValueError):
    pass


class TailoredCVProvider(Protocol):
    def generate(self, request: GenerateRequest):
        ...


def draft_tailored_cv(
    job_id: str,
    *,
    target_profile_id: str | None = None,
    instruction: str | None = None,
    evidence_limit: int = 8,
    model: str = TAILORED_CV_MODEL,
    jobs: JobRepository | None = None,
    candidate: CandidateRepository | None = None,
    chunks: CandidateEvidenceChunkRepository | None = None,
    embeddings: EmbeddingProvider | None = None,
    provider: TailoredCVProvider | None = None,
) -> dict[str, Any]:
    job_repository = jobs or JobRepository()
    job = job_repository.get(job_id)
    if job is None:
        raise JobForApplicationNotFoundError(f"Job not found: {job_id}")
    job = refresh_job_description_from_job(job, jobs=job_repository) or job

    target_profile = get_target_profile_with_evidence(target_profile_id) if target_profile_id else None
    query = _retrieval_query(job, target_profile=target_profile, instruction=instruction)
    embedding_provider = embeddings or create_embedding_provider()
    chunk_repository = chunks or CandidateEvidenceChunkRepository()
    evidence_chunks = chunk_repository.search_chunks(embedding=embedding_provider.embed_texts([query])[0], limit=evidence_limit)
    if not evidence_chunks:
        raise CandidateEvidenceUnavailableError("No indexed candidate evidence was found. Add candidate evidence or reindex it before tailoring a CV.")

    candidate_profile = (candidate or CandidateRepository()).get()
    prompt = _tailored_cv_prompt(
        job=job,
        candidate=candidate_profile,
        target_profile=target_profile,
        evidence_chunks=evidence_chunks,
        instruction=instruction,
    )
    generation_provider = provider or OpenAIAuthProvider(timeout=TAILORED_CV_TIMEOUT_SECONDS)
    response = generation_provider.generate(
        GenerateRequest(
            model=model,
            messages=[ProviderMessage(role="user", content=prompt)],
            instructions="Return strict JSON only. Do not include markdown fences or prose outside JSON.",
        )
    )
    draft = _parse_tailored_cv(response.text)
    return {
        "job_id": job["id"],
        "target_profile_id": target_profile_id,
        "headline": draft["headline"],
        "summary": draft["summary"],
        "bullets": draft["bullets"],
        "evidence_used": _evidence_used(draft.get("evidence_used"), evidence_chunks),
        "gaps_or_cautions": draft["gaps_or_cautions"],
        "retrieved_evidence": [_chunk_read(item) for item in evidence_chunks],
    }


def _retrieval_query(job: dict[str, Any], *, target_profile: dict[str, Any] | None, instruction: str | None) -> str:
    parts = [
        job.get("title") or "",
        job.get("company") or "",
        job.get("location") or "",
        job.get("seniority") or "",
        " ".join(job.get("skills") or []),
        job.get("description") or "",
    ]
    if target_profile:
        parts.extend(
            [
                target_profile.get("name") or "",
                target_profile.get("summary") or "",
                " ".join(target_profile.get("target_roles") or []),
                " ".join(target_profile.get("must_have_keywords") or []),
                " ".join(target_profile.get("nice_to_have_keywords") or []),
            ]
        )
    if instruction:
        parts.append(instruction)
    return "\n".join(part for part in parts if part).strip()


def _tailored_cv_prompt(
    *,
    job: dict[str, Any],
    candidate: dict[str, Any] | None,
    target_profile: dict[str, Any] | None,
    evidence_chunks: list[dict[str, Any]],
    instruction: str | None,
) -> str:
    return f"""
You are Scout, a job application assistant. Draft tailored CV content for this one job using only the candidate evidence below.

Rules:
- Do not invent employers, degrees, dates, metrics, tools, or responsibilities.
- Prefer specific, job-relevant evidence over generic claims.
- Write concise UK-style CV bullets unless the user instruction says otherwise.
- Each bullet must include an evidence_ids array with one or more retrieved evidence IDs.
- If the candidate lacks evidence for an important job requirement, put it in gaps_or_cautions instead of pretending.
- Write as final CV copy, not as an explanation of matching or tailoring.
- Do not use phrases like "tailored for", "strong match", "good fit", "candidate", "the role", "the job", "this position", or "supporting evidence" in headline, summary, or bullets.
- Do not mention the target company unless the candidate actually worked with that company.
- Keep bullets factual and human: start with concrete work done, avoid marketing claims, and avoid repeating the same technology list in every bullet.

Return JSON with this shape:
{{
  "headline": "short tailored CV headline",
  "summary": "2-3 sentence profile summary tailored to the job",
  "bullets": [{{"text": "CV bullet", "evidence_ids": ["uuid"]}}],
  "evidence_used": [{{"evidence_id": "uuid", "reason": "why it supports the draft"}}],
  "gaps_or_cautions": ["gap or caution"]
}}

Candidate:
{json.dumps(_candidate_context(candidate), default=str)}

Target profile:
{json.dumps(_target_profile_context(target_profile), default=str)}

Job:
{json.dumps(_job_context(job), default=str)}

User instruction:
{instruction or ""}

Retrieved candidate evidence:
{json.dumps([_chunk_prompt_context(item) for item in evidence_chunks], default=str)}
""".strip()


def _parse_tailored_cv(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TailoredCVGenerationError("Model returned invalid tailored CV JSON") from exc

    if not isinstance(data, dict):
        raise TailoredCVGenerationError("Tailored CV response must be a JSON object")

    headline = data.get("headline")
    summary = data.get("summary")
    bullets = data.get("bullets")
    if not isinstance(headline, str) or not headline.strip():
        raise TailoredCVGenerationError("Tailored CV response must include headline")
    if not isinstance(summary, str) or not summary.strip():
        raise TailoredCVGenerationError("Tailored CV response must include summary")
    if not isinstance(bullets, list) or not bullets:
        raise TailoredCVGenerationError("Tailored CV response must include bullets")

    parsed_bullets = []
    for item in bullets[:8]:
        if isinstance(item, str):
            parsed_bullets.append({"text": item, "evidence_ids": []})
        elif isinstance(item, dict) and isinstance(item.get("text"), str):
            evidence_ids = item.get("evidence_ids") if isinstance(item.get("evidence_ids"), list) else []
            parsed_bullets.append({"text": item["text"], "evidence_ids": [str(value) for value in evidence_ids]})

    if not parsed_bullets:
        raise TailoredCVGenerationError("Tailored CV response did not include usable bullets")

    cautions = data.get("gaps_or_cautions") if isinstance(data.get("gaps_or_cautions"), list) else []
    return {
        "headline": headline.strip(),
        "summary": summary.strip(),
        "bullets": parsed_bullets,
        "evidence_used": data.get("evidence_used") if isinstance(data.get("evidence_used"), list) else [],
        "gaps_or_cautions": [str(item) for item in cautions if isinstance(item, str)],
    }


def _evidence_used(items: object, evidence_chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(item["evidence_id"]): item for item in evidence_chunks}
    used = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            evidence_id = str(item.get("evidence_id") or "")
            if evidence_id in by_id:
                used.append({**_evidence_read(by_id[evidence_id]), "reason": str(item.get("reason") or "")})
    if used:
        return used
    return [_evidence_read(item) for item in evidence_chunks[:4]]


def _candidate_context(candidate: dict[str, Any] | None) -> dict[str, Any]:
    if candidate is None:
        return {}
    return {"display_name": candidate.get("display_name"), "headline": candidate.get("headline"), "summary": candidate.get("summary")}


def _target_profile_context(target_profile: dict[str, Any] | None) -> dict[str, Any]:
    if target_profile is None:
        return {}
    return {
        "name": target_profile.get("name"),
        "summary": target_profile.get("summary"),
        "target_roles": target_profile.get("target_roles") or [],
        "seniority": target_profile.get("seniority"),
        "must_have_keywords": target_profile.get("must_have_keywords") or [],
        "nice_to_have_keywords": target_profile.get("nice_to_have_keywords") or [],
        "instructions": target_profile.get("instructions"),
    }


def _job_context(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": job.get("title"),
        "company": job.get("company"),
        "location": job.get("location"),
        "contract_type": job.get("contract_type"),
        "seniority": job.get("seniority"),
        "skills": job.get("skills") or [],
        "description": job.get("description"),
    }


def _chunk_prompt_context(item: dict[str, Any]) -> dict[str, Any]:
    return {**_chunk_read(item), "content": item.get("content")}


def _chunk_read(item: dict[str, Any]) -> dict[str, Any]:
    return {**_evidence_read(item), "chunk_id": item.get("id"), "content": item.get("content"), "score": float(item.get("score") or 0.0)}


def _evidence_read(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": item.get("evidence_id"),
        "type": item.get("evidence_type"),
        "title": item.get("evidence_title"),
        "organization": item.get("evidence_organization"),
        "location": item.get("evidence_location"),
        "start_date": item.get("evidence_start_date"),
        "end_date": item.get("evidence_end_date"),
        "is_current": item.get("evidence_is_current"),
        "description": item.get("evidence_description"),
        "skills": item.get("evidence_skills") or [],
        "url": item.get("evidence_url"),
        "confidence": item.get("evidence_confidence"),
    }
