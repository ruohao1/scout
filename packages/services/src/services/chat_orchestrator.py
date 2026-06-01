from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Protocol

from db.profiles import ProfileRepository
from providers.openai_auth import OpenAIAuthProvider
from providers.types import GenerateRequest, ProviderMessage
from rag.types import JobSearchFilters

from .chat import ChatResult, respond_to_chat
from .job_ranking import ProfileNotFoundError, rank_jobs_for_profile
from .job_search import EmptySearchQueryError, search_jobs


class ChatPlanningProvider(Protocol):
    def generate(self, request: GenerateRequest):
        ...


def respond_to_chat_with_tools(
    *,
    message: str,
    history: list[dict[str, Any]] | None = None,
    profile_id: str | None = None,
    filters: JobSearchFilters | None = None,
    limit: int = 5,
    model: str = "gpt-5.5",
    provider: ChatPlanningProvider | None = None,
) -> ChatResult:
    planner = provider or OpenAIAuthProvider()
    active_filters = filters or JobSearchFilters()
    try:
        first_response = planner.generate(
            GenerateRequest(
                model=model,
                messages=_messages(message=message, history=history, profile_id=profile_id, filters=active_filters, limit=limit),
                instructions=_INSTRUCTIONS,
                tools=_TOOLS,
            )
        )
        tool_call = _first_tool_call(first_response.tool_calls)
        if tool_call is None:
            return ChatResult(message=first_response.text or "What would you like to do next?", tool="none")

        tool_name, tool_args = _tool_name(tool_call), _tool_arguments(tool_call)
        tool_result = _execute_tool(tool_name, tool_args, profile_id=profile_id, filters=active_filters, limit=limit)
        final_response = planner.generate(
            GenerateRequest(
                model=model,
                messages=_messages(message=message, history=history, profile_id=profile_id, filters=active_filters, limit=limit),
                instructions=_INSTRUCTIONS,
                previous_tool_calls=first_response.tool_calls,
                tool_results=[_tool_result_message(tool_call, tool_result)],
            )
        )
        return _chat_result(tool_name=tool_name, tool_result=tool_result, message=final_response.text)
    except Exception as exc:
        fallback = respond_to_chat(message=message, profile_id=profile_id, filters=active_filters, limit=limit)
        return ChatResult(
            message=fallback.message,
            tool=fallback.tool,
            jobs=fallback.jobs,
            ranked_jobs=fallback.ranked_jobs,
            warnings=["AI workflow planner unavailable; used local keyword router.", *fallback.warnings, str(exc)],
        )


def _messages(
    *,
    message: str,
    history: list[dict[str, Any]] | None,
    profile_id: str | None,
    filters: JobSearchFilters,
    limit: int,
) -> list[ProviderMessage]:
    context = {
        "selected_profile_id": profile_id,
        "filters": asdict(filters),
        "limit": limit,
    }
    messages: list[ProviderMessage] = [ProviderMessage(role="system", content=f"Current Scout context: {json.dumps(context)}")]
    for item in (history or [])[-8:]:
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            messages.append(ProviderMessage(role=role, content=content))
    messages.append(ProviderMessage(role="user", content=message))
    return messages


def _first_tool_call(tool_calls: list[dict[str, Any]]) -> dict[str, Any] | None:
    return tool_calls[0] if tool_calls else None


def _tool_name(tool_call: dict[str, Any]) -> str:
    name = tool_call.get("name") or tool_call.get("function", {}).get("name")
    return name if isinstance(name, str) else ""


def _tool_arguments(tool_call: dict[str, Any]) -> dict[str, Any]:
    raw_args = tool_call.get("arguments") or tool_call.get("function", {}).get("arguments") or "{}"
    if isinstance(raw_args, dict):
        return raw_args
    if not isinstance(raw_args, str):
        return {}
    try:
        args = json.loads(raw_args)
    except json.JSONDecodeError:
        return {}
    return args if isinstance(args, dict) else {}


def _execute_tool(
    tool_name: str,
    args: dict[str, Any],
    *,
    profile_id: str | None,
    filters: JobSearchFilters,
    limit: int,
) -> dict[str, Any]:
    if tool_name == "search_jobs":
        return _search_tool(args, filters=filters, limit=limit)
    if tool_name == "rank_jobs_for_profile":
        return _rank_tool(args, profile_id=profile_id, filters=filters, limit=limit)
    if tool_name == "list_profiles":
        return _list_profiles_tool(args)
    if tool_name == "get_profile":
        return _get_profile_tool(args, profile_id=profile_id)
    return {"ok": False, "error": f"Unsupported tool: {tool_name}"}


def _search_tool(args: dict[str, Any], *, filters: JobSearchFilters, limit: int) -> dict[str, Any]:
    query = _string_arg(args.get("query")) or "jobs"
    tool_filters = _filters(args.get("filters"), fallback=filters)
    tool_limit = _limit(args.get("limit"), fallback=limit)
    try:
        jobs = search_jobs(query, filters=tool_filters, limit=tool_limit)
    except EmptySearchQueryError as exc:
        return {"ok": False, "tool": "search_jobs", "error": str(exc), "jobs": []}
    return {"ok": True, "tool": "search_jobs", "jobs": [asdict(job) for job in jobs]}


def _rank_tool(args: dict[str, Any], *, profile_id: str | None, filters: JobSearchFilters, limit: int) -> dict[str, Any]:
    selected_profile_id = _string_arg(args.get("profile_id")) or profile_id
    if not selected_profile_id:
        return {"ok": False, "tool": "rank_jobs_for_profile", "error": "profile_id is required", "ranked_jobs": []}
    try:
        ranked = rank_jobs_for_profile(
            selected_profile_id,
            filters=_filters(args.get("filters"), fallback=filters),
            limit=_limit(args.get("limit"), fallback=limit),
        )
    except ProfileNotFoundError as exc:
        return {"ok": False, "tool": "rank_jobs_for_profile", "error": str(exc), "ranked_jobs": []}
    return {"ok": True, "tool": "rank_jobs_for_profile", "ranked_jobs": [asdict(job) for job in ranked]}


def _list_profiles_tool(args: dict[str, Any]) -> dict[str, Any]:
    profiles = ProfileRepository().list(limit=_limit(args.get("limit"), fallback=10))
    return {"ok": True, "tool": "list_profiles", "profiles": profiles}


def _get_profile_tool(args: dict[str, Any], *, profile_id: str | None) -> dict[str, Any]:
    selected_profile_id = _string_arg(args.get("profile_id")) or profile_id
    if not selected_profile_id:
        return {"ok": False, "tool": "get_profile", "error": "profile_id is required", "profile": None}
    profile = ProfileRepository().get(selected_profile_id)
    return {"ok": profile is not None, "tool": "get_profile", "profile": profile, "error": None if profile else "Profile not found"}


def _chat_result(*, tool_name: str, tool_result: dict[str, Any], message: str) -> ChatResult:
    jobs = tool_result.get("jobs") if tool_name == "search_jobs" else []
    ranked_jobs = tool_result.get("ranked_jobs") if tool_name == "rank_jobs_for_profile" else []
    warnings = [] if tool_result.get("ok") else [str(tool_result.get("error") or "Tool failed")]
    count = len(jobs or ranked_jobs or tool_result.get("profiles") or [])
    fallback_message = f"I ran {tool_name} and found {count} result{'s' if count != 1 else ''}."
    return ChatResult(
        message=message.strip() or fallback_message,
        tool=tool_name if tool_name in {"search_jobs", "rank_jobs_for_profile", "list_profiles", "get_profile"} else "none",
        jobs=jobs or [],
        ranked_jobs=ranked_jobs or [],
        warnings=warnings,
    )


def _tool_result_message(tool_call: dict[str, Any], tool_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function_call_output",
        "call_id": tool_call.get("call_id") or tool_call.get("id") or _tool_name(tool_call),
        "output": json.dumps(tool_result, default=str),
    }


def _filters(value: object, *, fallback: JobSearchFilters) -> JobSearchFilters:
    if not isinstance(value, dict):
        return fallback
    return JobSearchFilters(
        location=_string_arg(value.get("location")) or fallback.location,
        contract_type=_string_arg(value.get("contract_type")) or fallback.contract_type,
        company=_string_arg(value.get("company")) or fallback.company,
        seniority=_string_arg(value.get("seniority")) or fallback.seniority,
        remote_policy=_string_arg(value.get("remote_policy")) or fallback.remote_policy,
    )


def _limit(value: object, *, fallback: int) -> int:
    if isinstance(value, int):
        return max(1, min(value, 50))
    return fallback


def _string_arg(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


_INSTRUCTIONS = """
You are Scout, a job-matching workflow assistant.
Use tools for profile lookup, semantic job search, and deterministic job ranking.
Do not invent jobs, profiles, scores, database state, or CV facts.
If a profile is required but missing, use list_profiles or ask for a profile.
If tools return no results, explain the missing prerequisite and suggest a next action.
Keep answers concise and actionable.
""".strip()

_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "search_jobs",
        "description": "Search indexed jobs semantically.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "filters": {"type": "object"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": ["query"],
        },
    },
    {
        "type": "function",
        "name": "rank_jobs_for_profile",
        "description": "Rank indexed jobs against a candidate profile using deterministic scoring.",
        "parameters": {
            "type": "object",
            "properties": {
                "profile_id": {"type": "string"},
                "filters": {"type": "object"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
        },
    },
    {
        "type": "function",
        "name": "list_profiles",
        "description": "List candidate profiles available for matching.",
        "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}}},
    },
    {
        "type": "function",
        "name": "get_profile",
        "description": "Get one candidate profile by id.",
        "parameters": {"type": "object", "properties": {"profile_id": {"type": "string"}}},
    },
]
