from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResolvedChatJob:
    job_id: str
    title: str | None = None
    company: str | None = None


@dataclass(frozen=True)
class JobReferenceResolution:
    job: ResolvedChatJob | None
    reason: str
    needs_clarification: bool = False


def resolve_chat_job_reference(*, message: str, history: list[dict[str, Any]], selected_job_id: str | None = None) -> JobReferenceResolution:
    recent_jobs = _recent_jobs(history)
    normalized = _normalized(message)
    if selected_job_id and (_uses_selected_reference(normalized) or not _has_explicit_reference(normalized)):
        return JobReferenceResolution(job=_selected_job(selected_job_id, recent_jobs), reason="Used the currently selected chat job.")

    ordinal = _ordinal_reference(normalized)
    if ordinal is not None:
        if 0 <= ordinal < len(recent_jobs):
            return JobReferenceResolution(job=_job_from_result(recent_jobs[ordinal]), reason=f"Resolved job {ordinal + 1} from recent chat results.")
        return JobReferenceResolution(job=None, reason=f"I could not find job {ordinal + 1} in the recent chat results.", needs_clarification=True)

    matches = _text_matches(normalized, recent_jobs)
    if len(matches) == 1:
        return JobReferenceResolution(job=_job_from_result(matches[0]), reason="Resolved the job from a title or company mention in recent chat results.")
    if len(matches) > 1:
        return JobReferenceResolution(job=None, reason="I found multiple recent jobs matching that reference.", needs_clarification=True)

    if selected_job_id:
        return JobReferenceResolution(job=_selected_job(selected_job_id, recent_jobs), reason="Used the currently selected chat job.")
    return JobReferenceResolution(job=None, reason="I could not tell which job to use for the CV.", needs_clarification=True)


def _recent_jobs(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for item in reversed(history[-12:]):
        jobs = item.get("ranked_jobs") or item.get("rankedJobs") or item.get("jobs") or []
        if isinstance(jobs, list) and jobs:
            return [job for job in jobs if isinstance(job, dict) and (job.get("id") or job.get("job_id"))]
    return []


def _selected_job(selected_job_id: str, recent_jobs: list[dict[str, Any]]) -> ResolvedChatJob:
    for item in recent_jobs:
        if str(item.get("id") or item.get("job_id")) == selected_job_id:
            return _job_from_result(item)
    return ResolvedChatJob(job_id=selected_job_id)


def _job_from_result(item: dict[str, Any]) -> ResolvedChatJob:
    return ResolvedChatJob(job_id=str(item.get("id") or item.get("job_id")), title=_string(item.get("title")), company=_string(item.get("company")))


def _uses_selected_reference(normalized: str) -> bool:
    return any(phrase in normalized for phrase in ("this", "this one", "selected job", "open job", "current job"))


def _has_explicit_reference(normalized: str) -> bool:
    return _ordinal_reference(normalized) is not None or bool(re.search(r"\b(the\s+)?[a-z0-9][a-z0-9&.,+-]*(\s+[a-z0-9][a-z0-9&.,+-]*){0,4}\s+(role|job)\b", normalized))


def _ordinal_reference(normalized: str) -> int | None:
    match = re.search(r"\b(?:job|role|option|result)\s*(\d{1,2})\b", normalized)
    if match:
        return int(match.group(1)) - 1
    words = {
        "first": 0,
        "1st": 0,
        "second": 1,
        "2nd": 1,
        "third": 2,
        "3rd": 2,
        "fourth": 3,
        "4th": 3,
        "fifth": 4,
        "5th": 4,
    }
    for word, index in words.items():
        if re.search(rf"\b{re.escape(word)}\b", normalized):
            return index
    return None


def _text_matches(normalized: str, recent_jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches = []
    for item in recent_jobs:
        title = _normalized(_string(item.get("title")) or "")
        company = _normalized(_string(item.get("company")) or "")
        if (company and company in normalized) or (title and title in normalized):
            matches.append(item)
    return matches


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9&.,+\s-]", " ", value.lower())).strip()


def _string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
