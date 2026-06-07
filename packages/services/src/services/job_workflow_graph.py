from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import re
from typing import Any, Iterator, Protocol, TypedDict

from db.provider_import_runs import ProviderImportRunRepository
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from rag.types import JobSearchFilters

from .chat import ChatResult
from .chat_orchestrator import ChatPlanningProvider
from .chat_orchestrator import respond_to_chat_with_tools
from .job_corpus import get_job_corpus_status
from .job_providers import AdzunaJobProviderAdapter, AdzunaJobProviderClient, MockJobProviderAdapter, MockJobProviderClient, import_jobs


class JobWorkflowState(TypedDict, total=False):
    message: str
    history: list[dict[str, Any]]
    profile_id: str | None
    filters: dict[str, Any]
    limit: int
    model: str
    corpus_status: dict[str, Any]
    result: dict[str, Any]


class CompiledWorkflow(Protocol):
    def invoke(self, input: JobWorkflowState) -> JobWorkflowState:
        ...

    def stream(self, input: JobWorkflowState, **kwargs: Any) -> Iterator[dict[str, Any]]:
        ...


def respond_to_chat_with_graph(
    *,
    message: str,
    history: list[dict[str, Any]] | None = None,
    profile_id: str | None = None,
    filters: JobSearchFilters | None = None,
    limit: int = 5,
    model: str | None = None,
    provider: ChatPlanningProvider | None = None,
    graph: CompiledWorkflow | None = None,
) -> ChatResult:
    workflow = graph or build_job_workflow_graph(provider=provider)
    state = workflow.invoke(_input_state(message=message, history=history, profile_id=profile_id, filters=filters, limit=limit, model=model or "gpt-5.5"))
    return _chat_result_from_state(state)


def stream_chat_with_graph(
    *,
    message: str,
    history: list[dict[str, Any]] | None = None,
    profile_id: str | None = None,
    filters: JobSearchFilters | None = None,
    limit: int = 5,
    model: str = "gpt-5.5",
    provider: ChatPlanningProvider | None = None,
    graph: CompiledWorkflow | None = None,
) -> Iterator[dict[str, Any]]:
    workflow = graph or build_job_workflow_graph(provider=provider)
    final_state: JobWorkflowState = {}
    for chunk in workflow.stream(
        _input_state(message=message, history=history, profile_id=profile_id, filters=filters, limit=limit, model=model),
        stream_mode=["updates", "custom"],
        version="v2",
    ):
        if chunk.get("type") == "custom":
            event = chunk.get("data")
            if isinstance(event, dict):
                yield event
        elif chunk.get("type") == "updates":
            data = chunk.get("data")
            if isinstance(data, dict):
                for update in data.values():
                    if isinstance(update, dict):
                        final_state.update(update)
    yield {"type": "done", "response": asdict(_chat_result_from_state(final_state))}


def _input_state(
    *,
    message: str,
    history: list[dict[str, Any]] | None,
    profile_id: str | None,
    filters: JobSearchFilters | None,
    limit: int,
    model: str,
) -> JobWorkflowState:
    return {
        "message": message,
        "history": history or [],
        "profile_id": profile_id,
        "filters": asdict(filters or JobSearchFilters()),
        "limit": limit,
        "model": model,
    }


def _chat_result_from_state(state: JobWorkflowState) -> ChatResult:
    result = state.get("result") or {}
    return ChatResult(
        message=str(result.get("message") or "What would you like to do next?"),
        tool=str(result.get("tool") or "none"),
        jobs=_dict_list(result.get("jobs")),
        ranked_jobs=_dict_list(result.get("ranked_jobs")),
        warnings=_string_list(result.get("warnings")),
    )


def build_job_workflow_graph(*, provider: ChatPlanningProvider | None = None):
    builder = StateGraph(JobWorkflowState)

    def check_corpus(state: JobWorkflowState) -> dict[str, Any]:
        _emit({"type": "step_started", "id": "check_corpus", "title": "Check job corpus"})
        try:
            status = asdict(get_job_corpus_status())
        except Exception as exc:
            status = {"total_jobs": 0, "indexed_jobs": 0, "unindexed_jobs": 0, "source": None, "error": str(exc)}
        _emit({"type": "step_completed", "id": "check_corpus", "summary": f"{status.get('total_jobs', 0)} jobs, {status.get('indexed_jobs', 0)} indexed"})
        return {"corpus_status": status}

    def route_initial(state: JobWorkflowState) -> str:
        message = state.get("message", "")
        history = state.get("history") or []
        if _is_corpus_status_request(message):
            return "check_corpus"
        if _is_adzuna_import_request(message) or (_is_confirmation(message) and _history_requested_adzuna_import(history)):
            return "check_corpus"
        if _is_mock_import_request(message) or (_is_confirmation(message) and _history_requested_mock_import(history)):
            return "check_corpus"
        return "plan_and_run"

    def route_after_status(state: JobWorkflowState) -> str:
        message = state.get("message", "")
        if _is_corpus_status_request(message):
            return "corpus_status_response"
        if _is_adzuna_import_request(message) or (_is_confirmation(message) and _history_requested_adzuna_import(state.get("history") or [])):
            return "import_adzuna_jobs" if _is_confirmation(message) else "request_adzuna_import_confirmation"
        if _is_mock_import_request(message) or (_is_confirmation(message) and _history_requested_mock_import(state.get("history") or [])):
            return "import_mock_jobs" if _is_confirmation(message) else "request_mock_import_confirmation"
        return "plan_and_run"

    def corpus_status_response(state: JobWorkflowState) -> dict[str, Any]:
        _emit({"type": "step_started", "id": "summarize", "title": "Summarize corpus status"})
        _emit({"type": "tool_started", "id": "get_job_corpus_status", "tool": "get_job_corpus_status", "args": {}})
        status = state.get("corpus_status") or {}
        message = (
            "Here is the current job corpus status.\n\n"
            f"- **Total jobs:** {status.get('total_jobs', 0)}\n"
            f"- **Indexed jobs:** {status.get('indexed_jobs', 0)}\n"
            f"- **Unindexed jobs:** {status.get('unindexed_jobs', 0)}"
        )
        warnings = [str(status["error"])] if status.get("error") else []
        _emit({"type": "tool_completed", "id": "get_job_corpus_status", "summary": "Read corpus status"})
        _emit({"type": "step_completed", "id": "summarize", "summary": "Prepared corpus summary"})
        return {"result": {"message": message, "tool": "get_job_corpus_status", "jobs": [], "ranked_jobs": [], "warnings": warnings}}

    def request_mock_import_confirmation(state: JobWorkflowState) -> dict[str, Any]:
        _emit({"type": "step_started", "id": "confirm_import", "title": "Request import confirmation"})
        status = state.get("corpus_status") or {}
        message = (
            "I can import and index **10 mock jobs** for local testing.\n\n"
            "Current corpus:\n\n"
            f"- **Total jobs:** {status.get('total_jobs', 0)}\n"
            f"- **Indexed jobs:** {status.get('indexed_jobs', 0)}\n\n"
            "Reply **yes** to proceed."
        )
        _emit({"type": "step_completed", "id": "confirm_import", "summary": "Waiting for user confirmation"})
        return {
            "result": {
                "message": message,
                "tool": "get_job_corpus_status",
                "jobs": [],
                "ranked_jobs": [],
                "warnings": ["confirm_import_mock_jobs"],
            }
        }

    def import_mock_jobs_node(state: JobWorkflowState) -> dict[str, Any]:
        _emit({"type": "step_started", "id": "import_mock_jobs", "title": "Import mock jobs"})
        _emit({"type": "tool_started", "id": "import_mock_jobs", "tool": "import_mock_jobs", "args": {"count": 10, "index": True}})
        try:
            result = import_jobs(
                client=MockJobProviderClient(fixture_path=_mock_fixture_path()),
                adapter=MockJobProviderAdapter(),
                count=10,
                should_index=True,
            )
        except Exception as exc:
            _emit({"type": "tool_failed", "id": "import_mock_jobs", "summary": str(exc)})
            _emit({"type": "step_failed", "id": "import_mock_jobs", "summary": "Mock import failed"})
            return {
                "result": {
                    "message": (
                        "I could not import and index mock jobs.\n\n"
                        "Check these items:\n\n"
                        "- Database is running\n"
                        "- Job schema has been set up\n"
                        "- Embedding provider is configured"
                    ),
                    "tool": "import_mock_jobs",
                    "jobs": [],
                    "ranked_jobs": [],
                    "warnings": [str(exc)],
                }
            }
        message = (
            "Mock jobs are ready.\n\n"
            f"- **Imported:** {len(result.created)}\n"
            f"- **Skipped duplicates:** {result.skipped}\n"
            f"- **Indexed:** {result.indexed}\n\n"
            "You can now ask Scout to search or rank these jobs."
        )
        _emit({"type": "tool_completed", "id": "import_mock_jobs", "summary": message})
        _emit({"type": "step_completed", "id": "import_mock_jobs", "summary": message})
        return {"result": {"message": message, "tool": "import_mock_jobs", "jobs": [], "ranked_jobs": [], "warnings": []}}

    def request_adzuna_import_confirmation(state: JobWorkflowState) -> dict[str, Any]:
        _emit({"type": "step_started", "id": "confirm_adzuna_import", "title": "Request Adzuna import confirmation"})
        params = _adzuna_import_params_from_state(state)
        query = _format_adzuna_query(params)
        message = (
            f"I can fetch and index up to **{params['count']} fresh Adzuna jobs** for {query}.\n\n"
            "Current corpus:\n\n"
            f"- **Total jobs:** {(state.get('corpus_status') or {}).get('total_jobs', 0)}\n"
            f"- **Indexed jobs:** {(state.get('corpus_status') or {}).get('indexed_jobs', 0)}\n\n"
            "Reply **yes** to proceed.\n\n"
            f'Confirmation details: confirm_import_adzuna_jobs country={params["country"]}; '
            f'what={params.get("what") or ""}; where={params.get("where") or ""}; count={params["count"]}.'
        )
        _emit({"type": "step_completed", "id": "confirm_adzuna_import", "summary": "Waiting for user confirmation"})
        return {
            "result": {
                "message": message,
                "tool": "get_job_corpus_status",
                "jobs": [],
                "ranked_jobs": [],
                "warnings": ["confirm_import_adzuna_jobs"],
            }
        }

    def import_adzuna_jobs_node(state: JobWorkflowState) -> dict[str, Any]:
        _emit({"type": "step_started", "id": "import_adzuna_jobs", "title": "Import Adzuna jobs"})
        params = _adzuna_import_params_from_state(state)
        _emit({"type": "tool_started", "id": "import_adzuna_jobs", "tool": "import_adzuna_jobs", "args": params})
        runs = ProviderImportRunRepository()
        try:
            result = import_jobs(
                client=AdzunaJobProviderClient(
                    country=params["country"],
                    what=params.get("what"),
                    where=params.get("where"),
                    results_per_page=50,
                ),
                adapter=AdzunaJobProviderAdapter(),
                count=params["count"],
                should_index=True,
            )
        except Exception as exc:
            _record_adzuna_run(runs, params=params, created=0, skipped=0, indexed=0, status="failed", error=str(exc))
            _emit({"type": "tool_failed", "id": "import_adzuna_jobs", "summary": str(exc)})
            _emit({"type": "step_failed", "id": "import_adzuna_jobs", "summary": "Adzuna import failed"})
            return {
                "result": {
                    "message": (
                        "I could not import and index Adzuna jobs.\n\n"
                        "Check these items:\n\n"
                        "- `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` are set\n"
                        "- Database is running\n"
                        "- Embedding provider is configured"
                    ),
                    "tool": "import_adzuna_jobs",
                    "jobs": [],
                    "ranked_jobs": [],
                    "warnings": [str(exc)],
                }
            }

        _record_adzuna_run(
            runs,
            params=params,
            created=len(result.created),
            skipped=result.skipped,
            indexed=result.indexed,
            status="completed",
            error=None,
        )
        message = (
            "Adzuna import is complete.\n\n"
            f"- **Imported:** {len(result.created)}\n"
            f"- **Skipped duplicates:** {result.skipped}\n"
            f"- **Indexed:** {result.indexed}\n\n"
            "You can now search or rank these fresh jobs."
        )
        _emit({"type": "tool_completed", "id": "import_adzuna_jobs", "summary": message})
        _emit({"type": "step_completed", "id": "import_adzuna_jobs", "summary": message})
        return {"result": {"message": message, "tool": "import_adzuna_jobs", "jobs": [], "ranked_jobs": [], "warnings": []}}

    def plan_and_run(state: JobWorkflowState) -> dict[str, Any]:
        _emit({"type": "step_started", "id": "plan", "title": "Plan next action"})
        result = respond_to_chat_with_tools(
            message=state.get("message", ""),
            history=state.get("history") or [],
            profile_id=state.get("profile_id"),
            filters=JobSearchFilters(**(state.get("filters") or {})),
            limit=int(state.get("limit") or 5),
            model=state.get("model") or "gpt-5.5",
            provider=provider,
        )
        _emit({"type": "step_completed", "id": "plan", "summary": f"Used {result.tool}" if result.tool != "none" else "Answered without a tool"})
        return {"result": asdict(result)}

    builder.add_node("check_corpus", check_corpus)
    builder.add_node("corpus_status_response", corpus_status_response)
    builder.add_node("request_mock_import_confirmation", request_mock_import_confirmation)
    builder.add_node("request_adzuna_import_confirmation", request_adzuna_import_confirmation)
    builder.add_node("import_mock_jobs", import_mock_jobs_node)
    builder.add_node("import_adzuna_jobs", import_adzuna_jobs_node)
    builder.add_node("plan_and_run", plan_and_run)
    builder.add_conditional_edges(
        START,
        route_initial,
        {
            "check_corpus": "check_corpus",
            "plan_and_run": "plan_and_run",
        },
    )
    builder.add_conditional_edges(
        "check_corpus",
        route_after_status,
        {
            "corpus_status_response": "corpus_status_response",
            "request_mock_import_confirmation": "request_mock_import_confirmation",
            "request_adzuna_import_confirmation": "request_adzuna_import_confirmation",
            "import_mock_jobs": "import_mock_jobs",
            "import_adzuna_jobs": "import_adzuna_jobs",
            "plan_and_run": "plan_and_run",
        },
    )
    builder.add_edge("corpus_status_response", END)
    builder.add_edge("request_mock_import_confirmation", END)
    builder.add_edge("request_adzuna_import_confirmation", END)
    builder.add_edge("import_mock_jobs", END)
    builder.add_edge("import_adzuna_jobs", END)
    builder.add_edge("plan_and_run", END)
    return builder.compile()


def _dict_list(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _emit(event: dict[str, Any]) -> None:
    try:
        get_stream_writer()(event)
    except RuntimeError:
        return


def _is_corpus_status_request(message: str) -> bool:
    normalized = message.lower()
    return any(phrase in normalized for phrase in ("corpus status", "indexed jobs", "how many jobs", "job count"))


def _is_mock_import_request(message: str) -> bool:
    normalized = message.lower()
    return "mock" in normalized and any(word in normalized for word in ("import", "ingest", "seed", "index"))


def _is_adzuna_import_request(message: str) -> bool:
    normalized = message.lower()
    provider_requested = "adzuna" in normalized or "real job" in normalized or "fresh job" in normalized
    action_requested = any(word in normalized for word in ("fetch", "import", "ingest", "find", "search", "index"))
    return provider_requested and action_requested


def _is_confirmation(message: str) -> bool:
    normalized = message.strip().lower()
    return normalized in {"yes", "y", "ok", "okay", "proceed", "go ahead", "confirm", "do it"}


def _history_requested_mock_import(history: list[dict[str, Any]]) -> bool:
    for item in history[-4:]:
        content = item.get("content")
        if isinstance(content, str) and "confirm_import_mock_jobs" in content:
            return True
        if isinstance(content, str) and "import and index 10 mock jobs" in content.lower():
            return True
    return False


def _history_requested_adzuna_import(history: list[dict[str, Any]]) -> bool:
    return _adzuna_import_params_from_history(history) is not None


def _adzuna_import_params_from_state(state: JobWorkflowState) -> dict[str, Any]:
    from_history = _adzuna_import_params_from_history(state.get("history") or [])
    if from_history is not None:
        return from_history
    return _adzuna_import_params_from_message(state.get("message", ""), state.get("filters") or {})


def _adzuna_import_params_from_history(history: list[dict[str, Any]]) -> dict[str, Any] | None:
    pattern = re.compile(r"confirm_import_adzuna_jobs country=([^;]+); what=([^;]*); where=([^;]*); count=(\d+)")
    for item in reversed(history[-6:]):
        content = item.get("content")
        if not isinstance(content, str):
            continue
        match = pattern.search(content)
        if match:
            country, what, where, count = match.groups()
            return {
                "country": country.strip() or "gb",
                "what": what.strip() or None,
                "where": where.strip() or None,
                "count": _bounded_count(count),
            }
    return None


def _adzuna_import_params_from_message(message: str, filters: dict[str, Any]) -> dict[str, Any]:
    normalized = message.strip()
    country = _regex_group(r"\b(?:country|in country)\s+([a-z]{2})\b", normalized, default="gb").lower()
    count = _bounded_count(_regex_group(r"\b(\d{1,3})\s+(?:(?:fresh|real|adzuna)\s+)*(?:jobs?|roles?)\b", normalized, default="25"))
    where = _regex_group(r"\b(?:in|near|around)\s+([A-Za-z][A-Za-z\s,.-]{1,40})(?:\s+(?:for|from|on)\b|$)", normalized)
    if where is None:
        location_filter = filters.get("location")
        where = location_filter if isinstance(location_filter, str) and location_filter.strip() else None

    quoted = re.search(r'"([^"]+)"|\'([^\']+)\'', normalized)
    if quoted:
        what = (quoted.group(1) or quoted.group(2)).strip()
    else:
        what = _regex_group(r"\bfor\s+(.+?)(?:\s+(?:in|near|around)\b|$)", normalized)
    if what:
        what = re.sub(r"\b(?:adzuna|real|fresh|jobs?|roles?|fetch|import|ingest|find|search|index|please)\b", " ", what, flags=re.IGNORECASE)
        what = re.sub(r"\s+", " ", what).strip(" ,.-") or None

    return {"country": country, "what": what, "where": where, "count": count}


def _format_adzuna_query(params: dict[str, Any]) -> str:
    what = params.get("what") or "jobs"
    where = params.get("where")
    country = params.get("country") or "gb"
    if where:
        return f'"{what}" in {where} ({country})'
    return f'"{what}" ({country})'


def _regex_group(pattern: str, text: str, *, default: str | None = None) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return default
    value = match.group(1).strip()
    return value or default


def _bounded_count(value: object) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = 25
    return max(1, min(count, 25))


def _record_adzuna_run(
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
            "provider": "adzuna",
            "query": {
                "country": params["country"],
                "what": params.get("what"),
                "where": params.get("where"),
                "count": params["count"],
                "index": True,
                "results_per_page": 50,
            },
            "requested_count": params["count"],
            "created_count": created,
            "skipped_count": skipped,
            "indexed_count": indexed,
            "status": status,
            "error": error,
        }
    )


def _mock_fixture_path() -> Path:
    return Path(__file__).resolve().parents[2] / "fixtures" / "mock_jobs.json"
