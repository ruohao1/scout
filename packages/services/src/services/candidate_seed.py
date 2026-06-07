from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from db.candidate import CandidateDocumentRepository, CandidateEvidenceRepository, CandidateRepository
from db.target_profiles import TargetProfileRepository

from .candidate_indexing import index_candidate_evidence
from .target_profiles import create_target_profile, get_target_profile_with_evidence, update_target_profile


DEFAULT_FAKE_CANDIDATE_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "fake_candidate_maya_chen.json"


class CandidateSeedFixtureError(ValueError):
    pass


def seed_fake_candidate(
    *,
    fixture_path: Path | None = None,
    should_index: bool = True,
    with_target_profile: bool = True,
) -> dict[str, Any]:
    fixture = _load_fixture(fixture_path or DEFAULT_FAKE_CANDIDATE_FIXTURE)
    candidate = CandidateRepository().upsert(_required_dict(fixture, "candidate"))
    document = _seed_document(_required_dict(fixture, "document"))
    evidence = CandidateEvidenceRepository().replace_for_document(str(document["id"]), _required_list(fixture, "evidence"))

    indexed_count = 0
    if should_index:
        for item in evidence:
            indexed_count += index_candidate_evidence(str(item["id"]))

    target_profile = None
    if with_target_profile and isinstance(fixture.get("target_profile"), dict):
        target_profile = _seed_target_profile(fixture["target_profile"], evidence)

    return {
        "candidate_id": str(candidate["id"]),
        "document_id": str(document["id"]),
        "evidence_count": len(evidence),
        "target_profile_id": str(target_profile["id"]) if target_profile else None,
        "indexed_count": indexed_count,
    }


def _load_fixture(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CandidateSeedFixtureError(f"Could not read candidate fixture: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CandidateSeedFixtureError(f"Candidate fixture is not valid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise CandidateSeedFixtureError("Candidate fixture must be a JSON object")
    return data


def _seed_document(payload: dict[str, Any]) -> dict[str, Any]:
    source = _required_text(payload, "source")
    existing = next(
        (document for document in CandidateDocumentRepository().list(limit=10_000) if document.get("source") == source),
        None,
    )
    if existing is not None:
        return existing
    return CandidateDocumentRepository().create(payload)


def _seed_target_profile(payload: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    marker = _required_text(payload, "instructions")
    profile_payload = dict(payload)
    link_specs = profile_payload.pop("evidence", []) or []
    profile_payload["evidence"] = _target_profile_links(link_specs, evidence)
    existing = next(
        (profile for profile in TargetProfileRepository().list(limit=10_000) if profile.get("instructions") == marker),
        None,
    )
    if existing is None:
        return create_target_profile(profile_payload)
    return update_target_profile(str(existing["id"]), profile_payload) or get_target_profile_with_evidence(str(existing["id"])) or existing


def _target_profile_links(link_specs: object, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(link_specs, list):
        raise CandidateSeedFixtureError("target_profile.evidence must be a list")
    evidence_by_title = {str(item.get("title") or ""): item for item in evidence}
    links: list[dict[str, Any]] = []
    for spec in link_specs:
        if not isinstance(spec, dict):
            raise CandidateSeedFixtureError("target_profile.evidence entries must be objects")
        title = _required_text(spec, "title")
        item = evidence_by_title.get(title)
        if item is None:
            raise CandidateSeedFixtureError(f"Target profile references unknown evidence title: {title}")
        links.append(
            {
                "evidence_id": str(item["id"]),
                "weight": spec.get("weight", 1.0),
                "note": spec.get("note"),
            }
        )
    return links


def _required_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise CandidateSeedFixtureError(f"Candidate fixture field must be an object: {key}")
    return value


def _required_list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise CandidateSeedFixtureError(f"Candidate fixture field must be a list of objects: {key}")
    return value


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CandidateSeedFixtureError(f"Candidate fixture field must be non-empty text: {key}")
    return value.strip()
