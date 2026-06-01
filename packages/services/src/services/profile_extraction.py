from __future__ import annotations

import json
from typing import Any, Protocol

from providers.openai_auth import OpenAIAuthProvider
from providers.types import GenerateRequest, ProviderMessage


class ProfileExtractionError(ValueError):
    pass


class ProfileExtractionProvider(Protocol):
    def generate(self, request: GenerateRequest):
        ...


def extract_profile_fields(
    cv_text: str,
    *,
    provider: ProfileExtractionProvider | None = None,
    model: str = "gpt-5.5",
) -> dict[str, Any]:
    extraction_provider = provider or OpenAIAuthProvider()
    try:
        response = extraction_provider.generate(
            GenerateRequest(
                model=model,
                messages=[ProviderMessage(role="user", content=_profile_extraction_prompt(cv_text))],
                instructions="Return strict JSON only. Do not include markdown fences or prose outside JSON.",
            )
        )
    except Exception as exc:
        raise ProfileExtractionError("Profile extraction requires OpenAI OAuth login and a working model") from exc
    return _parse_profile_fields(response.text)


def _profile_extraction_prompt(cv_text: str) -> str:
    return (
        "Extract structured candidate profile fields from this CV text. "
        "Use only evidence present in the CV. Return strict JSON with exactly these keys: "
        "target_roles, target_locations, skills, seniority, preferred_contract_types, remote_preference. "
        "target_roles, target_locations, skills, and preferred_contract_types must be arrays of strings. "
        "seniority must be one of student, junior, mid-level, senior, lead, or null. "
        "preferred_contract_types values must be internship, full-time, or contract when inferable. "
        "remote_preference must be remote, hybrid, onsite, or null. "
        "If a field is not supported by the CV text, return an empty array or null.\n\n"
        f"CV text:\n{cv_text}"
    )


def _parse_profile_fields(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProfileExtractionError("Model returned invalid profile extraction JSON") from exc
    if not isinstance(data, dict):
        raise ProfileExtractionError("Model profile extraction JSON must be an object")

    return {
        "target_roles": _string_list(data.get("target_roles"), limit=10),
        "target_locations": _string_list(data.get("target_locations"), limit=10),
        "skills": _string_list(data.get("skills"), limit=30),
        "seniority": _seniority(data.get("seniority")),
        "preferred_contract_types": _contract_types(data.get("preferred_contract_types")),
        "remote_preference": _remote_preference(data.get("remote_preference")),
    }


def _string_list(value: object, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        normalized = item.strip()
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        items.append(normalized)
        seen.add(key)
        if len(items) >= limit:
            break
    return items


def _seniority(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    aliases = {
        "student": "student",
        "intern": "student",
        "internship": "student",
        "junior": "junior",
        "entry-level": "junior",
        "entry level": "junior",
        "mid": "mid-level",
        "middle": "mid-level",
        "mid-level": "mid-level",
        "senior": "senior",
        "lead": "lead",
        "principal": "lead",
    }
    return aliases.get(normalized)


def _contract_types(value: object) -> list[str]:
    aliases = {
        "internship": "internship",
        "intern": "internship",
        "full-time": "full-time",
        "full time": "full-time",
        "permanent": "full-time",
        "contract": "contract",
        "freelance": "contract",
    }
    result: list[str] = []
    for item in _string_list(value, limit=5):
        normalized = aliases.get(item.lower())
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _remote_preference(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in {"remote", "hybrid", "onsite"}:
        return normalized
    if normalized in {"on-site", "on site"}:
        return "onsite"
    return None
