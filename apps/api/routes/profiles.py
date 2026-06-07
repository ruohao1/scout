from __future__ import annotations

from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile

from apps.api.schemas import (
    ProfileCreate,
    ProfileEnrichmentRead,
    ProfileExperienceCreate,
    ProfileExperienceRead,
    ProfileListRead,
    ProfileProjectCreate,
    ProfileProjectRead,
    ProfileRead,
    ProfileSkillCreate,
    ProfileSkillRead,
)
from db.profiles import ProfileRepository
from services import EmptyCVError, InvalidCVFileError, ProfileExtractionError, UnsupportedCVFileError, extract_cv_text, extract_profile_fields


router = APIRouter(prefix="/profiles", tags=["profiles"])
MAX_CV_UPLOAD_BYTES = 5 * 1024 * 1024


@router.post("", response_model=ProfileRead)
def create_profile(profile: ProfileCreate) -> dict:
    return ProfileRepository().create(profile.model_dump())


@router.get("", response_model=list[ProfileListRead])
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
    extract_profile: bool = Form(default=False),
    model: str = Form(default="gpt-5.5"),
) -> dict:
    data = await _read_upload_with_limit(file, limit=MAX_CV_UPLOAD_BYTES)

    try:
        cv_text = extract_cv_text(file.filename or "", file.content_type, data)
    except UnsupportedCVFileError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except (EmptyCVError, InvalidCVFileError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    extracted = _empty_extracted_profile()
    extraction_warning = None
    if extract_profile:
        try:
            extracted = extract_profile_fields(cv_text, model=model)
        except ProfileExtractionError as exc:
            extraction_warning = str(exc)

    profile = {
        "name": _blank_to_none(name),
        "cv_text": cv_text,
        "cv_filename": file.filename or "cv.pdf",
        "cv_content_type": file.content_type or "application/pdf",
        "cv_file": data,
        "target_roles": _csv_values(target_roles) if target_roles is not None else extracted["target_roles"],
        "target_locations": _csv_values(target_locations) if target_locations is not None else extracted["target_locations"],
        "skills": _csv_values(skills) if skills is not None else extracted["skills"],
        "seniority": _blank_to_none(seniority) if seniority is not None else extracted["seniority"],
        "preferred_contract_types": _csv_values(preferred_contract_types)
        if preferred_contract_types is not None
        else extracted["preferred_contract_types"],
        "remote_preference": _blank_to_none(remote_preference) if remote_preference is not None else extracted["remote_preference"],
    }
    repository = ProfileRepository()
    created = repository.create(profile)
    if extract_profile and extraction_warning is None:
        _replace_extracted_enrichment(repository, str(created["id"]), extracted)
    created["extraction_warning"] = extraction_warning
    return created


@router.get("/{profile_id}/cv")
def get_profile_cv(profile_id: UUID) -> Response:
    cv_file = ProfileRepository().get_cv_file(str(profile_id))
    if cv_file is None:
        raise HTTPException(status_code=404, detail="Profile CV file not found")

    filename = cv_file["cv_filename"] or "cv.pdf"
    content_type = cv_file["cv_content_type"] or "application/pdf"
    quoted_filename = quote(filename)
    return Response(
        content=bytes(cv_file["cv_file"]),
        media_type=content_type,
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quoted_filename}"},
    )


@router.post("/{profile_id}/cv", response_model=ProfileRead)
async def attach_profile_cv(
    profile_id: UUID,
    file: UploadFile = File(...),
    extract_profile: bool = Form(default=True),
    model: str = Form(default="gpt-5.5"),
) -> dict:
    data = await _read_upload_with_limit(file, limit=MAX_CV_UPLOAD_BYTES)
    try:
        cv_text = extract_cv_text(file.filename or "", file.content_type, data)
    except UnsupportedCVFileError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except (EmptyCVError, InvalidCVFileError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    extracted = _empty_extracted_profile()
    extraction_warning = None
    if extract_profile:
        try:
            extracted = extract_profile_fields(cv_text, model=model)
        except ProfileExtractionError as exc:
            extraction_warning = str(exc)

    repository = ProfileRepository()
    updated = repository.attach_cv_file(
        str(profile_id),
        filename=file.filename or "cv.pdf",
        content_type=file.content_type or "application/pdf",
        data=data,
        cv_text=cv_text,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    if extract_profile and extraction_warning is None:
        _replace_extracted_enrichment(repository, str(profile_id), extracted)
    updated["extraction_warning"] = extraction_warning
    return updated


@router.get("/{profile_id}/enrichment", response_model=ProfileEnrichmentRead)
def get_profile_enrichment(profile_id: UUID) -> dict:
    repository = ProfileRepository()
    _require_profile(repository, str(profile_id))
    return repository.list_enrichment(str(profile_id))


@router.post("/{profile_id}/experiences", response_model=ProfileExperienceRead)
def create_profile_experience(profile_id: UUID, experience: ProfileExperienceCreate) -> dict:
    repository = ProfileRepository()
    _require_profile(repository, str(profile_id))
    return repository.create_experience(str(profile_id), _normalized_payload(experience.model_dump()))


@router.put("/{profile_id}/experiences/{experience_id}", response_model=ProfileExperienceRead)
def update_profile_experience(profile_id: UUID, experience_id: UUID, experience: ProfileExperienceCreate) -> dict:
    repository = ProfileRepository()
    _require_profile(repository, str(profile_id))
    updated = repository.update_experience(str(profile_id), str(experience_id), _normalized_payload(experience.model_dump()))
    if updated is None:
        raise HTTPException(status_code=404, detail="Profile experience not found")
    return updated


@router.delete("/{profile_id}/experiences/{experience_id}", status_code=204)
def delete_profile_experience(profile_id: UUID, experience_id: UUID) -> Response:
    repository = ProfileRepository()
    _require_profile(repository, str(profile_id))
    if not repository.delete_experience(str(profile_id), str(experience_id)):
        raise HTTPException(status_code=404, detail="Profile experience not found")
    return Response(status_code=204)


@router.post("/{profile_id}/projects", response_model=ProfileProjectRead)
def create_profile_project(profile_id: UUID, project: ProfileProjectCreate) -> dict:
    repository = ProfileRepository()
    _require_profile(repository, str(profile_id))
    return repository.create_project(str(profile_id), _normalized_payload(project.model_dump()))


@router.put("/{profile_id}/projects/{project_id}", response_model=ProfileProjectRead)
def update_profile_project(profile_id: UUID, project_id: UUID, project: ProfileProjectCreate) -> dict:
    repository = ProfileRepository()
    _require_profile(repository, str(profile_id))
    updated = repository.update_project(str(profile_id), str(project_id), _normalized_payload(project.model_dump()))
    if updated is None:
        raise HTTPException(status_code=404, detail="Profile project not found")
    return updated


@router.delete("/{profile_id}/projects/{project_id}", status_code=204)
def delete_profile_project(profile_id: UUID, project_id: UUID) -> Response:
    repository = ProfileRepository()
    _require_profile(repository, str(profile_id))
    if not repository.delete_project(str(profile_id), str(project_id)):
        raise HTTPException(status_code=404, detail="Profile project not found")
    return Response(status_code=204)


@router.post("/{profile_id}/skills", response_model=ProfileSkillRead)
def create_profile_skill(profile_id: UUID, skill: ProfileSkillCreate) -> dict:
    repository = ProfileRepository()
    _require_profile(repository, str(profile_id))
    return repository.create_skill(str(profile_id), _normalized_payload(skill.model_dump()))


@router.put("/{profile_id}/skills/{skill_id}", response_model=ProfileSkillRead)
def update_profile_skill(profile_id: UUID, skill_id: UUID, skill: ProfileSkillCreate) -> dict:
    repository = ProfileRepository()
    _require_profile(repository, str(profile_id))
    updated = repository.update_skill(str(profile_id), str(skill_id), _normalized_payload(skill.model_dump()))
    if updated is None:
        raise HTTPException(status_code=404, detail="Profile skill not found")
    return updated


@router.delete("/{profile_id}/skills/{skill_id}", status_code=204)
def delete_profile_skill(profile_id: UUID, skill_id: UUID) -> Response:
    repository = ProfileRepository()
    _require_profile(repository, str(profile_id))
    if not repository.delete_skill(str(profile_id), str(skill_id)):
        raise HTTPException(status_code=404, detail="Profile skill not found")
    return Response(status_code=204)


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


def _require_profile(repository: ProfileRepository, profile_id: str) -> None:
    if repository.get(profile_id) is None:
        raise HTTPException(status_code=404, detail="Profile not found")


def _normalized_payload(payload: dict) -> dict:
    normalized = {}
    for key, value in payload.items():
        if isinstance(value, str):
            normalized[key] = _blank_to_none(value)
        elif isinstance(value, list):
            normalized[key] = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        else:
            normalized[key] = value
    return normalized


def _empty_extracted_profile() -> dict:
    return {
        "target_roles": [],
        "target_locations": [],
        "skills": [],
        "seniority": None,
        "preferred_contract_types": [],
        "remote_preference": None,
        "experiences": [],
        "projects": [],
        "enriched_skills": [],
    }


def _replace_extracted_enrichment(repository: ProfileRepository, profile_id: str, extracted: dict) -> None:
    repository.replace_enrichment(
        profile_id,
        experiences=extracted.get("experiences") or [],
        projects=extracted.get("projects") or [],
        skills=extracted.get("enriched_skills") or [],
    )


async def _read_upload_with_limit(file: UploadFile, *, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=413, detail="CV upload must be 5 MB or smaller")
        chunks.append(chunk)
    return b"".join(chunks)
