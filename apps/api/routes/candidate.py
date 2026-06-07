from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile

from apps.api.schemas import (
    CandidateDocumentRead,
    CandidateEvidenceCreate,
    CandidateEvidenceRead,
    CandidateEvidenceReindexRead,
    CandidateRead,
    CandidateUpdate,
    EvidenceType,
)
from db.candidate import CandidateDocumentRepository, CandidateEvidenceRepository, CandidateRepository
from services import (
    EmptyCVError,
    InvalidCVFileError,
    UnsupportedCVFileError,
    index_candidate_evidence,
    reindex_all_candidate_evidence,
    upload_candidate_cv,
)


router = APIRouter(prefix="/candidate", tags=["candidate"])
MAX_CV_UPLOAD_BYTES = 5 * 1024 * 1024


@router.get("", response_model=CandidateRead)
def get_candidate() -> dict:
    candidate = CandidateRepository().get()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


@router.put("", response_model=CandidateRead)
def update_candidate(candidate: CandidateUpdate) -> dict:
    return CandidateRepository().upsert(candidate.model_dump())


@router.get("/documents", response_model=list[CandidateDocumentRead])
def list_candidate_documents(limit: int = Query(default=50, ge=1, le=200)) -> list[dict]:
    return CandidateDocumentRepository().list(limit=limit)


@router.post("/documents/upload", response_model=CandidateDocumentRead)
async def upload_candidate_document(
    file: UploadFile = File(...),
    extract_profile: bool = Form(default=True),
    model: str = Form(default="gpt-5.5"),
) -> dict:
    data = await _read_upload_with_limit(file, limit=MAX_CV_UPLOAD_BYTES)
    try:
        result = upload_candidate_cv(
            filename=file.filename or "cv.pdf",
            content_type=file.content_type,
            data=data,
            extract_profile=extract_profile,
            model=model,
        )
    except UnsupportedCVFileError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except (EmptyCVError, InvalidCVFileError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result["document"]


@router.get("/evidence", response_model=list[CandidateEvidenceRead])
def list_candidate_evidence(
    evidence_type: EvidenceType | None = Query(default=None, alias="type"),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[dict]:
    return CandidateEvidenceRepository().list(evidence_type=evidence_type, limit=limit)


@router.post("/evidence", response_model=CandidateEvidenceRead)
def create_candidate_evidence(evidence: CandidateEvidenceCreate) -> dict:
    created = CandidateEvidenceRepository().create(evidence.model_dump())
    index_candidate_evidence(str(created["id"]))
    return created


@router.put("/evidence/{evidence_id}", response_model=CandidateEvidenceRead)
def update_candidate_evidence(evidence_id: UUID, evidence: CandidateEvidenceCreate) -> dict:
    updated = CandidateEvidenceRepository().update(str(evidence_id), evidence.model_dump())
    if updated is None:
        raise HTTPException(status_code=404, detail="Candidate evidence not found")
    index_candidate_evidence(str(updated["id"]))
    return updated


@router.delete("/evidence/{evidence_id}", status_code=204)
def delete_candidate_evidence(evidence_id: UUID) -> Response:
    if not CandidateEvidenceRepository().delete(str(evidence_id)):
        raise HTTPException(status_code=404, detail="Candidate evidence not found")
    return Response(status_code=204)


@router.post("/evidence/reindex", response_model=CandidateEvidenceReindexRead)
def reindex_candidate_evidence() -> dict[str, int]:
    return {"indexed": reindex_all_candidate_evidence()}


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
