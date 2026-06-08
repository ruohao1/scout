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
    summary_chunk = _summary_chunk(job_id=job_id, job=job, metadata=metadata)

    section_chunks = _section_chunks(job_id=job_id, description=description, metadata=metadata, start_index=1)
    if section_chunks:
        return [summary_chunk, *section_chunks]

    return [summary_chunk, *_description_chunks(job_id=job_id, description=description, metadata=metadata, start_index=1)]


def _description_chunks(*, job_id: str, description: str, metadata: dict[str, Any], start_index: int) -> list[JobChunk]:
    document = Document(id=job_id, text=description, metadata=metadata)
    return [
        JobChunk(
            job_id=job_id,
            chunk_index=start_index + index,
            section=None,
            content=chunk.text,
            metadata=chunk.metadata,
        )
        for index, chunk in enumerate(chunk_text(document))
    ]


def _summary_chunk(*, job_id: str, job: dict[str, Any], metadata: dict[str, Any]) -> JobChunk:
    return JobChunk(
        job_id=job_id,
        chunk_index=0,
        section="summary",
        content=_summary_text(job),
        metadata={**metadata, "section": "summary"},
    )


def _section_chunks(*, job_id: str, description: str, metadata: dict[str, Any], start_index: int) -> list[JobChunk]:
    chunks: list[JobChunk] = []
    current_section: str | None = None
    current_lines: list[str] = []

    for line in description.splitlines():
        heading = _heading(line)
        if heading:
            if current_section and _content_text(current_lines):
                chunks.append(_job_chunk(job_id, start_index + len(chunks), current_section, current_lines, metadata))
            current_section = heading
            current_lines = [line]
            continue
        if current_section:
            current_lines.append(line)

    if current_section and _content_text(current_lines):
        chunks.append(_job_chunk(job_id, start_index + len(chunks), current_section, current_lines, metadata))

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
        "source": job.get("source"),
        "salary": job.get("salary"),
        "seniority": job.get("seniority"),
        "remote_policy": job.get("remote_policy"),
        "skills": job.get("skills") or [],
    }


def _summary_text(job: dict[str, Any]) -> str:
    skills = ", ".join(str(skill) for skill in job.get("skills") or [])
    fields = [
        ("Title", job.get("title")),
        ("Company", job.get("company")),
        ("Location", job.get("location")),
        ("Contract type", job.get("contract_type")),
        ("Seniority", job.get("seniority")),
        ("Remote policy", job.get("remote_policy")),
        ("Salary", job.get("salary")),
        ("Source", job.get("source")),
        ("Skills", skills),
        ("Description", _description_excerpt(job.get("description"))),
    ]
    return "\n".join(f"{label}: {value}" for label, value in fields if value)


def _description_excerpt(value: object, *, limit: int = 2_000) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text if len(text) <= limit else f"{text[:limit].rstrip()}..."
