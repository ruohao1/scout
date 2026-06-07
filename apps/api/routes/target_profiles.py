from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response

from apps.api.schemas import TargetProfileCreate, TargetProfileRead, TargetProfileSuggestionRequest
from db.target_profiles import TargetProfileEvidenceRepository, TargetProfileRepository


router = APIRouter(prefix="/target-profiles", tags=["target-profiles"])


@router.get("", response_model=list[TargetProfileRead])
def list_target_profiles(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    return [_with_evidence(profile) for profile in TargetProfileRepository().list(limit=limit)]


@router.post("", response_model=TargetProfileRead)
def create_target_profile(profile: TargetProfileCreate) -> dict[str, Any]:
    payload = profile.model_dump()
    evidence = payload.pop("evidence")
    created = TargetProfileRepository().create(payload)
    TargetProfileEvidenceRepository().replace_for_profile(str(created["id"]), evidence)
    return _with_evidence(created)


@router.post("/suggest")
def suggest_target_profiles(_request: TargetProfileSuggestionRequest) -> None:
    raise HTTPException(status_code=501, detail="Target profile suggestion service is not implemented yet")


@router.get("/{target_profile_id}", response_model=TargetProfileRead)
def get_target_profile(target_profile_id: UUID) -> dict[str, Any]:
    profile = TargetProfileRepository().get(str(target_profile_id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Target profile not found")
    return _with_evidence(profile)


@router.put("/{target_profile_id}", response_model=TargetProfileRead)
def update_target_profile(target_profile_id: UUID, profile: TargetProfileCreate) -> dict[str, Any]:
    payload = profile.model_dump()
    evidence = payload.pop("evidence")
    updated = TargetProfileRepository().update(str(target_profile_id), payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Target profile not found")
    TargetProfileEvidenceRepository().replace_for_profile(str(target_profile_id), evidence)
    return _with_evidence(updated)


@router.delete("/{target_profile_id}", status_code=204)
def delete_target_profile(target_profile_id: UUID) -> Response:
    if not TargetProfileRepository().delete(str(target_profile_id)):
        raise HTTPException(status_code=404, detail="Target profile not found")
    return Response(status_code=204)


def _with_evidence(profile: dict[str, Any]) -> dict[str, Any]:
    links = TargetProfileEvidenceRepository().list_for_profile(str(profile["id"]))
    return {**profile, "evidence": [_evidence_link(link) for link in links]}


def _evidence_link(link: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": link["evidence_id"],
        "weight": link["weight"],
        "note": link["note"],
    }
