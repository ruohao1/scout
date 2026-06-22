from __future__ import annotations

from dataclasses import asdict
import re
from typing import Any, Iterator, Protocol, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from rag.types import JobSearchFilters

from .chat import ChatResult, classify_chat_intent, missing_target_profile_message, target_profile_not_found_message, vague_search_message
from .job_search_agent import (
    _chat_result_from_local,
    _core_query_terms,
    _fetch_live_jobs,
    _has_good_enough_results,
    _healthcare_core_matches,
    _job_matches_core_terms,
    _parse_job_find_request,
    _run_local_search,
)


class ScoutMultiAgentState(TypedDict, total=False):
    message: str
    history: list[dict[str, Any]]
    target_profile_id: str | None
    profile_id: str | None
    filters: dict[str, Any]
    limit: int
    route: dict[str, Any]
    selected_target_profile_id: str | None
    request: dict[str, Any]
    local_result: dict[str, Any]
    live_result: dict[str, Any]
    final_local_result: dict[str, Any]
    fetched_live: bool
    relaxed_student_search: bool
    warnings: list[str]
    result: dict[str, Any]


class CompiledScoutMultiAgent(Protocol):
    def invoke(self, input: ScoutMultiAgentState) -> ScoutMultiAgentState:
        ...

    def stream(self, input: ScoutMultiAgentState, **kwargs: Any) -> Iterator[dict[str, Any]]:
        ...


def respond_to_scout_multi_agent(
    *,
    message: str,
    history: list[dict[str, Any]] | None = None,
    target_profile_id: str | None = None,
    profile_id: str | None = None,
    filters: JobSearchFilters | None = None,
    limit: int = 5,
    route: dict[str, Any] | None = None,
    graph: CompiledScoutMultiAgent | None = None,
) -> ChatResult:
    workflow = graph or build_scout_multi_agent_graph()
    input_state: ScoutMultiAgentState = {
        "message": message,
        "history": history or [],
        "target_profile_id": target_profile_id,
        "profile_id": profile_id,
        "filters": asdict(filters or JobSearchFilters()),
        "limit": limit,
        "route": route or {},
        "warnings": [],
    }
    state = _run_scout_multi_agent_graph(workflow, input_state)
    result = state.get("result") or {}
    return ChatResult(
        message=str(result.get("message") or "What would you like to do next?"),
        tool=_public_tool_name(result.get("tool")),
        jobs=_dict_list(result.get("jobs")),
        ranked_jobs=_dict_list(result.get("ranked_jobs")),
        warnings=_string_list(result.get("warnings")),
    )


def build_scout_multi_agent_graph() -> CompiledScoutMultiAgent:
    builder = StateGraph(ScoutMultiAgentState)

    def intent_agent(state: ScoutMultiAgentState) -> dict[str, Any]:
        _emit({"type": "step_started", "id": "intent_agent", "title": "Interpret job-search intent"})
        selected_target_profile_id = state.get("target_profile_id") or state.get("profile_id")
        route = state.get("route") or {}
        summary = str(route.get("intent") or route.get("route") or "job_search")
        _emit({"type": "step_completed", "id": "intent_agent", "summary": f"Intent: {summary}"})
        return {"selected_target_profile_id": selected_target_profile_id}

    def query_normalizer_agent(state: ScoutMultiAgentState) -> dict[str, Any]:
        _emit({"type": "step_started", "id": "query_normalizer_agent", "title": "Normalize job query"})
        route = state.get("route") or {}
        request = _parse_job_find_request(
            text=state.get("message", ""),
            history=state.get("history") or [],
            route_query=route.get("query") if isinstance(route.get("query"), str) else None,
            route_intent=route.get("intent") if isinstance(route.get("intent"), str) else None,
            route_wants_live=route.get("wants_live") if isinstance(route.get("wants_live"), bool) else None,
            filters=JobSearchFilters(**(state.get("filters") or {})),
            fallback_limit=int(state.get("limit") or 5),
        )
        request_dict = asdict(request)
        summary_parts = [request.query]
        if request.filters.location:
            summary_parts.append(f"location={request.filters.location}")
        if request.filters.contract_type:
            summary_parts.append(f"contract={request.filters.contract_type}")
        _emit({"type": "step_completed", "id": "query_normalizer_agent", "summary": "; ".join(summary_parts)})
        return {"request": request_dict, "filters": request_dict["filters"], "limit": request.limit}

    def request_guard_agent(state: ScoutMultiAgentState) -> dict[str, Any]:
        _emit({"type": "step_started", "id": "request_guard_agent", "title": "Check required search inputs"})
        request = _request(state)
        selected_target_profile_id = state.get("selected_target_profile_id")
        warnings = _warnings(state)
        if not request.get("wants_ranking") and classify_chat_intent(str(request.get("query") or "")) == "vague_search":
            warning = "Search request needs role, skill, location, or target profile detail."
            _emit({"type": "step_completed", "id": "request_guard_agent", "summary": "Search request is too vague"})
            return {"warnings": [*warnings, warning], "result": _result(vague_search_message(), warnings=[*warnings, warning])}
        if request.get("wants_ranking") and not selected_target_profile_id:
            warning = "target_profile_id is required for matching."
            _emit({"type": "step_completed", "id": "request_guard_agent", "summary": "Missing target profile"})
            return {"warnings": [*warnings, warning], "result": _result(missing_target_profile_message(), warnings=[*warnings, warning])}
        _emit({"type": "step_completed", "id": "request_guard_agent", "summary": "Request is actionable"})
        return {}

    def route_after_guard(state: ScoutMultiAgentState) -> str:
        return "answer_agent" if state.get("result") else "retrieval_agent"

    def retrieval_agent(state: ScoutMultiAgentState) -> dict[str, Any]:
        _emit({"type": "step_started", "id": "retrieval_agent", "title": "Search indexed jobs"})
        request = _request(state)
        local = _run_local_search(
            text=_search_text(request, state),
            wants_ranking=bool(request.get("wants_ranking")),
            target_profile_id=state.get("selected_target_profile_id"),
            filters=_request_filters(request),
            limit=int(request.get("limit") or state.get("limit") or 5),
        )
        if _target_profile_missing(local):
            _emit({"type": "step_completed", "id": "retrieval_agent", "summary": "Target profile not found"})
            return {"local_result": local, "final_local_result": local, "result": _result(target_profile_not_found_message(), warnings=_warnings(state, local.get("warnings")))}
        final_local = local
        relaxed = False
        if not request.get("wants_ranking") and _should_relax_student_search(request) and not _has_good_enough_results(local, int(request.get("limit") or state.get("limit") or 5)):
            _emit({"type": "step_started", "id": "relaxed_retrieval_agent", "title": "Search like a job board keyword query"})
            relaxed_local = _run_local_search(
                text=_relaxed_student_search_text(request, state),
                wants_ranking=False,
                target_profile_id=state.get("selected_target_profile_id"),
                filters=_relaxed_filters(request),
                limit=int(request.get("limit") or state.get("limit") or 5),
            )
            relaxed_count = len(relaxed_local.get("ranked_jobs") or relaxed_local.get("jobs") or [])
            strict_count = len(local.get("ranked_jobs") or local.get("jobs") or [])
            if relaxed_count > strict_count:
                final_local = relaxed_local
                relaxed = True
                _emit({"type": "step_completed", "id": "relaxed_retrieval_agent", "summary": f"Accepted {relaxed_count} relaxed keyword results"})
            else:
                _emit({"type": "step_completed", "id": "relaxed_retrieval_agent", "summary": f"Kept strict results over {relaxed_count} relaxed results"})
        count = len(final_local.get("ranked_jobs") or final_local.get("jobs") or [])
        _emit({"type": "step_completed", "id": "retrieval_agent", "summary": f"Retrieved {count} local results"})
        return {"local_result": local, "final_local_result": final_local, "relaxed_student_search": relaxed}

    def route_after_retrieval(state: ScoutMultiAgentState) -> str:
        if state.get("result"):
            return "answer_agent"
        request = _request(state)
        local = state.get("final_local_result") or state.get("local_result") or {}
        if local.get("ok") is False:
            return "validation_agent"
        should_fetch_live = bool(request.get("wants_live")) or not _has_good_enough_results(local, int(request.get("limit") or state.get("limit") or 5))
        return "job_import_agent" if should_fetch_live else "validation_agent"

    def job_import_agent(state: ScoutMultiAgentState) -> dict[str, Any]:
        _emit({"type": "step_started", "id": "job_import_agent", "title": "Fetch live jobs"})
        request = _request(state)
        live = _fetch_live_jobs(
            text=_live_search_text(request, state),
            target_profile_id=state.get("selected_target_profile_id"),
            filters=_live_filters(request),
            limit=int(request.get("limit") or state.get("limit") or 5),
            importer=None,
        )
        summary = "Fetched live jobs" if live.get("ok") else "Live fetch failed"
        _emit({"type": "step_completed", "id": "job_import_agent", "summary": summary})
        return {"live_result": live, "fetched_live": True}

    def refresh_retrieval_agent(state: ScoutMultiAgentState) -> dict[str, Any]:
        live = state.get("live_result") or {}
        local = state.get("local_result") or {}
        if not live.get("ok"):
            if len(local.get("ranked_jobs") or local.get("jobs") or []) > 0:
                warnings = _warnings(state, live.get("warnings"), ["Live JobSpy search failed; showing indexed local results instead."])
                return {"final_local_result": local, "warnings": warnings}
            warnings = _warnings(state, live.get("warnings"))
            return {"final_local_result": {"ok": True, "tool": "job_search_agent", "jobs": [], "ranked_jobs": [], "warnings": warnings}, "warnings": warnings}

        _emit({"type": "step_started", "id": "refresh_retrieval_agent", "title": "Refresh indexed search"})
        request = _request(state)
        refreshed = _run_local_search(
            text=_live_search_text(request, state),
            wants_ranking=bool(request.get("wants_ranking")),
            target_profile_id=state.get("selected_target_profile_id"),
            filters=_live_filters(request),
            limit=int(request.get("limit") or state.get("limit") or 5),
        )
        warnings = _warnings(state, live.get("warnings"), refreshed.get("warnings"))
        count = len(refreshed.get("ranked_jobs") or refreshed.get("jobs") or [])
        if count == 0 and len(local.get("ranked_jobs") or local.get("jobs") or []) > 0:
            warnings.append("Live refresh returned no stronger matches; keeping indexed local results.")
            _emit({"type": "step_completed", "id": "refresh_retrieval_agent", "summary": "Kept local results after empty refresh"})
            return {"final_local_result": local, "warnings": warnings}
        _emit({"type": "step_completed", "id": "refresh_retrieval_agent", "summary": f"Retrieved {count} refreshed results"})
        return {"final_local_result": refreshed, "relaxed_student_search": _should_relax_student_search(request), "warnings": warnings}

    def validation_agent(state: ScoutMultiAgentState) -> dict[str, Any]:
        _emit({"type": "step_started", "id": "validation_agent", "title": "Validate job constraints"})
        request = _request(state)
        local = dict(state.get("final_local_result") or state.get("local_result") or {})
        relaxed_student = bool(state.get("relaxed_student_search"))
        filters = _relaxed_filters(request) if relaxed_student else _request_filters(request)
        core_terms = _core_query_terms(_live_search_text(request, state) if relaxed_student else _search_text(request, state))
        jobs, broader_jobs = _validate_job_buckets(_dict_list(local.get("jobs")), filters=filters, core_terms=core_terms, require_student_like=relaxed_student)
        ranked_jobs, broader_ranked_jobs = _validate_job_buckets(_dict_list(local.get("ranked_jobs")), filters=filters, core_terms=core_terms, require_student_like=relaxed_student)
        warnings = _warnings(state, local.get("warnings"))
        original_count = len(_dict_list(local.get("jobs"))) + len(_dict_list(local.get("ranked_jobs")))
        if len(jobs) + len(ranked_jobs) < 5:
            jobs = [*jobs, *broader_jobs]
            ranked_jobs = [*ranked_jobs, *broader_ranked_jobs]
            if broader_jobs or broader_ranked_jobs:
                warnings.append("Included broader matches after strict validation found too few strong matches.")
        validated_count = len(jobs) + len(ranked_jobs)
        if relaxed_student and validated_count:
            warnings.append("Relaxed contract/seniority filters and searched student terms like a job board keyword search.")
        if original_count and validated_count < original_count:
            warnings.append("Validation agent removed jobs that did not match the requested constraints.")
        local["jobs"] = jobs
        local["ranked_jobs"] = ranked_jobs
        local["warnings"] = warnings
        _emit({"type": "step_completed", "id": "validation_agent", "summary": f"Accepted {validated_count} jobs"})
        return {"final_local_result": local, "warnings": warnings}

    def answer_agent(state: ScoutMultiAgentState) -> dict[str, Any]:
        if state.get("result"):
            return {"result": state["result"]}
        _emit({"type": "step_started", "id": "answer_agent", "title": "Prepare final answer"})
        request = _request(state)
        live = state.get("live_result") or {}
        result = _chat_result_from_local(
            state.get("final_local_result") or state.get("local_result") or {},
            fetched_live=bool(state.get("fetched_live")),
            created=int(live.get("created") or 0),
            indexed=int(live.get("indexed") or 0),
            warnings=_warnings(state),
            search_text=_search_text(request, state),
            filters=_request_filters(request),
        )
        _emit({"type": "step_completed", "id": "answer_agent", "summary": f"Prepared answer with {result.tool}"})
        return {"result": asdict(result)}

    builder.add_node("intent_agent", intent_agent)
    builder.add_node("query_normalizer_agent", query_normalizer_agent)
    builder.add_node("request_guard_agent", request_guard_agent)
    builder.add_node("retrieval_agent", retrieval_agent)
    builder.add_node("job_import_agent", job_import_agent)
    builder.add_node("refresh_retrieval_agent", refresh_retrieval_agent)
    builder.add_node("validation_agent", validation_agent)
    builder.add_node("answer_agent", answer_agent)

    builder.add_edge(START, "intent_agent")
    builder.add_edge("intent_agent", "query_normalizer_agent")
    builder.add_edge("query_normalizer_agent", "request_guard_agent")
    builder.add_conditional_edges("request_guard_agent", route_after_guard, {"retrieval_agent": "retrieval_agent", "answer_agent": "answer_agent"})
    builder.add_conditional_edges("retrieval_agent", route_after_retrieval, {"job_import_agent": "job_import_agent", "validation_agent": "validation_agent", "answer_agent": "answer_agent"})
    builder.add_edge("job_import_agent", "refresh_retrieval_agent")
    builder.add_edge("refresh_retrieval_agent", "validation_agent")
    builder.add_edge("validation_agent", "answer_agent")
    builder.add_edge("answer_agent", END)
    return builder.compile()


def _run_scout_multi_agent_graph(workflow: CompiledScoutMultiAgent, input_state: ScoutMultiAgentState) -> ScoutMultiAgentState:
    final_state: ScoutMultiAgentState = dict(input_state)
    try:
        chunks = workflow.stream(input_state, stream_mode=["updates", "custom"], version="v2")
    except TypeError:
        return workflow.invoke(input_state)
    for chunk in chunks:
        if chunk.get("type") == "custom":
            event = chunk.get("data")
            if isinstance(event, dict):
                _emit(event)
            continue
        if chunk.get("type") != "updates":
            continue
        data = chunk.get("data")
        if not isinstance(data, dict):
            continue
        for update in data.values():
            if isinstance(update, dict):
                final_state.update(update)
    return final_state


def _request(state: ScoutMultiAgentState) -> dict[str, Any]:
    value = state.get("request")
    return value if isinstance(value, dict) else {}


def _request_filters(request: dict[str, Any]) -> JobSearchFilters:
    filters = request.get("filters") if isinstance(request.get("filters"), dict) else {}
    return JobSearchFilters(**filters)


def _relaxed_filters(request: dict[str, Any]) -> JobSearchFilters:
    filters = _request_filters(request)
    return JobSearchFilters(
        location=filters.location,
        company=filters.company,
        remote_policy=filters.remote_policy,
        source=filters.source,
    )


def _search_text(request: dict[str, Any], state: ScoutMultiAgentState) -> str:
    for key in ("role_query", "query"):
        value = request.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return str(state.get("message") or "")


def _live_search_text(request: dict[str, Any], state: ScoutMultiAgentState) -> str:
    if _should_relax_student_search(request):
        return _relaxed_student_search_text(request, state)
    return _search_text(request, state)


def _live_filters(request: dict[str, Any]) -> JobSearchFilters:
    return _relaxed_filters(request) if _should_relax_student_search(request) else _request_filters(request)


def _relaxed_student_search_text(request: dict[str, Any], state: ScoutMultiAgentState) -> str:
    text = _search_text(request, state)
    normalized = _normalized(text)
    if re.search(r"\b(student|intern|internship|stage|stagiaire|placement|trainee|co-op|coop|summer|graduate)\b", normalized):
        return text
    return f"{text} student".strip()


def _should_relax_student_search(request: dict[str, Any]) -> bool:
    filters = _request_filters(request)
    if _normalized(str(filters.contract_type or "")) == "internship":
        return True
    if _normalized(str(filters.seniority or "")) == "student":
        return True
    text = " ".join(str(request.get(key) or "") for key in ("query", "role_query"))
    return bool(re.search(r"\b(student|intern|internship|stage|stagiaire|placement|trainee|co-op|coop|summer)\b", _normalized(text)))


def _validate_jobs(jobs: list[dict[str, Any]], *, filters: JobSearchFilters, core_terms: list[str] | None = None, require_student_like: bool = False) -> list[dict[str, Any]]:
    strong, broader = _validate_job_buckets(jobs, filters=filters, core_terms=core_terms, require_student_like=require_student_like)
    return [*strong, *broader]


def _validate_job_buckets(jobs: list[dict[str, Any]], *, filters: JobSearchFilters, core_terms: list[str] | None = None, require_student_like: bool = False) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    required_core_terms = core_terms or []
    strong: list[dict[str, Any]] = []
    broader: list[dict[str, Any]] = []
    for job in jobs:
        if not _matches_location(job, filters.location):
            continue
        if not _matches_contract_type(job, filters.contract_type):
            continue
        if require_student_like and not _is_student_like(job):
            continue
        if _job_matches_core_terms(job, required_core_terms) and _job_matches_strong_core_terms(job, required_core_terms):
            strong.append(job)
        elif _job_matches_broader_core_terms(job, required_core_terms):
            broader.append(job)
    return strong, broader


def _matches_location(job: dict[str, Any], location: str | None) -> bool:
    if not location:
        return True
    job_location = _normalized(str(job.get("location") or ""))
    requested = _normalized(location)
    if not job_location:
        return False
    if requested in {"usa", "us", "u s", "u s a", "united states", "united states of america"}:
        return _matches_usa_location(str(job.get("location") or ""))
    aliases = _location_aliases(requested)
    return any(alias in job_location for alias in aliases)


def _matches_usa_location(location: str) -> bool:
    raw = location.strip()
    if not raw:
        return False
    if re.search(r",\s*(ab|bc|mb|nb|nl|ns|nt|nu|on|pe|qc|sk|yt)\s*,\s*ca\s*$", raw, re.IGNORECASE):
        return False
    state_codes = "|".join(sorted(_US_STATE_CODES))
    return bool(
        re.search(r"(^|[,\s])(usa|u\.s\.|us|united states( of america)?)([,\s]|$)", raw, re.IGNORECASE)
        or re.search(rf",\s*({state_codes})(\s*,\s*(us|usa|u\.s\.|united states( of america)?))?\s*$", raw, re.IGNORECASE)
    )


def _matches_contract_type(job: dict[str, Any], contract_type: str | None) -> bool:
    if not contract_type:
        return True
    normalized = _normalized(contract_type)
    if normalized == "internship":
        return _is_internship_like(job)
    return _normalized(str(job.get("contract_type") or "")) == normalized


def _is_internship_like(job: dict[str, Any]) -> bool:
    title = _normalized(str(job.get("title") or ""))
    if re.search(r"\b(intern|internship|stage|stagiaire|placement|trainee)\b", title):
        return True
    if _has_senior_title(title):
        return False
    if _normalized(str(job.get("contract_type") or "")) == "internship":
        return True
    text = _normalized("\n".join(str(job.get(field) or "") for field in ("content", "description")))
    return bool(re.search(r"\b(internship programme|internship program|student placement|co-op|coop|trainee programme|trainee program)\b", text))


def _is_student_like(job: dict[str, Any]) -> bool:
    if _is_internship_like(job):
        return True
    title = _normalized(str(job.get("title") or ""))
    if re.search(r"\b(student|co-op|coop|summer|graduate|campus|early career)\b", title):
        return True
    if _has_senior_title(title):
        return False
    text = _normalized("\n".join(str(job.get(field) or "") for field in ("content", "description")))
    return bool(re.search(r"\b(graduate programme|graduate program|campus recruitment|early career programme|early career program|summer internship|co-op programme|co-op program|coop programme|coop program)\b", text))


def _has_senior_title(title: str) -> bool:
    return bool(re.search(r"\b(senior|staff|principal|lead|head of|director|manager|lecturer|professor)\b", title))


def _job_matches_broader_core_terms(job: dict[str, Any], core_terms: list[str]) -> bool:
    if not core_terms:
        return True
    title = _normalized(str(job.get("title") or ""))
    text = _normalized("\n".join(str(job.get(field) or "") for field in ("title", "content", "description", "company")))
    if "cybersecurity" in core_terms:
        if re.search(r"\b(go-to-market|gtm|marketing|sales|barista|office assistant|faculty|teacher|lecturer|professor)\b", title):
            return False
        return bool(re.search(r"\b(cyber|cybersecurity|cyber security|security|iam|soc|grc|dlp|siem|infosec|information security)\b", text))
    return False


def _job_matches_strong_core_terms(job: dict[str, Any], core_terms: list[str]) -> bool:
    if not core_terms:
        return True
    title = _normalized(str(job.get("title") or ""))
    skills = _normalized(" ".join(skill for skill in [*(job.get("skills") or []), *(job.get("matched_skills") or [])] if isinstance(skill, str)))
    if "cybersecurity" in core_terms:
        return bool(
            re.search(
                r"\b(cyber|cybersecurity|cyber security|security|infosec|information security|soc|grc|dlp|siem|iam|red team|blue team)\b",
                f"{title} {skills}",
            )
        )
    if "healthcare" in core_terms:
        company = _normalized(str(job.get("company") or ""))
        return _healthcare_core_matches(f"{title} {company} {skills}")
    return True


def _location_aliases(location: str) -> set[str]:
    aliases = {location}
    if location in {"usa", "us", "u s", "u s a", "united states", "united states of america"}:
        aliases.update({"usa", "united states"})
    if location == "england":
        aliases.update({"uk", "united kingdom", "england"})
    if location == "uk":
        aliases.update({"uk", "united kingdom", "england"})
    if location == "united kingdom":
        aliases.update({"uk", "united kingdom", "england"})
    if location == "san francisco":
        aliases.update(
            {
                "san francisco",
                "san francisco bay area",
                "bay area",
                "oakland",
                "berkeley",
                "palo alto",
                "mountain view",
                "menlo park",
                "redwood city",
                "san mateo",
                "san jose",
                "sunnyvale",
                "santa clara",
            }
        )
    if location == "spain":
        aliases.update({"spain", "espagne"})
    if location == "luxembourg":
        aliases.add("luxembourg")
    return aliases


_US_STATE_CODES = {
    "al",
    "ak",
    "az",
    "ar",
    "ca",
    "co",
    "ct",
    "de",
    "fl",
    "ga",
    "hi",
    "id",
    "il",
    "in",
    "ia",
    "ks",
    "ky",
    "la",
    "me",
    "md",
    "ma",
    "mi",
    "mn",
    "ms",
    "mo",
    "mt",
    "ne",
    "nv",
    "nh",
    "nj",
    "nm",
    "ny",
    "nc",
    "nd",
    "oh",
    "ok",
    "or",
    "pa",
    "ri",
    "sc",
    "sd",
    "tn",
    "tx",
    "ut",
    "vt",
    "va",
    "wa",
    "wv",
    "wi",
    "wy",
    "dc",
}


def _normalized(text: str) -> str:
    normalized = re.sub(r"[^\w\s-]", " ", text.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def _target_profile_missing(local: dict[str, Any]) -> bool:
    return "Target profile not found." in (local.get("warnings") or [])


def _warnings(state: ScoutMultiAgentState, *values: object) -> list[str]:
    warnings = [warning for warning in state.get("warnings", []) if isinstance(warning, str)]
    for value in values:
        if isinstance(value, list):
            warnings.extend(str(item) for item in value if item)
        elif value:
            warnings.append(str(value))
    return warnings


def _result(message: str, *, warnings: list[str]) -> dict[str, Any]:
    return {"message": message, "tool": "search_jobs", "jobs": [], "ranked_jobs": [], "warnings": warnings}


def _public_tool_name(value: object) -> str:
    tool = str(value or "search_jobs")
    return "search_jobs" if tool == "job_search_agent" else tool


def _dict_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _emit(event: dict[str, Any]) -> None:
    try:
        get_stream_writer()(event)
    except RuntimeError:
        return
