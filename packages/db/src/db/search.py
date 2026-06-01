from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row
from rag.types import JobSearchFilters, JobSearchResult

from .config import database_url


class JobSearchRepository:
    def __init__(self, *, url: str | None = None) -> None:
        self.url = url or database_url()

    def search_chunks(
        self,
        *,
        embedding: list[float],
        filters: JobSearchFilters,
        limit: int = 10,
    ) -> list[JobSearchResult]:
        params = _search_params(embedding=embedding, filters=filters, limit=limit)
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            rows = conn.execute(
                """
                SELECT
                    jobs.id AS job_id,
                    job_chunks.id AS chunk_id,
                    job_chunks.chunk_index,
                    1 - (job_chunks.embedding <=> %(embedding)s::vector) AS score,
                    jobs.title,
                    job_chunks.content,
                    job_chunks.section,
                    jobs.company,
                    jobs.location,
                    jobs.contract_type,
                    jobs.source,
                    jobs.url,
                    jobs.salary,
                    jobs.seniority,
                    jobs.remote_policy,
                    jobs.skills,
                    jobs.created_at
                FROM job_chunks
                JOIN jobs ON jobs.id = job_chunks.job_id
                WHERE job_chunks.embedding IS NOT NULL
                    AND (%(location)s::text IS NULL OR jobs.location ILIKE %(location_like)s)
                    AND (%(contract_type)s::text IS NULL OR jobs.contract_type = %(contract_type)s)
                    AND (%(company)s::text IS NULL OR jobs.company ILIKE %(company_like)s)
                    AND (%(seniority)s::text IS NULL OR jobs.seniority = %(seniority)s)
                    AND (%(remote_policy)s::text IS NULL OR jobs.remote_policy = %(remote_policy)s)
                ORDER BY job_chunks.embedding <=> %(embedding)s::vector
                LIMIT %(limit)s
                """,
                params,
            ).fetchall()
        return [_row_to_result(row) for row in rows]


def _search_params(*, embedding: list[float], filters: JobSearchFilters, limit: int) -> dict[str, Any]:
    return {
        "embedding": _vector_literal(embedding),
        "limit": limit,
        "location": filters.location,
        "location_like": _like(filters.location),
        "contract_type": filters.contract_type,
        "company": filters.company,
        "company_like": _like(filters.company),
        "seniority": filters.seniority,
        "remote_policy": filters.remote_policy,
    }


def _row_to_result(row: dict[str, Any]) -> JobSearchResult:
    return JobSearchResult(
        job_id=str(row["job_id"]),
        chunk_id=str(row["chunk_id"]),
        chunk_index=int(row["chunk_index"]),
        score=float(row["score"]),
        title=str(row["title"]),
        content=str(row["content"]),
        section=row["section"],
        company=row["company"],
        location=row["location"],
        contract_type=row["contract_type"],
        source=row["source"],
        url=row["url"],
        salary=row["salary"],
        seniority=row["seniority"],
        remote_policy=row["remote_policy"],
        skills=list(row["skills"] or []),
        created_at=row["created_at"],
    )


def _like(value: str | None) -> str | None:
    return f"%{value}%" if value is not None else None


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(str(value) for value in embedding) + "]"
