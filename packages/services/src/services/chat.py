from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from rag.types import JobSearchFilters

from .job_ranking import TargetProfileNotFoundError, rank_jobs_for_target_profile
from .job_search import EmptySearchQueryError, search_jobs


NO_TOOL_INTENTS = {"chat", "help", "vague_search"}


@dataclass(frozen=True)
class ChatResult:
    message: str
    tool: str
    jobs: list[dict] = field(default_factory=list)
    ranked_jobs: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    artifacts: list[dict] = field(default_factory=list)


def respond_to_chat(
    *,
    message: str,
    target_profile_id: str | None = None,
    profile_id: str | None = None,
    filters: JobSearchFilters | None = None,
    limit: int = 5,
) -> ChatResult:
    text = message.strip()
    if not text:
        return ChatResult(
            message=empty_message(),
            tool="none",
            warnings=["Message must not be empty."],
        )
    intent = classify_chat_intent(text)
    if intent in NO_TOOL_INTENTS:
        return ChatResult(message=no_tool_message(intent), tool="none")

    merged_filters = _merge_filters(text, filters or JobSearchFilters())
    if intent == "rank":
        selected_target_profile_id = target_profile_id or profile_id
        if not selected_target_profile_id:
            return ChatResult(
                message=missing_target_profile_message(),
                tool="rank_jobs_for_profile",
                warnings=["target_profile_id is required for matching."],
            )
        try:
            ranked = rank_jobs_for_target_profile(selected_target_profile_id, filters=merged_filters, limit=limit)
        except TargetProfileNotFoundError:
            return ChatResult(
                message=target_profile_not_found_message(),
                tool="rank_jobs_for_profile",
                warnings=["Target profile not found."],
            )
        except Exception as exc:
            return ChatResult(
                message=ranking_unavailable_message(),
                tool="rank_jobs_for_profile",
                warnings=[f"Ranking failed: {exc}"],
            )
        if not ranked:
            return ChatResult(
                message=no_ranked_jobs_message(),
                tool="rank_jobs_for_profile",
                ranked_jobs=[],
                warnings=["No ranked jobs found."],
            )
        return ChatResult(
            message=rank_success_message(len(ranked)),
            tool="rank_jobs_for_profile",
            ranked_jobs=[asdict(job) for job in ranked],
        )

    if intent != "search":
        return ChatResult(message=no_tool_message("chat"), tool="none")

    query = _search_query(text)
    try:
        jobs = search_jobs(query, filters=merged_filters, limit=limit)
    except EmptySearchQueryError:
        return ChatResult(
            message=vague_search_message(),
            tool="search_jobs",
            warnings=["Search query must not be empty."],
        )
    except Exception as exc:
        return ChatResult(
            message=search_unavailable_message(),
            tool="search_jobs",
            warnings=[f"Search failed: {exc}"],
        )
    if not jobs:
        return ChatResult(
            message=no_search_results_message(),
            tool="search_jobs",
            jobs=[],
            warnings=["No jobs found."],
        )
    return ChatResult(
        message=search_success_message(len(jobs)),
        tool="search_jobs",
        jobs=[asdict(job) for job in jobs],
    )


def classify_chat_intent(text: str) -> str:
    if _is_greeting(text) or _is_small_talk(text):
        return "chat"
    if _is_help_request(text):
        return "help"
    if _is_match_intent(text):
        return "rank"
    if _is_search_intent(text):
        return "search" if _has_search_details(text) else "vague_search"
    return "chat"


def no_tool_message(intent: str) -> str:
    if intent == "help":
        return help_message()
    if intent == "vague_search":
        return vague_search_message()
    return auth_unavailable_message()


def empty_message() -> str:
    return """Tell me what you want to do with jobs.

Try one of these:

- **Search:** `Find remote backend jobs`
- **Rank:** `Rank jobs for my profile`
- **Profiles:** `List candidate profiles`
- **Corpus:** `How many jobs are indexed?`
""".strip()


def help_message() -> str:
    return """I can help with job search and matching.

Useful prompts:

- **Search jobs:** `Find remote backend jobs`
- **Rank matches:** `Rank jobs for my profile`
- **Profiles:** `List candidate profiles`
- **Corpus:** `How many jobs are indexed?`
""".strip()


def auth_unavailable_message() -> str:
    return """AI chat is not configured yet, but local job tools can still run for clear search or ranking requests.

To enable fuller chat:

- Run `uv run python main.py auth openai login --no-browser`
- Then try your question again
""".strip()


def missing_target_profile_message() -> str:
    return """Select or create a target profile before ranking jobs.

Next steps:

- Open **Target profiles** and select or create a target profile
- Then ask: `Rank jobs for my target profile`
""".strip()


def target_profile_not_found_message() -> str:
    return """I could not find the selected target profile.

Try this:

- Refresh **Target profiles**
- Select an existing target profile
- Run ranking again
""".strip()


def ranking_unavailable_message() -> str:
    return """Ranking is not ready yet.

Check these prerequisites:

- Database is running
- Jobs are imported and indexed
- Embedding provider configuration matches the index
""".strip()


def no_ranked_jobs_message() -> str:
    return """I did not find ranked matches for that target profile.

Next step:

- Import and index jobs, then rerun ranking
""".strip()


def rank_success_message(count: int) -> str:
    return f"""Ranked **{count} jobs** against your selected target profile.

The strongest matches are shown below with skill overlap, location fit, and evidence where available.
""".strip()


def vague_search_message() -> str:
    return """Tell me what kind of role to search for.

Examples:

- `Find Python developer jobs in London`
- `Show remote backend roles`
- `Search senior product manager jobs in Berlin`
""".strip()


def search_unavailable_message() -> str:
    return """Search is not ready yet.

Check these prerequisites:

- Database is running
- Jobs are imported
- Jobs are indexed with the configured embedding provider
""".strip()


def no_search_results_message() -> str:
    return """I did not find matching indexed jobs.

Try one of these:

- Broaden the role or skill keywords
- Remove location or contract filters
- Import and index more jobs
""".strip()


def search_success_message(count: int) -> str:
    return f"""Found **{count} matching jobs**.

The strongest matches are shown below. You can narrow the search with a location, contract type, seniority, or company.
""".strip()


def _is_match_intent(text: str) -> bool:
    normalized = text.lower()
    return any(phrase in normalized for phrase in ("match me", "rank", "best for me", "fit for me", "for my profile"))


def _is_greeting(text: str) -> bool:
    normalized = _normalized_text(text)
    greetings = {"hello", "hi", "hey", "hiya", "yo", "good morning", "good afternoon", "good evening", "salut", "bonjour", "bonsoir", "coucou"}
    return normalized in greetings or any(normalized == f"{greeting} scout" for greeting in greetings)


def _is_small_talk(text: str) -> bool:
    normalized = _normalized_text(text)
    return normalized in {"thanks", "thank you", "ok", "okay", "cool", "nice", "great", "bye", "goodbye"}


def _is_help_request(text: str) -> bool:
    normalized = _normalized_text(text)
    return any(
        phrase in normalized
        for phrase in (
            "what can you do",
            "help",
            "capabilities",
            "how does this work",
            "how can you help",
            "what do you do",
        )
    )


def _is_search_intent(text: str) -> bool:
    normalized = _normalized_text(text)
    return any(word in normalized.split() for word in ("find", "search", "show", "get", "list")) and any(
        word in normalized.split() for word in ("job", "jobs", "role", "roles", "offer", "offers")
    )


def _has_search_details(text: str) -> bool:
    normalized = _normalized_text(text)
    generic = {
        "find",
        "search",
        "show",
        "get",
        "list",
        "for",
        "a",
        "an",
        "the",
        "job",
        "jobs",
        "role",
        "roles",
        "offer",
        "offers",
        "work",
        "opportunity",
        "opportunities",
    }
    terms = [term for term in normalized.split() if term not in generic]
    return bool(terms) or any(value is not None for value in (_first_location(text.lower()), _first_contract_type(text.lower()), _first_seniority(text.lower()), _first_remote_policy(text.lower())))


def _normalized_text(text: str) -> str:
    normalized = re.sub(r"[^\w\s-]", " ", text.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def _search_query(text: str) -> str:
    query = re.sub(r"\b(find|search|show|get|list|jobs?|roles?|offers?)\b", " ", text, flags=re.IGNORECASE)
    query = re.sub(r"\s+", " ", query).strip()
    return query or text


def _merge_filters(text: str, filters: JobSearchFilters) -> JobSearchFilters:
    normalized = text.lower()
    return JobSearchFilters(
        location=filters.location or _first_location(normalized),
        contract_type=filters.contract_type or _first_contract_type(normalized),
        company=filters.company,
        seniority=filters.seniority or _first_seniority(normalized),
        remote_policy=filters.remote_policy or _first_remote_policy(normalized),
        source=filters.source,
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
