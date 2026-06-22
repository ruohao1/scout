from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Any, Literal, Protocol

from providers.errors import ProviderHTTPError
from providers.openai_auth import OpenAIAuthProvider
from providers.types import GenerateRequest, ProviderMessage
from rag.types import JobSearchFilters

from .chat import classify_chat_intent


ChatRouteName = Literal["corpus_status", "job_import", "job_search", "job_rank", "general_chat"]
JobImportProvider = Literal["adzuna"]


@dataclass(frozen=True)
class ChatRoute:
    route: ChatRouteName
    intent: str
    query: str | None = None
    filters: dict[str, Any] | None = None
    limit: int | None = None
    wants_live: bool = False
    import_provider: JobImportProvider | None = None
    needs_confirmation: bool = False
    confidence: float = 0.0
    reason: str = ""
    used_fallback: bool = False
    warning: str | None = None


class ChatRouterProvider(Protocol):
    def generate(self, request: GenerateRequest):
        ...


def route_chat_request(
    *,
    message: str,
    history: list[dict[str, Any]] | None = None,
    target_profile_id: str | None = None,
    profile_id: str | None = None,
    filters: JobSearchFilters | None = None,
    limit: int = 5,
    model: str = "gpt-5.5",
    provider: ChatRouterProvider | None = None,
) -> ChatRoute:
    message = _strip_system_reminders(message)
    history = _strip_history_system_reminders(history or [])
    router = provider or OpenAIAuthProvider()
    try:
        response = router.generate(
            GenerateRequest(
                model=model,
                messages=_messages(
                    message=message,
                    history=history,
                    target_profile_id=target_profile_id or profile_id,
                    filters=filters or JobSearchFilters(),
                    limit=limit,
                ),
                instructions=_INSTRUCTIONS,
            )
        )
        return _route_from_ai_response(response.text, fallback_limit=limit)
    except (ProviderHTTPError, Exception) as exc:
        fallback = route_chat_request_fallback(
            message=message,
            history=history,
            target_profile_id=target_profile_id,
            profile_id=profile_id,
            filters=filters,
            limit=limit,
        )
        return ChatRoute(**{**asdict(fallback), "warning": f"AI router unavailable; used local router: {exc}"})


def route_chat_request_fallback(
    *,
    message: str,
    history: list[dict[str, Any]] | None = None,
    target_profile_id: str | None = None,
    profile_id: str | None = None,
    filters: JobSearchFilters | None = None,
    limit: int = 5,
) -> ChatRoute:
    del history, target_profile_id, profile_id, filters
    text = _strip_system_reminders(message).strip()
    normalized = _normalized_text(text)
    if _is_corpus_status_request(normalized):
        return ChatRoute(route="corpus_status", intent="corpus_status", limit=limit, confidence=1.0, reason="User asked about indexed job corpus status.", used_fallback=True)
    if _is_adzuna_import_request(normalized):
        return ChatRoute(route="job_import", intent="import_adzuna_jobs", import_provider="adzuna", needs_confirmation=True, query=_clean_search_query(text), limit=_requested_limit(text, fallback=limit), confidence=1.0, reason="User asked for Adzuna import.", used_fallback=True)
    if _is_confirmation(normalized):
        return ChatRoute(route="job_import", intent="confirm_import", needs_confirmation=False, limit=limit, confidence=0.8, reason="User confirmed the previous import prompt.", used_fallback=True)
    if _looks_like_profile_match(normalized) or classify_chat_intent(text) == "rank":
        return ChatRoute(route="job_rank", intent="rank_jobs", query=_clean_search_query(text), limit=_requested_limit(text, fallback=limit), confidence=0.9, reason="User asked to match jobs against the selected target profile.", used_fallback=True)
    if classify_chat_intent(text) in {"search", "vague_search"} or _looks_like_job_search(normalized):
        return ChatRoute(route="job_search", intent="search_jobs", query=_clean_search_query(text), limit=_requested_limit(text, fallback=limit), wants_live=_wants_live_jobs(normalized), confidence=0.85, reason="User asked to search jobs.", used_fallback=True)
    return ChatRoute(route="general_chat", intent="chat", limit=limit, confidence=0.7, reason="No job workflow action was clearly requested.", used_fallback=True)


def _route_from_ai_response(text: str, *, fallback_limit: int) -> ChatRoute:
    payload = _json_object(text)
    if payload is None:
        return ChatRoute(route="general_chat", intent="chat", limit=fallback_limit, confidence=0.0, reason="AI router returned non-JSON output.", used_fallback=True, warning="AI router returned non-JSON output.")
    route = payload.get("route") if payload.get("route") in _ROUTES else "general_chat"
    filters = payload.get("filters") if isinstance(payload.get("filters"), dict) else None
    return ChatRoute(
        route=route,
        intent=_string(payload.get("intent")) or route,
        query=_string(payload.get("query")),
        filters=filters,
        limit=_limit(payload.get("limit"), fallback=fallback_limit),
        wants_live=bool(payload.get("wants_live")),
        import_provider=payload.get("import_provider") if payload.get("import_provider") == "adzuna" else None,
        needs_confirmation=bool(payload.get("needs_confirmation")),
        confidence=_confidence(payload.get("confidence")),
        reason=_string(payload.get("reason")) or "AI router selected this route.",
    )


def _messages(*, message: str, history: list[dict[str, Any]], target_profile_id: str | None, filters: JobSearchFilters, limit: int) -> list[ProviderMessage]:
    context = {"selected_target_profile_id": target_profile_id, "filters": asdict(filters), "limit": limit}
    messages = [ProviderMessage(role="developer", content=f"Current Scout routing context: {json.dumps(context)}")]
    for item in history[-8:]:
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            messages.append(ProviderMessage(role=role, content=_strip_system_reminders(content)))
    messages.append(ProviderMessage(role="user", content=message))
    return messages


def _json_object(text: str) -> dict[str, Any] | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _clean_search_query(text: str) -> str | None:
    text = _strip_system_reminders(text)
    query = re.sub(r"\b(fetch|find|search|show|get|list|jobs?|roles?|offers?)\b", " ", text, flags=re.IGNORECASE)
    query = re.sub(r"\s+", " ", query).strip()
    return query or None


def _requested_limit(text: str, *, fallback: int) -> int:
    match = re.search(r"\b(?:find|get|show|list|top|limit|return|give(?:\s+me)?)\s+(?:me\s+)?(?:the\s+)?(?:top\s+)?(\d{1,2})\b", text, flags=re.IGNORECASE)
    if not match:
        return fallback
    return max(1, min(int(match.group(1)), 50))


def _is_corpus_status_request(normalized: str) -> bool:
    return any(phrase in normalized for phrase in ("corpus status", "indexed jobs", "how many jobs", "job count"))


def _is_adzuna_import_request(normalized: str) -> bool:
    return "adzuna" in normalized and any(word in normalized for word in ("fetch", "import", "ingest", "find", "search", "index"))


def _is_confirmation(normalized: str) -> bool:
    return normalized in {"yes", "y", "ok", "okay", "proceed", "go ahead", "confirm", "do it"}


def _looks_like_job_search(normalized: str) -> bool:
    words = set(normalized.split())
    return bool(words & {"cherche", "chercher", "find", "get", "list", "montre", "search", "show", "trouve", "trouver"}) and bool(words & {"backend", "cybersecurity", "data", "developer", "engineer", "frontend", "intern", "internship", "manager", "product", "python", "software", "react", "stage", "stages"})


def _looks_like_profile_match(normalized: str) -> bool:
    return any(phrase in normalized for phrase in ("match my profile", "matches my profile", "matching my profile", "jobs for my profile", "roles for my profile", "offers for my profile"))


def _wants_live_jobs(normalized: str) -> bool:
    return any(word in normalized.split() for word in ("fresh", "live", "current", "new", "latest", "online"))


def _normalized_text(text: str) -> str:
    text = _strip_system_reminders(text)
    normalized = re.sub(r"[^\w\s-]", " ", text.lower())
    normalized = re.sub(r"\b(cyberecurity|cybersecuirty|cyber security)\b", "cybersecurity", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _strip_history_system_reminders(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stripped: list[dict[str, Any]] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if isinstance(content, str):
            stripped.append({**item, "content": _strip_system_reminders(content)})
        else:
            stripped.append(item)
    return stripped


def _strip_system_reminders(text: str) -> str:
    return re.sub(r"<system-reminder>.*?</system-reminder>", " ", text, flags=re.IGNORECASE | re.DOTALL)


def _string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _limit(value: object, *, fallback: int) -> int:
    if isinstance(value, int):
        return max(1, min(value, 50))
    return fallback


def _confidence(value: object) -> float:
    if isinstance(value, int | float):
        return max(0.0, min(float(value), 1.0))
    return 0.0


_ROUTES = {"corpus_status", "job_import", "job_search", "job_rank", "general_chat"}

_INSTRUCTIONS = """
You are Scout's routing agent. Interpret the user's latest message and choose exactly one workflow route.

Return only one JSON object with these fields:
- route: one of corpus_status, job_import, job_search, job_rank, general_chat
- intent: short action label
- query: cleaned search phrase or null
- filters: object with optional location, contract_type, company, seniority, remote_policy
- limit: requested result count, or the provided default; do not treat technology versions as limits
- wants_live: true only when user asks for fresh/live/current/new/latest/online jobs
- import_provider: adzuna or null
- needs_confirmation: true for imports that should ask before running
- confidence: 0.0 to 1.0
- reason: one short sentence

Routing rules:
- Use job_search for requests to find/search/list jobs or roles.
- Use job_rank for requests to match/rank jobs against the selected target profile.
- Use job_import for explicit import/seed/index requests, not ordinary fresh JobSpy searches.
- Use corpus_status for job counts, indexed job counts, or corpus status.
- Use general_chat for greetings, help, and non-job conversation.
- Preserve version terms in query, e.g. "Python 3 developer" or "React 18".
- Parse limits only from explicit result-count language like "find me 3", "show 10", "top 20".
- For internships/stages/traineeships, set filters.contract_type="internship" and filters.seniority="student".
- Do not set filters.seniority="internship"; internship is a contract type, not a seniority.
""".strip()
