from __future__ import annotations

from typing import Any

from db.candidate import CandidateDocumentRepository, CandidateEvidenceRepository, CandidateRepository
from db.profiles import ProfileRepository
from db.target_profiles import TargetProfileEvidenceRepository, TargetProfileRepository

from .candidate_indexing import index_candidate_evidence
from .target_profiles import create_target_profile, get_target_profile_with_evidence


class LegacyProfileNotFoundError(ValueError):
    pass


def migrate_profiles_to_candidate(source_profile_id: str | None = None) -> dict[str, Any]:
    profile_repository = ProfileRepository()
    profile = _source_profile(profile_repository, source_profile_id)
    if profile is None:
        raise LegacyProfileNotFoundError("Legacy profile not found")

    profile_id = str(profile["id"])
    enrichment = profile_repository.list_enrichment(profile_id)
    candidate = CandidateRepository().upsert(
        {
            "display_name": profile.get("name"),
            "headline": _headline(profile),
            "summary": _summary(profile),
        }
    )
    document = _legacy_document(profile_repository, profile)
    evidence = _migrated_evidence(profile, enrichment, document_id=str(document["id"]) if document else None)
    target_profile = _migrated_target_profile(profile, evidence)

    indexed_count = 0
    for item in evidence:
        indexed_count += index_candidate_evidence(str(item["id"]))

    return {
        "candidate_id": str(candidate["id"]),
        "document_id": str(document["id"]) if document else None,
        "evidence_count": len(evidence),
        "target_profile_id": str(target_profile["id"]) if target_profile else None,
        "indexed_count": indexed_count,
    }


def _source_profile(repository: ProfileRepository, source_profile_id: str | None) -> dict[str, Any] | None:
    if source_profile_id:
        return repository.get(source_profile_id)
    profiles = repository.list(limit=1)
    if not profiles:
        return None
    return repository.get(str(profiles[0]["id"]))


def _legacy_document(repository: ProfileRepository, profile: dict[str, Any]) -> dict[str, Any] | None:
    cv_text = _text(profile.get("cv_text"))
    if cv_text is None:
        return None

    source = _legacy_source(profile)
    documents = CandidateDocumentRepository().list(limit=10_000)
    existing = next((document for document in documents if document.get("source") == source), None)
    if existing is not None:
        return existing

    cv_file = repository.get_cv_file(str(profile["id"])) or {}
    return CandidateDocumentRepository().create(
        {
            "filename": cv_file.get("cv_filename") or profile.get("cv_filename"),
            "content_type": cv_file.get("cv_content_type") or profile.get("cv_content_type"),
            "file_data": cv_file.get("cv_file"),
            "text": cv_text,
            "source": source,
        }
    )


def _migrated_evidence(profile: dict[str, Any], enrichment: dict[str, list[dict[str, Any]]], *, document_id: str | None) -> list[dict[str, Any]]:
    repository = CandidateEvidenceRepository()
    existing = _existing_legacy_evidence(repository, str(profile["id"]))
    migrated: list[dict[str, Any]] = []

    for item in enrichment.get("experiences", []):
        key = ("experience", str(item["id"]))
        migrated.append(existing.get(key) or repository.create(_experience_evidence(profile, item, document_id=document_id)))

    for item in enrichment.get("projects", []):
        key = ("project", str(item["id"]))
        migrated.append(existing.get(key) or repository.create(_project_evidence(profile, item, document_id=document_id)))

    for item in _legacy_skills(profile, enrichment):
        source_id = str(item.get("id") or item["name"])
        key = ("skill", source_id)
        migrated.append(existing.get(key) or repository.create(_skill_evidence(profile, item, source_id=source_id, document_id=document_id)))

    return migrated


def _existing_legacy_evidence(repository: CandidateEvidenceRepository, profile_id: str) -> dict[tuple[str, str], dict[str, Any]]:
    existing: dict[tuple[str, str], dict[str, Any]] = {}
    for item in repository.list(limit=10_000):
        metadata = item.get("metadata") or {}
        if str(metadata.get("legacy_profile_id") or "") != profile_id:
            continue
        source = _text(metadata.get("legacy_source"))
        source_id = _text(metadata.get("legacy_source_id"))
        if source and source_id:
            existing[(source, source_id)] = item
    return existing


def _experience_evidence(profile: dict[str, Any], item: dict[str, Any], *, document_id: str | None) -> dict[str, Any]:
    return {
        "type": "experience",
        "title": item.get("title") or "Experience",
        "organization": item.get("company"),
        "location": item.get("location"),
        "start_date": item.get("start_date"),
        "end_date": item.get("end_date"),
        "is_current": bool(item.get("is_current")),
        "description": item.get("description"),
        "skills": item.get("skills") or [],
        "source_document_id": document_id,
        "metadata": _legacy_metadata(profile, "experience", str(item["id"])),
    }


def _project_evidence(profile: dict[str, Any], item: dict[str, Any], *, document_id: str | None) -> dict[str, Any]:
    return {
        "type": "project",
        "title": item.get("name") or item.get("role") or "Project",
        "organization": item.get("role"),
        "description": item.get("description"),
        "skills": item.get("skills") or [],
        "url": item.get("url"),
        "source_document_id": document_id,
        "metadata": _legacy_metadata(profile, "project", str(item["id"])),
    }


def _skill_evidence(profile: dict[str, Any], item: dict[str, Any], *, source_id: str, document_id: str | None) -> dict[str, Any]:
    details = [item.get("category"), item.get("proficiency")]
    return {
        "type": "skill",
        "title": item["name"],
        "description": "; ".join(part for part in details if part) or None,
        "skills": [item["name"]],
        "source_document_id": document_id,
        "metadata": _legacy_metadata(profile, "skill", source_id),
    }


def _legacy_skills(profile: dict[str, Any], enrichment: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    skills = list(enrichment.get("enriched_skills", []))
    seen = {str(skill.get("name") or "").strip().lower() for skill in skills}
    for name in profile.get("skills") or []:
        text = _text(name)
        if text is None or text.lower() in seen:
            continue
        skills.append({"name": text, "category": None, "proficiency": None})
        seen.add(text.lower())
    return [skill for skill in skills if _text(skill.get("name"))]


def _migrated_target_profile(profile: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any] | None:
    existing = _existing_migrated_target_profile(str(profile["id"]))
    links = [{"evidence_id": str(item["id"]), "weight": 0.8, "note": "Migrated from legacy profile"} for item in evidence]
    if existing is None:
        return create_target_profile({**_target_profile_payload(profile), "evidence": links})

    merged_links = _merged_target_links(str(existing["id"]), links)
    TargetProfileEvidenceRepository().replace_for_profile(str(existing["id"]), merged_links)
    return get_target_profile_with_evidence(str(existing["id"])) or existing


def _existing_migrated_target_profile(profile_id: str) -> dict[str, Any] | None:
    marker = _target_profile_marker(profile_id)
    for profile in TargetProfileRepository().list(limit=10_000):
        if profile.get("instructions") == marker:
            return profile
    return None


def _merged_target_links(target_profile_id: str, links: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = {
        str(link["evidence_id"]): {"evidence_id": str(link["evidence_id"]), "weight": link.get("weight"), "note": link.get("note")}
        for link in TargetProfileEvidenceRepository().list_for_profile(target_profile_id)
    }
    for link in links:
        merged.setdefault(str(link["evidence_id"]), link)
    return list(merged.values())


def _target_profile_payload(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": f"{profile.get('name') or 'Candidate'} target profile",
        "summary": _summary(profile),
        "target_roles": profile.get("target_roles") or [],
        "target_locations": profile.get("target_locations") or [],
        "preferred_contract_types": profile.get("preferred_contract_types") or [],
        "seniority": profile.get("seniority"),
        "remote_preference": profile.get("remote_preference"),
        "must_have_keywords": profile.get("skills") or [],
        "nice_to_have_keywords": [],
        "avoid_keywords": [],
        "instructions": _target_profile_marker(str(profile["id"])),
    }


def _headline(profile: dict[str, Any]) -> str | None:
    roles = profile.get("target_roles") or []
    return ", ".join(roles[:3]) if roles else None


def _summary(profile: dict[str, Any]) -> str | None:
    cv_text = _text(profile.get("cv_text"))
    if cv_text is None:
        return None
    return cv_text[:1000]


def _legacy_source(profile: dict[str, Any]) -> str:
    return f"legacy_profile:{profile['id']}"


def _legacy_metadata(profile: dict[str, Any], source: str, source_id: str) -> dict[str, Any]:
    return {
        "legacy_profile_id": str(profile["id"]),
        "legacy_source": source,
        "legacy_source_id": source_id,
    }


def _target_profile_marker(profile_id: str) -> str:
    return f"Migrated from legacy profile {profile_id}"


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None
