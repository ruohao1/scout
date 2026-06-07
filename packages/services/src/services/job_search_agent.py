from __future__ import annotations

from dataclasses import asdict
import re
from typing import Any, Callable

from db.provider_import_runs import ProviderImportRunRepository
from langgraph.config import get_stream_writer
from rag.types import JobSearchFilters

from .chat import ChatResult, classify_chat_intent, missing_target_profile_message, target_profile_not_found_message, vague_search_message
from .job_corpus import get_job_corpus_status
from .job_providers import JobImportResult, JobSpyJobProviderAdapter, JobSpyJobProviderClient, import_jobs
from .job_ranking import TargetProfileNotFoundError, rank_jobs_for_target_profile
from .job_search import EmptySearchQueryError, search_jobs
from .target_profiles import get_target_profile_with_evidence


JobSpyImporter = Callable[..., JobImportResult]


def respond_to_job_search_agent(
    *,
    message: str,
    history: list[dict[str, Any]] | None = None,
    target_profile_id: str | None = None,
    profile_id: str | None = None,
    filters: JobSearchFilters | None = None,
    limit: int = 5,
    jobspy_importer: JobSpyImporter | None = None,
    route_query: str | None = None,
    route_intent: str | None = None,
    route_wants_live: bool | None = None,
) -> ChatResult:
    text = message.strip()
    if not text:
        return ChatResult(message=vague_search_message(), tool="job_search_agent", warnings=["Message must not be empty."])

    search_text = route_query.strip() if isinstance(route_query, str) and route_query.strip() else _effective_search_text(text, history or [])
    active_limit = _requested_limit(text, fallback=limit)
    active_filters = _merge_filters(search_text, filters or JobSearchFilters())
    selected_target_profile_id = target_profile_id or profile_id
    intent = classify_chat_intent(search_text)
    if route_intent and "rank" in route_intent:
        intent = "rank"
    elif route_intent and "search" in route_intent:
        intent = "search"
    if _looks_like_profile_match(search_text):
        intent = "rank"
    if intent == "chat" and _looks_like_job_search(search_text):
        intent = "search"
    wants_ranking = intent == "rank"
    wants_live = route_wants_live if route_wants_live is not None else _wants_live_jobs(text) or _wants_live_jobs(search_text)

    if intent == "vague_search":
        return ChatResult(message=vague_search_message(), tool="job_search_agent", warnings=["Search request needs role, skill, location, or target profile detail."])
    if wants_ranking and not selected_target_profile_id:
        return ChatResult(message=missing_target_profile_message(), tool="job_search_agent", warnings=["target_profile_id is required for matching."])

    _emit({"type": "step_started", "id": "job_search_agent", "title": "Run job-search specialist"})
    local = _run_local_search(
        text=search_text,
        wants_ranking=wants_ranking,
        target_profile_id=selected_target_profile_id,
        filters=active_filters,
        limit=active_limit,
    )
    local_count = len(local.get("ranked_jobs") or local.get("jobs") or [])
    if _target_profile_missing(local):
        _emit({"type": "step_completed", "id": "job_search_agent", "summary": "Target profile not found"})
        return ChatResult(message=target_profile_not_found_message(), tool="job_search_agent", warnings=local.get("warnings", []))
    should_fetch_live = wants_live or (intent in {"search", "rank"} and not _has_enough_results(local_count, active_limit))

    if not should_fetch_live:
        _emit({"type": "step_completed", "id": "job_search_agent", "summary": f"Found {local_count} local results"})
        return _chat_result_from_local(local, fetched_live=False)

    live_result = _fetch_live_jobs(
        text=search_text,
        target_profile_id=selected_target_profile_id,
        filters=active_filters,
        limit=active_limit,
        importer=jobspy_importer,
    )
    warnings = [*local.get("warnings", []), *live_result.get("warnings", [])]
    if live_result.get("ok"):
        refreshed = _run_local_search(
            text=search_text,
            wants_ranking=wants_ranking,
            target_profile_id=selected_target_profile_id,
            filters=active_filters,
            limit=active_limit,
        )
        warnings.extend(refreshed.get("warnings", []))
        fetched = int(live_result.get("created") or 0)
        indexed = int(live_result.get("indexed") or 0)
        count = len(refreshed.get("ranked_jobs") or refreshed.get("jobs") or [])
        _emit({"type": "step_completed", "id": "job_search_agent", "summary": f"Fetched {fetched} live jobs and returned {count} results"})
        return _chat_result_from_local(refreshed, fetched_live=True, created=fetched, indexed=indexed, warnings=warnings)

    if local_count:
        warnings.append("Live JobSpy search failed; showing indexed local results instead.")
        _emit({"type": "step_completed", "id": "job_search_agent", "summary": "Live fetch failed; returned local results"})
        return _chat_result_from_local(local, fetched_live=False, warnings=warnings)

    _emit({"type": "step_completed", "id": "job_search_agent", "summary": "No local or live results"})
    return ChatResult(
        message="I could not find enough relevant jobs locally, and the live JobSpy search failed.",
        tool="job_search_agent",
        warnings=warnings or ["No jobs found."],
    )


def is_job_search_agent_request(message: str, history: list[dict[str, Any]] | None = None) -> bool:
    normalized = _normalized_text(message)
    if classify_chat_intent(message) in {"search", "rank", "vague_search"}:
        return True
    if _looks_like_job_search(message):
        return True
    if _is_job_followup(message) and _last_job_query(history or [], current_message=message):
        return True
    return _wants_live_jobs(message) and any(word in normalized.split() for word in ("job", "jobs", "role", "roles", "offer", "offers"))


def _looks_like_job_search(text: str) -> bool:
    words = set(_normalized_text(text).split())
    has_search_action = bool(words & {"find", "get", "list", "search", "show"})
    has_role_terms = bool(words & {"backend", "developer", "engineer", "frontend", "manager", "product", "python", "software"})
    return has_search_action and has_role_terms


def _looks_like_profile_match(text: str) -> bool:
    normalized = _normalized_text(text)
    return any(
        phrase in normalized
        for phrase in (
            "match my profile",
            "matches my profile",
            "matching my profile",
            "match the profile",
            "matches the profile",
            "matching the profile",
            "jobs for my profile",
            "roles for my profile",
            "offers for my profile",
        )
    )


def _effective_search_text(text: str, history: list[dict[str, Any]]) -> str:
    if not _is_job_followup(text):
        return text
    previous = _last_job_query(history, current_message=text)
    if previous is None:
        return text
    if _wants_live_jobs(text):
        return f"{previous} {text}"
    return f"{previous} {text}"


def _requested_limit(text: str, *, fallback: int) -> int:
    match = re.search(
        r"\b(?:find|get|show|list|top|limit|return|give(?:\s+me)?)\s+(?:me\s+)?(?:the\s+)?(?:top\s+)?(\d{1,2})\b",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return fallback
    return max(1, min(int(match.group(1)), 50))


def _is_job_followup(text: str) -> bool:
    normalized = _normalized_text(text)
    if normalized in {"more", "more jobs", "show more", "fetch fresh offers", "fresh offers", "fetch live offers", "live offers"}:
        return True
    if _wants_live_jobs(text) and any(word in normalized.split() for word in ("offer", "offers", "job", "jobs", "role", "roles")):
        return True
    return bool(re.search(r"\b(find|get|show|list)\s+(me\s+)?\d{1,2}\b", normalized))


def _last_job_query(history: list[dict[str, Any]], *, current_message: str) -> str | None:
    skipped_current = False
    current = current_message.strip()
    for item in reversed(history[-10:]):
        if item.get("role") != "user":
            continue
        content = item.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        if content.strip() == current and not skipped_current:
            skipped_current = True
            continue
        if classify_chat_intent(content) in {"search", "rank"}:
            return content.strip()
        normalized = _normalized_text(content)
        words = set(normalized.split())
        has_job_terms = bool(words & {"backend", "developer", "engineer", "frontend", "python", "software"})
        has_search_action = bool(words & {"find", "get", "list", "search", "show"})
        has_job_noun = bool(words & {"job", "jobs", "offer", "offers", "role", "roles"})
        if has_job_terms and (has_search_action or has_job_noun):
            return content.strip()
    return None


def _run_local_search(
    *,
    text: str,
    wants_ranking: bool,
    target_profile_id: str | None,
    filters: JobSearchFilters,
    limit: int,
) -> dict[str, Any]:
    _emit({"type": "step_started", "id": "search_local_jobs", "title": "Search indexed jobs"})
    try:
        status = asdict(get_job_corpus_status())
    except Exception as exc:
        return {"ok": False, "tool": "job_search_agent", "jobs": [], "ranked_jobs": [], "warnings": [f"Corpus check failed: {exc}"]}

    if status.get("indexed_jobs", 0) <= 0:
        _emit({"type": "step_completed", "id": "search_local_jobs", "summary": "No indexed jobs available"})
        return {"ok": True, "tool": "job_search_agent", "jobs": [], "ranked_jobs": [], "warnings": ["No indexed jobs found in the local corpus."]}

    try:
        if wants_ranking:
            if not target_profile_id:
                return {"ok": False, "tool": "job_search_agent", "jobs": [], "ranked_jobs": [], "warnings": ["target_profile_id is required for matching."]}
            _emit(
                {
                    "type": "tool_started",
                    "id": "rank_jobs_for_profile",
                    "tool": "rank_jobs_for_profile",
                    "args": {"target_profile_id": target_profile_id, "filters": asdict(filters), "limit": limit},
                }
            )
            ranked = rank_jobs_for_target_profile(target_profile_id, filters=filters, limit=limit)
            ranked_jobs = _relevant_ranked_jobs([asdict(job) for job in ranked], limit=limit)
            _emit({"type": "tool_completed", "id": "rank_jobs_for_profile", "summary": f"Ranked {len(ranked_jobs)} jobs"})
            _emit({"type": "step_completed", "id": "search_local_jobs", "summary": f"Ranked {len(ranked)} indexed jobs"})
            return {"ok": True, "tool": "rank_jobs_for_profile", "jobs": [], "ranked_jobs": ranked_jobs, "warnings": []}
        query = _role_search_query(text) or _search_query(text)
        _emit(
            {
                "type": "tool_started",
                "id": "search_jobs",
                "tool": "search_jobs",
                "args": {"query": query, "filters": asdict(filters), "limit": max(limit * 5, 20)},
            }
        )
        jobs = search_jobs(query, filters=filters, limit=max(limit * 5, 20))
        unique_jobs = _relevant_search_jobs([asdict(job) for job in jobs], text=text, limit=limit)
        _emit({"type": "tool_completed", "id": "search_jobs", "summary": f"Found {len(unique_jobs)} unique relevant jobs"})
        _emit({"type": "step_completed", "id": "search_local_jobs", "summary": f"Found {len(jobs)} indexed jobs"})
        return {"ok": True, "tool": "search_jobs", "jobs": unique_jobs, "ranked_jobs": [], "warnings": []}
    except TargetProfileNotFoundError:
        _emit({"type": "tool_failed", "id": "rank_jobs_for_profile", "summary": "Target profile not found"})
        return {"ok": False, "tool": "job_search_agent", "jobs": [], "ranked_jobs": [], "warnings": ["Target profile not found."]}
    except EmptySearchQueryError:
        _emit({"type": "tool_failed", "id": "search_jobs", "summary": "Search query must not be empty"})
        return {"ok": False, "tool": "job_search_agent", "jobs": [], "ranked_jobs": [], "warnings": ["Search query must not be empty."]}
    except Exception as exc:
        _emit({"type": "tool_failed", "id": "search_local_jobs", "summary": str(exc)})
        return {"ok": False, "tool": "job_search_agent", "jobs": [], "ranked_jobs": [], "warnings": [f"Local job search failed: {exc}"]}


def _fetch_live_jobs(
    *,
    text: str,
    target_profile_id: str | None,
    filters: JobSearchFilters,
    limit: int,
    importer: JobSpyImporter | None,
) -> dict[str, Any]:
    try:
        search_term = _jobspy_search_term(text, target_profile_id=target_profile_id)
    except TargetProfileNotFoundError:
        return {"ok": False, "warnings": ["Target profile not found."]}
    if not search_term:
        return {"ok": False, "warnings": ["Live JobSpy search needs a role, skill, or target profile search term."]}

    count = max(10, min(25, limit * 3))
    params = {
        "search_term": search_term,
        "location": filters.location,
        "sites": ["indeed"],
        "count": count,
        "hours_old": None,
        "is_remote": filters.remote_policy == "remote" if filters.remote_policy else None,
        "job_type": _jobspy_job_type(filters.contract_type),
        "country_indeed": "UK",
        "limit": limit,
    }
    _emit({"type": "tool_started", "id": "fetch_jobspy_jobs", "tool": "fetch_jobspy_jobs", "args": {key: value for key, value in params.items() if value is not None}})
    runs = ProviderImportRunRepository()
    try:
        result = (importer or import_jobs)(
            client=JobSpyJobProviderClient(
                site_name=params["sites"],
                search_term=search_term,
                location=filters.location,
                job_type=params["job_type"],
                is_remote=params["is_remote"],
                hours_old=params["hours_old"],
                country_indeed=params["country_indeed"],
            ),
            adapter=JobSpyJobProviderAdapter(),
            count=count,
            should_index=True,
        )
    except Exception as exc:
        _record_jobspy_run(runs, params=params, created=0, skipped=0, indexed=0, status="failed", error=str(exc))
        _emit({"type": "tool_failed", "id": "fetch_jobspy_jobs", "summary": str(exc)})
        return {"ok": False, "warnings": [f"JobSpy live search failed: {exc}"]}

    _record_jobspy_run(runs, params=params, created=len(result.created), skipped=result.skipped, indexed=result.indexed, status="completed", error=None)
    _emit({"type": "tool_completed", "id": "fetch_jobspy_jobs", "summary": f"Imported {len(result.created)} jobs and indexed {result.indexed}"})
    return {"ok": True, "created": len(result.created), "skipped": result.skipped, "indexed": result.indexed, "warnings": []}


def _chat_result_from_local(
    local: dict[str, Any],
    *,
    fetched_live: bool,
    created: int = 0,
    indexed: int = 0,
    warnings: list[str] | None = None,
) -> ChatResult:
    jobs = local.get("jobs") or []
    ranked_jobs = local.get("ranked_jobs") or []
    result_warnings = warnings if warnings is not None else local.get("warnings", [])
    count = len(ranked_jobs or jobs)
    if ranked_jobs:
        message = f"Ranked **{count} {_plural(count, 'job')}** against your selected target profile."
    elif jobs:
        message = f"Found **{count} matching {_plural(count, 'job')}**."
    else:
        message = "I did not find enough relevant jobs."

    if fetched_live:
        if created:
            message += f" I also fetched **{created} live {_plural(created, 'job')}** with JobSpy and indexed **{indexed}** before refreshing results."
        else:
            message += " I also checked JobSpy for live offers, but it did not return new relevant jobs to index."
    elif result_warnings and not count:
        message += " I checked the local corpus first, but it did not have enough relevant indexed jobs."

    return ChatResult(message=message, tool=str(local.get("tool") or "job_search_agent"), jobs=jobs, ranked_jobs=ranked_jobs, warnings=result_warnings)


def _plural(count: int, singular: str) -> str:
    return singular if count == 1 else f"{singular}s"


def _has_enough_results(count: int, limit: int) -> bool:
    return count >= min(max(limit, 1), 3)


def _relevant_search_jobs(jobs: list[dict[str, Any]], *, text: str, limit: int) -> list[dict[str, Any]]:
    terms = _relevance_terms(text)
    unique = _unique_by_job_id(jobs)
    if not terms:
        return unique[:limit]
    filtered = [job for job in unique if _job_matches_terms(job, terms)]
    return filtered[:limit]


def _relevant_ranked_jobs(jobs: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    return _unique_by_job_id(jobs)[:limit]


def _unique_by_job_id(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for job in jobs:
        job_id = str(job.get("job_id") or job.get("id") or "")
        if not job_id:
            continue
        if job_id not in best_by_id:
            best_by_id[job_id] = job
            order.append(job_id)
            continue
        if _job_score(job) > _job_score(best_by_id[job_id]):
            best_by_id[job_id] = job
    return [best_by_id[job_id] for job_id in order]


def _job_score(job: dict[str, Any]) -> float:
    value = job.get("final_score", job.get("score", 0.0))
    return float(value) if isinstance(value, int | float) else 0.0


def _job_matches_terms(job: dict[str, Any], terms: set[str]) -> bool:
    haystack = _normalized_text(
        " ".join(
            part
            for part in [
                str(job.get("title") or ""),
                str(job.get("content") or ""),
                " ".join(skill for skill in job.get("skills") or [] if isinstance(skill, str)),
                " ".join(skill for skill in job.get("matched_skills") or [] if isinstance(skill, str)),
            ]
            if part
        )
    )
    if not haystack:
        return False
    specific_terms = terms - _GENERIC_RELEVANCE_TERMS
    if specific_terms:
        return all(term in haystack for term in specific_terms)
    return any(term in haystack for term in terms)


def _relevance_terms(text: str) -> set[str]:
    return set(_relevance_terms_ordered(text))


def _relevance_terms_ordered(text: str) -> list[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "best",
        "current",
        "find",
        "for",
        "fresh",
        "get",
        "in",
        "job",
        "jobs",
        "latest",
        "list",
        "live",
        "matching",
        "me",
        "more",
        "new",
        "offer",
        "offers",
        "online",
        "opportunities",
        "opportunity",
        "please",
        "role",
        "roles",
        "search",
        "show",
        "the",
        "to",
    }
    locations = {"amsterdam", "berlin", "london", "lyon", "paris"}
    terms: list[str] = []
    seen: set[str] = set()
    for token in _normalized_text(_search_query(text)).split():
        if len(token) < 3 or token.isdigit() or token in stopwords or token in locations or token in seen:
            continue
        terms.append(token)
        seen.add(token)
    return terms


def _target_profile_missing(local: dict[str, Any]) -> bool:
    return "Target profile not found." in (local.get("warnings") or [])


def _wants_live_jobs(text: str) -> bool:
    normalized = _normalized_text(text)
    return any(word in normalized.split() for word in ("fresh", "live", "current", "new", "latest", "online"))


def _jobspy_search_term(text: str, *, target_profile_id: str | None) -> str | None:
    query = _role_search_query(text)
    if query and query.lower() not in {"job", "jobs", "role", "roles", "offer", "offers"}:
        return query
    if not target_profile_id:
        return None
    profile = get_target_profile_with_evidence(target_profile_id)
    if not profile:
        raise TargetProfileNotFoundError(f"Target profile not found: {target_profile_id}")
    roles = [role for role in profile.get("target_roles") or [] if isinstance(role, str) and role.strip()]
    if roles:
        return roles[0].strip()
    name = profile.get("name")
    return name.strip() if isinstance(name, str) and name.strip() else None


def _search_query(text: str) -> str:
    query = re.sub(r"\b(fetch|find|search|show|get|list|jobs?|roles?|offers?)\b", " ", text, flags=re.IGNORECASE)
    query = re.sub(r"\s+", " ", query).strip()
    return query or text


def _role_search_query(text: str) -> str | None:
    terms = _relevance_terms_ordered(text)
    return " ".join(terms) if terms else None


def _merge_filters(text: str, filters: JobSearchFilters) -> JobSearchFilters:
    normalized = text.lower()
    return JobSearchFilters(
        location=filters.location or _first_location(normalized),
        contract_type=filters.contract_type or _first_contract_type(normalized),
        company=filters.company,
        seniority=filters.seniority or _first_seniority(normalized),
        remote_policy=filters.remote_policy or _first_remote_policy(normalized),
    )


def _first_location(text: str) -> str | None:
    for location in ("paris", "lyon", "berlin", "amsterdam", "london"):
        if location in text:
            return location.title()
    return None


def _first_contract_type(text: str) -> str | None:
    if "contract" in text or "freelance" in text:
        return "contract"
    if "full time" in text or "full-time" in text or "permanent" in text:
        return "full-time"
    return None


def _first_seniority(text: str) -> str | None:
    if "senior" in text:
        return "senior"
    if "lead" in text:
        return "lead"
    if "mid" in text or "middle" in text:
        return "mid-level"
    return None


def _first_remote_policy(text: str) -> str | None:
    if "hybrid" in text:
        return "hybrid"
    if "onsite" in text or "on-site" in text:
        return "onsite"
    if "remote" in text:
        return "remote"
    return None


def _jobspy_job_type(contract_type: str | None) -> str | None:
    if not contract_type:
        return None
    normalized = contract_type.lower()
    if normalized in {"full-time", "full time", "permanent"}:
        return "fulltime"
    if normalized in {"part-time", "part time"}:
        return "parttime"
    if normalized == "contract":
        return "contract"
    return None


def _record_jobspy_run(
    runs: ProviderImportRunRepository,
    *,
    params: dict[str, Any],
    created: int,
    skipped: int,
    indexed: int,
    status: str,
    error: str | None,
) -> None:
    runs.create(
        {
            "provider": "jobspy",
            "query": params,
            "requested_count": int(params.get("count") or 0),
            "created_count": created,
            "skipped_count": skipped,
            "indexed_count": indexed,
            "status": status,
            "error": error,
        }
    )


def _normalized_text(text: str) -> str:
    normalized = re.sub(r"[^\w\s-]", " ", text.lower())
    return re.sub(r"\s+", " ", normalized).strip()


_GENERIC_RELEVANCE_TERMS = {"developer", "engineer", "engineering", "software", "role", "roles"}


def _emit(event: dict[str, Any]) -> None:
    try:
        get_stream_writer()(event)
    except RuntimeError:
        return
