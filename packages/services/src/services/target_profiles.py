from __future__ import annotations

import json
from typing import Any, Protocol

from db.candidate import CandidateEvidenceRepository
from db.target_profiles import TargetProfileEvidenceRepository, TargetProfileRepository
from providers.openai_auth import OpenAIAuthProvider
from providers.types import GenerateRequest, ProviderMessage

TARGET_PROFILE_SUGGESTION_TIMEOUT_SECONDS = 30.0
MAX_EVIDENCE_PROMPT_CHARS = 60_000


class TargetProfileSuggestionError(ValueError):
    pass


class TargetProfileSuggestionProvider(Protocol):
    def generate(self, request: GenerateRequest):
        ...


def create_target_profile(payload: dict[str, Any]) -> dict[str, Any]:
    profile = dict(payload)
    evidence = profile.pop("evidence", []) or []
    created = TargetProfileRepository().create(profile)
    TargetProfileEvidenceRepository().replace_for_profile(str(created["id"]), evidence)
    return get_target_profile_with_evidence(str(created["id"])) or {**created, "evidence": []}


def update_target_profile(target_profile_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    profile = dict(payload)
    evidence = profile.pop("evidence", None)
    updated = TargetProfileRepository().update(target_profile_id, profile)
    if updated is None:
        return None
    if evidence is not None:
        TargetProfileEvidenceRepository().replace_for_profile(target_profile_id, evidence or [])
    return get_target_profile_with_evidence(target_profile_id)


def get_target_profile_with_evidence(target_profile_id: str) -> dict[str, Any] | None:
    profile = TargetProfileRepository().get(target_profile_id)
    if profile is None:
        return None
    links = TargetProfileEvidenceRepository().list_for_profile(target_profile_id)
    return {**profile, "evidence": [_evidence_link(link) for link in links]}


def suggest_target_profiles(
    *,
    count: int = 3,
    provider: TargetProfileSuggestionProvider | None = None,
    model: str = "gpt-5.5",
) -> list[dict[str, Any]]:
    evidence = CandidateEvidenceRepository().list(limit=200)
    evidence_ids = {str(item["id"]) for item in evidence}
    suggestion_provider = provider or OpenAIAuthProvider(timeout=TARGET_PROFILE_SUGGESTION_TIMEOUT_SECONDS)
    try:
        response = suggestion_provider.generate(
            GenerateRequest(
                model=model,
                messages=[ProviderMessage(role="user", content=_suggestion_prompt(evidence, count=count))],
                instructions="Return strict JSON only. Do not include markdown fences or prose outside JSON.",
            )
        )
    except Exception as exc:
        raise TargetProfileSuggestionError("Target profile suggestions require OpenAI OAuth login and a working model") from exc
    return _parse_suggestions(response.text, evidence_ids=evidence_ids, count=count)


def _evidence_link(link: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": link["evidence_id"],
        "weight": _clamp_weight(link.get("weight")),
        "note": _text(link.get("note")),
    }


def _suggestion_prompt(evidence: list[dict[str, Any]], *, count: int) -> str:
    evidence_lines = []
    for item in evidence:
        skills = ", ".join(item.get("skills") or [])
        evidence_lines.append(
            "\n".join(
                part
                for part in [
                    f"Evidence ID: {item.get('id')}",
                    f"Type: {item.get('type')}",
                    f"Title: {item.get('title')}",
                    f"Organization: {item.get('organization')}",
                    f"Location: {item.get('location')}",
                    f"Description: {item.get('description')}",
                    f"Skills: {skills}",
                ]
                if not part.endswith(": None") and not part.endswith(": ")
            )
        )
    evidence_text = "\n\n".join(evidence_lines)[:MAX_EVIDENCE_PROMPT_CHARS]
    return (
        f"Suggest {count} target job-search profiles from the candidate evidence below. "
        "Return unsaved drafts only; do not invent evidence IDs. Return strict JSON with a top-level profiles array. "
        "Each profile must contain: name, summary, target_roles, target_locations, preferred_contract_types, "
        "seniority, remote_preference, must_have_keywords, nice_to_have_keywords, avoid_keywords, instructions, "
        "and evidence. evidence must be links with evidence_id, weight from 0 to 1, and note. "
        "Use empty arrays or null when fields are unsupported.\n\n"
        f"Candidate evidence:\n{evidence_text}"
    )


def _parse_suggestions(text: str, *, evidence_ids: set[str], count: int) -> list[dict[str, Any]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TargetProfileSuggestionError("Model returned invalid target profile suggestion JSON") from exc
    if not isinstance(data, dict) or not isinstance(data.get("profiles"), list):
        raise TargetProfileSuggestionError("Model target profile suggestion JSON must contain a profiles array")

    profiles: list[dict[str, Any]] = []
    for item in data["profiles"]:
        if not isinstance(item, dict):
            continue
        name = _text(item.get("name"))
        if name is None:
            continue
        profiles.append(
            {
                "name": name,
                "summary": _text(item.get("summary")),
                "target_roles": _string_list(item.get("target_roles"), limit=12),
                "target_locations": _string_list(item.get("target_locations"), limit=12),
                "preferred_contract_types": _string_list(item.get("preferred_contract_types"), limit=8),
                "seniority": _text(item.get("seniority")),
                "remote_preference": _text(item.get("remote_preference")),
                "must_have_keywords": _string_list(item.get("must_have_keywords"), limit=20),
                "nice_to_have_keywords": _string_list(item.get("nice_to_have_keywords"), limit=20),
                "avoid_keywords": _string_list(item.get("avoid_keywords"), limit=20),
                "instructions": _text(item.get("instructions")),
                "evidence": _suggested_evidence_links(item.get("evidence"), evidence_ids=evidence_ids),
            }
        )
        if len(profiles) >= count:
            break
    return profiles


def _suggested_evidence_links(value: object, *, evidence_ids: set[str]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        evidence_id = _text(item.get("evidence_id"))
        if evidence_id is None or evidence_id not in evidence_ids or evidence_id in seen:
            continue
        links.append(
            {
                "evidence_id": evidence_id,
                "weight": _clamp_weight(item.get("weight")),
                "note": _text(item.get("note")),
            }
        )
        seen.add(evidence_id)
    return links


def _string_list(value: object, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _text(item)
        if text is None:
            continue
        key = text.lower()
        if key in seen:
            continue
        result.append(text)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _clamp_weight(value: object) -> float:
    if isinstance(value, int | float):
        return max(0.0, min(1.0, float(value)))
    return 1.0
