from __future__ import annotations

from typing import Any

from db.candidate import CandidateDocumentRepository, CandidateEvidenceRepository

from .candidate_indexing import index_candidate_evidence
from .cv_parsing import extract_cv_text
from .profile_extraction import (
    ProfileExtractionError,
    extract_profile_fields,
    profile_fields_to_candidate_evidence,
)


def upload_candidate_cv(
    *,
    filename: str,
    content_type: str | None,
    data: bytes,
    extract_profile: bool = True,
    model: str = "gpt-5.5",
) -> dict[str, Any]:
    cv_text = extract_cv_text(filename, content_type, data)
    document = CandidateDocumentRepository().create(
        {
            "filename": filename,
            "content_type": content_type or "application/pdf",
            "file_data": data,
            "text": cv_text,
            "source": "upload",
        }
    )

    created: list[dict[str, Any]] = []
    extraction_warning = None
    if extract_profile:
        try:
            extracted = extract_profile_fields(cv_text, model=model)
            evidence_items = profile_fields_to_candidate_evidence(
                extracted,
                source_document_id=str(document["id"]),
            )
            created = CandidateEvidenceRepository().replace_for_document(str(document["id"]), evidence_items)
            for item in created:
                index_candidate_evidence(str(item["id"]))
        except ProfileExtractionError as exc:
            extraction_warning = str(exc)

    return {"document": document, "evidence": created, "extraction_warning": extraction_warning}
