from __future__ import annotations

from typing import Any


def candidate_evidence_text(evidence: dict[str, Any]) -> str:
    parts = [
        f"Type: {evidence.get('type')}",
        f"Title: {evidence.get('title')}",
        f"Organization: {evidence.get('organization')}",
        f"Location: {evidence.get('location')}",
        f"Dates: {_dates(evidence)}",
        f"Description: {evidence.get('description')}",
        f"Skills: {', '.join(evidence.get('skills') or [])}",
        f"URL: {evidence.get('url')}",
    ]
    return "\n".join(part for part in parts if not part.endswith(": None") and not part.endswith(": ")).strip()


def candidate_evidence_metadata(evidence: dict[str, Any]) -> dict[str, Any]:
    source_document_id = evidence.get("source_document_id")
    return {
        "type": evidence.get("type"),
        "title": evidence.get("title"),
        "organization": evidence.get("organization"),
        "skills": evidence.get("skills") or [],
        "source_document_id": str(source_document_id) if source_document_id is not None else None,
        "confidence": evidence.get("confidence"),
    }


def _dates(evidence: dict[str, Any]) -> str:
    start_date = evidence.get("start_date")
    end_date = "present" if evidence.get("is_current") else evidence.get("end_date")
    if start_date and end_date:
        return f"{start_date} - {end_date}"
    return str(start_date or end_date or "")
