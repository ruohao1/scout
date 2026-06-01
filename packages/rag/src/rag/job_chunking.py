from __future__ import annotations

from typing import Any

from .chunking import chunk_text
from .types import Document, JobChunk


SECTION_HEADINGS = {
    "about us",
    "benefits",
    "contract details",
    "mission",
    "nice to have",
    "profile",
    "qualifications",
    "requirements",
    "responsibilities",
    "skills",
}


def chunk_job(job: dict[str, Any]) -> list[JobChunk]:
    job_id = str(job["id"])
    description = str(job.get("description") or "")
    metadata = _job_metadata(job)

    section_chunks = _section_chunks(job_id=job_id, description=description, metadata=metadata)
    if section_chunks:
        return section_chunks

    document = Document(id=job_id, text=description, metadata=metadata)
    return [
        JobChunk(
            job_id=job_id,
            chunk_index=index,
            section=None,
            content=chunk.text,
            metadata=chunk.metadata,
        )
        for index, chunk in enumerate(chunk_text(document))
    ]


def _section_chunks(*, job_id: str, description: str, metadata: dict[str, Any]) -> list[JobChunk]:
    chunks: list[JobChunk] = []
    current_section: str | None = None
    current_lines: list[str] = []

    for line in description.splitlines():
        heading = _heading(line)
        if heading:
            if current_section and _content_text(current_lines):
                chunks.append(_job_chunk(job_id, len(chunks), current_section, current_lines, metadata))
            current_section = heading
            current_lines = [line]
            continue
        if current_section:
            current_lines.append(line)

    if current_section and _content_text(current_lines):
        chunks.append(_job_chunk(job_id, len(chunks), current_section, current_lines, metadata))

    return chunks


def _heading(line: str) -> str | None:
    normalized = line.strip().lower().removesuffix(":")
    return normalized if normalized in SECTION_HEADINGS else None


def _content_text(lines: list[str]) -> str:
    return "\n".join(lines).strip()


def _job_chunk(
    job_id: str,
    chunk_index: int,
    section: str,
    lines: list[str],
    metadata: dict[str, Any],
) -> JobChunk:
    return JobChunk(
        job_id=job_id,
        chunk_index=chunk_index,
        section=section,
        content=_content_text(lines),
        metadata={**metadata, "section": section},
    )


def _job_metadata(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": job.get("title"),
        "company": job.get("company"),
        "location": job.get("location"),
        "contract_type": job.get("contract_type"),
        "skills": job.get("skills") or [],
    }
