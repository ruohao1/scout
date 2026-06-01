from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph
from rag.types import JobSearchFilters

from .chat import ChatResult
from .chat_orchestrator import ChatPlanningProvider, respond_to_chat_with_tools
from .job_corpus import get_job_corpus_status
from .job_providers import MockJobProviderAdapter, MockJobProviderClient, import_jobs


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


def respond_to_chat_with_graph(
    *,
    message: str,
    history: list[dict[str, Any]] | None = None,
    profile_id: str | None = None,
    filters: JobSearchFilters | None = None,
    limit: int = 5,
    model: str = "gpt-5.5",
    provider: ChatPlanningProvider | None = None,
    graph: CompiledWorkflow | None = None,
) -> ChatResult:
    workflow = graph or build_job_workflow_graph(provider=provider)
    state = workflow.invoke(
        {
            "message": message,
            "history": history or [],
            "profile_id": profile_id,
            "filters": asdict(filters or JobSearchFilters()),
            "limit": limit,
            "model": model,
        }
    )
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
        try:
            return {"corpus_status": asdict(get_job_corpus_status())}
        except Exception as exc:
            return {"corpus_status": {"total_jobs": 0, "indexed_jobs": 0, "unindexed_jobs": 0, "source": None, "error": str(exc)}}

    def route_after_status(state: JobWorkflowState) -> str:
        message = state.get("message", "")
        if _is_corpus_status_request(message):
            return "corpus_status_response"
        if _is_mock_import_request(message) or (_is_confirmation(message) and _history_requested_mock_import(state.get("history") or [])):
            return "import_mock_jobs" if _is_confirmation(message) else "request_mock_import_confirmation"
        return "plan_and_run"

    def corpus_status_response(state: JobWorkflowState) -> dict[str, Any]:
        status = state.get("corpus_status") or {}
        message = (
            f"Scout has {status.get('total_jobs', 0)} jobs, "
            f"{status.get('indexed_jobs', 0)} indexed jobs, and "
            f"{status.get('unindexed_jobs', 0)} unindexed jobs."
        )
        warnings = [str(status["error"])] if status.get("error") else []
        return {"result": {"message": message, "tool": "get_job_corpus_status", "jobs": [], "ranked_jobs": [], "warnings": warnings}}

    def request_mock_import_confirmation(state: JobWorkflowState) -> dict[str, Any]:
        status = state.get("corpus_status") or {}
        message = (
            "I can import and index 10 mock jobs so Scout has a searchable local corpus. "
            f"Current corpus: {status.get('total_jobs', 0)} jobs, {status.get('indexed_jobs', 0)} indexed. "
            "Reply yes to proceed."
        )
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
        try:
            result = import_jobs(
                client=MockJobProviderClient(fixture_path=_mock_fixture_path()),
                adapter=MockJobProviderAdapter(),
                count=10,
                should_index=True,
            )
        except Exception as exc:
            return {
                "result": {
                    "message": "I could not import and index mock jobs. Check the database and embedding provider configuration.",
                    "tool": "import_mock_jobs",
                    "jobs": [],
                    "ranked_jobs": [],
                    "warnings": [str(exc)],
                }
            }
        message = f"Imported {len(result.created)} mock jobs, skipped {result.skipped} duplicates, and indexed {result.indexed} jobs."
        return {"result": {"message": message, "tool": "import_mock_jobs", "jobs": [], "ranked_jobs": [], "warnings": []}}

    def plan_and_run(state: JobWorkflowState) -> dict[str, Any]:
        result = respond_to_chat_with_tools(
            message=state.get("message", ""),
            history=state.get("history") or [],
            profile_id=state.get("profile_id"),
            filters=JobSearchFilters(**(state.get("filters") or {})),
            limit=int(state.get("limit") or 5),
            model=state.get("model") or "gpt-5.5",
            provider=provider,
        )
        return {"result": asdict(result)}

    builder.add_node("check_corpus", check_corpus)
    builder.add_node("corpus_status_response", corpus_status_response)
    builder.add_node("request_mock_import_confirmation", request_mock_import_confirmation)
    builder.add_node("import_mock_jobs", import_mock_jobs_node)
    builder.add_node("plan_and_run", plan_and_run)
    builder.add_edge(START, "check_corpus")
    builder.add_conditional_edges(
        "check_corpus",
        route_after_status,
        {
            "corpus_status_response": "corpus_status_response",
            "request_mock_import_confirmation": "request_mock_import_confirmation",
            "import_mock_jobs": "import_mock_jobs",
            "plan_and_run": "plan_and_run",
        },
    )
    builder.add_edge("corpus_status_response", END)
    builder.add_edge("request_mock_import_confirmation", END)
    builder.add_edge("import_mock_jobs", END)
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


def _is_corpus_status_request(message: str) -> bool:
    normalized = message.lower()
    return any(phrase in normalized for phrase in ("corpus status", "indexed jobs", "how many jobs", "job count"))


def _is_mock_import_request(message: str) -> bool:
    normalized = message.lower()
    return "mock" in normalized and any(word in normalized for word in ("import", "ingest", "seed", "index"))


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


def _mock_fixture_path() -> Path:
    return Path(__file__).resolve().parents[2] / "fixtures" / "mock_jobs.json"
