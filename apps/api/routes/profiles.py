from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from apps.api.schemas import ProfileCreate, ProfileRead
from db.profiles import ProfileRepository
from services import EmptyCVError, InvalidCVFileError, ProfileExtractionError, UnsupportedCVFileError, extract_cv_text, extract_profile_fields


router = APIRouter(prefix="/profiles", tags=["profiles"])
MAX_CV_UPLOAD_BYTES = 5 * 1024 * 1024


@router.post("", response_model=ProfileRead)
def create_profile(profile: ProfileCreate) -> dict:
    return ProfileRepository().create(profile.model_dump())


@router.get("", response_model=list[ProfileRead])
def list_profiles(limit: int = Query(default=50, ge=1, le=200)) -> list[dict]:
    return ProfileRepository().list(limit=limit)


@router.post("/upload", response_model=ProfileRead)
async def upload_profile(
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    target_roles: str | None = Form(default=None),
    target_locations: str | None = Form(default=None),
    skills: str | None = Form(default=None),
    seniority: str | None = Form(default=None),
    preferred_contract_types: str | None = Form(default=None),
    remote_preference: str | None = Form(default=None),
    extract_profile: bool = Form(default=True),
    model: str = Form(default="gpt-5.5"),
) -> dict:
    data = await file.read()
    if len(data) > MAX_CV_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="CV upload must be 5 MB or smaller")

    try:
        cv_text = extract_cv_text(file.filename or "", file.content_type, data)
    except UnsupportedCVFileError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except (EmptyCVError, InvalidCVFileError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    extracted = _empty_extracted_profile()
    if extract_profile:
        try:
            extracted = extract_profile_fields(cv_text, model=model)
        except ProfileExtractionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    profile = {
        "name": _blank_to_none(name),
        "cv_text": cv_text,
        "target_roles": _csv_values(target_roles) if target_roles is not None else extracted["target_roles"],
        "target_locations": _csv_values(target_locations) if target_locations is not None else extracted["target_locations"],
        "skills": _csv_values(skills) if skills is not None else extracted["skills"],
        "seniority": _blank_to_none(seniority) if seniority is not None else extracted["seniority"],
        "preferred_contract_types": _csv_values(preferred_contract_types)
        if preferred_contract_types is not None
        else extracted["preferred_contract_types"],
        "remote_preference": _blank_to_none(remote_preference) if remote_preference is not None else extracted["remote_preference"],
    }
    return ProfileRepository().create(profile)


@router.get("/{profile_id}", response_model=ProfileRead)
def get_profile(profile_id: UUID) -> dict:
    profile = ProfileRepository().get(str(profile_id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


def _csv_values(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _empty_extracted_profile() -> dict:
    return {
        "target_roles": [],
        "target_locations": [],
        "skills": [],
        "seniority": None,
        "preferred_contract_types": [],
        "remote_preference": None,
    }
