from __future__ import annotations

import json
from typing import Any, Protocol

from providers.openai_auth import OpenAIAuthProvider
from providers.types import GenerateRequest, ProviderMessage

MIN_CONFIDENCE = 0.45
MAX_PROFILE_EXTRACTION_CHARS = 60_000
PROFILE_EXTRACTION_TIMEOUT_SECONDS = 30.0


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
    extraction_provider = provider or OpenAIAuthProvider(timeout=PROFILE_EXTRACTION_TIMEOUT_SECONDS)
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


def profile_fields_to_candidate_evidence(
    extracted: dict[str, Any],
    *,
    source_document_id: str | None = None,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []

    for item in extracted.get("experiences") or []:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        evidence.append(
            {
                "type": "experience",
                "title": item["title"],
                "organization": item.get("company"),
                "location": item.get("location"),
                "start_date": item.get("start_date"),
                "end_date": item.get("end_date"),
                "is_current": bool(item.get("is_current")),
                "description": item.get("description"),
                "skills": item.get("skills") or [],
                "source_document_id": source_document_id,
            }
        )

    for item in extracted.get("projects") or []:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        evidence.append(
            {
                "type": "project",
                "title": item["name"],
                "organization": None,
                "url": item.get("url"),
                "description": item.get("description"),
                "skills": item.get("skills") or [],
                "source_document_id": source_document_id,
            }
        )

    for item in extracted.get("enriched_skills") or []:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        category = item.get("category")
        proficiency = item.get("proficiency")
        detail = ", ".join(value for value in [category, proficiency] if value)
        evidence.append(
            {
                "type": "skill",
                "title": item["name"],
                "description": detail or None,
                "metadata": {
                    key: value
                    for key, value in {"category": category, "proficiency": proficiency}.items()
                    if value
                },
                "source_document_id": source_document_id,
            }
        )

    for key, title in [
        ("target_roles", "Target roles"),
        ("target_locations", "Target locations"),
        ("preferred_contract_types", "Preferred contract types"),
    ]:
        values = extracted.get(key) or []
        if values:
            evidence.append(
                {
                    "type": "document_note",
                    "title": title,
                    "description": ", ".join(values),
                    "source_document_id": source_document_id,
                }
            )

    return evidence


def _profile_extraction_prompt(cv_text: str) -> str:
    cv_text = cv_text[:MAX_PROFILE_EXTRACTION_CHARS]
    return (
        "Extract a structured candidate profile from this CV text. Use only evidence present in the CV. "
        "Return strict JSON only with these keys: summary, target_roles, target_locations, skills, "
        "experience, projects, education, certifications, languages, seniority, preferred_contract_types, "
        "remote_preference, warnings.\n"
        "target_roles and target_locations must be arrays of objects with value, confidence, and evidence.\n"
        "skills must be an array of objects with name, category, confidence, and evidence.\n"
        "experience must be an array of objects with title, company, location, start_date, end_date, is_current, description, technologies, confidence, and evidence.\n"
        "projects must be an array of objects with name, role, url, description, technologies, confidence, and evidence.\n"
        "education must be an array of objects with institution, degree, and evidence.\n"
        "certifications must be an array of objects with name and evidence.\n"
        "languages must be an array of objects with name, level, and evidence.\n"
        "seniority and remote_preference must be objects with value, confidence, and evidence, or null.\n"
        "preferred_contract_types must be an array of objects with value, confidence, and evidence.\n"
        "confidence must be a number from 0 to 1. Use lower confidence for weak inferences.\n"
        "seniority value must be student, junior, mid-level, senior, lead, or null.\n"
        "preferred_contract_types values must be internship, full-time, or contract when inferable.\n"
        "remote_preference value must be remote, hybrid, onsite, or null.\n"
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
        "target_roles": _profile_items(data.get("target_roles"), value_key="value", limit=10),
        "target_locations": _profile_items(data.get("target_locations"), value_key="value", limit=10),
        "skills": _profile_items(data.get("skills"), value_key="name", limit=30),
        "seniority": _seniority(_profile_value(data.get("seniority"))),
        "preferred_contract_types": _contract_types(_profile_items(data.get("preferred_contract_types"), value_key="value", limit=5)),
        "remote_preference": _remote_preference(_profile_value(data.get("remote_preference"))),
        "experiences": _experiences(data.get("experience"), limit=12),
        "projects": _projects(data.get("projects"), limit=12),
        "enriched_skills": _skills(data.get("skills"), limit=40),
    }


def _profile_items(value: object, *, value_key: str, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []

    items: list[str] = []
    seen: set[str] = set()
    for item in value:
        candidate = _profile_item_value(item, value_key=value_key)
        if candidate is None:
            continue
        normalized = candidate.strip()
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        items.append(normalized)
        seen.add(key)
        if len(items) >= limit:
            break
    return items


def _profile_item_value(item: object, *, value_key: str) -> str | None:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict) or _confidence(item.get("confidence")) < MIN_CONFIDENCE:
        return None
    value = item.get(value_key)
    return value.strip() if isinstance(value, str) else None


def _profile_value(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict) or _confidence(value.get("confidence")) < MIN_CONFIDENCE:
        return None
    item = value.get("value")
    return item.strip() if isinstance(item, str) else None


def _experiences(value: object, *, limit: int) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or _confidence(item.get("confidence")) < MIN_CONFIDENCE:
            continue
        title = _text(item.get("title"))
        if title is None:
            continue
        company = _text(item.get("company"))
        key = f"{title.lower()}::{(company or '').lower()}"
        if key in seen:
            continue
        result.append(
            {
                "title": title,
                "company": company,
                "location": _text(item.get("location")),
                "start_date": _text(item.get("start_date")),
                "end_date": _text(item.get("end_date")),
                "is_current": bool(item.get("is_current")),
                "description": _text(item.get("description")) or _text(item.get("evidence")),
                "skills": _string_list(item.get("technologies"), limit=12),
            }
        )
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def _projects(value: object, *, limit: int) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or _confidence(item.get("confidence")) < MIN_CONFIDENCE:
            continue
        name = _text(item.get("name"))
        if name is None:
            continue
        key = name.lower()
        if key in seen:
            continue
        result.append(
            {
                "name": name,
                "role": _text(item.get("role")),
                "url": _text(item.get("url")),
                "description": _text(item.get("description")) or _text(item.get("evidence")),
                "skills": _string_list(item.get("technologies"), limit=12),
            }
        )
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def _skills(value: object, *, limit: int) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or _confidence(item.get("confidence")) < MIN_CONFIDENCE:
            continue
        name = _text(item.get("name"))
        if name is None:
            continue
        key = name.lower()
        if key in seen:
            continue
        result.append(
            {
                "name": name,
                "category": _text(item.get("category")),
                "proficiency": _text(item.get("proficiency")),
            }
        )
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _confidence(value: object) -> float:
    if isinstance(value, int | float):
        return max(0.0, min(1.0, float(value)))
    return 1.0


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
