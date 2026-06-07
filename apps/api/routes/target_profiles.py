from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response

from apps.api.schemas import TargetProfileCreate, TargetProfileRead, TargetProfileSuggestionRequest
from db.target_profiles import TargetProfileRepository
from services import (
    TargetProfileSuggestionError,
    create_target_profile as create_target_profile_service,
    get_target_profile_with_evidence,
    suggest_target_profiles as suggest_target_profiles_service,
    update_target_profile as update_target_profile_service,
)


router = APIRouter(prefix="/target-profiles", tags=["target-profiles"])


@router.get("", response_model=list[TargetProfileRead])
def list_target_profiles(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    profiles = []
    for profile in TargetProfileRepository().list(limit=limit):
        profile_with_evidence = get_target_profile_with_evidence(str(profile["id"]))
        if profile_with_evidence is not None:
            profiles.append(profile_with_evidence)
    return profiles


@router.post("", response_model=TargetProfileRead)
def create_target_profile(profile: TargetProfileCreate) -> dict[str, Any]:
    return create_target_profile_service(profile.model_dump())


@router.post("/suggest", response_model=list[TargetProfileCreate])
def suggest_target_profiles(request: TargetProfileSuggestionRequest) -> list[dict[str, Any]]:
    try:
        return suggest_target_profiles_service(count=request.count)
    except TargetProfileSuggestionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{target_profile_id}", response_model=TargetProfileRead)
def get_target_profile(target_profile_id: UUID) -> dict[str, Any]:
    profile = get_target_profile_with_evidence(str(target_profile_id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Target profile not found")
    return profile


@router.put("/{target_profile_id}", response_model=TargetProfileRead)
def update_target_profile(target_profile_id: UUID, profile: TargetProfileCreate) -> dict[str, Any]:
    updated = update_target_profile_service(str(target_profile_id), profile.model_dump())
    if updated is None:
        raise HTTPException(status_code=404, detail="Target profile not found")
    return updated


@router.delete("/{target_profile_id}", status_code=204)
def delete_target_profile(target_profile_id: UUID) -> Response:
    if not TargetProfileRepository().delete(str(target_profile_id)):
        raise HTTPException(status_code=404, detail="Target profile not found")
    return Response(status_code=204)
