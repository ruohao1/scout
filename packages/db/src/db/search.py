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
                    AND (
                        %(location)s::text IS NULL
                        OR (
                            %(location_regex)s::text IS NOT NULL
                            AND jobs.location ~* %(location_regex)s
                            AND (%(location_exclude_regex)s::text IS NULL OR jobs.location !~* %(location_exclude_regex)s)
                        )
                        OR (
                            %(location_regex)s::text IS NULL
                            AND jobs.location ILIKE ANY(%(location_likes)s::text[])
                        )
                    )
                    AND (%(contract_type)s::text IS NULL OR jobs.contract_type = %(contract_type)s)
                    AND (%(company)s::text IS NULL OR jobs.company ILIKE %(company_like)s)
                    AND (%(seniority)s::text IS NULL OR jobs.seniority = %(seniority)s)
                    AND (%(remote_policy)s::text IS NULL OR jobs.remote_policy = %(remote_policy)s)
                    AND (%(source)s::text IS NULL OR jobs.source = %(source)s)
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
        "location_likes": _location_likes(filters.location),
        "location_regex": _location_regex(filters.location),
        "location_exclude_regex": _location_exclude_regex(filters.location),
        "contract_type": filters.contract_type,
        "company": filters.company,
        "company_like": _like(filters.company),
        "seniority": filters.seniority,
        "remote_policy": filters.remote_policy,
        "source": filters.source,
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


def _location_likes(value: str | None) -> list[str] | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"usa", "us", "u.s.", "united states", "united states of america"}:
        return ["%USA%", "%United States%", "% US%", *[f"%, {state}%" for state in _US_STATE_CODES]]
    aliases = _location_aliases(value)
    return [f"%{alias}%" for alias in aliases]


def _location_regex(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized not in {"usa", "us", "u.s.", "united states", "united states of america"}:
        return None
    state_codes = "|".join(sorted(_US_STATE_CODES))
    return rf"(^|[,[:space:]])(USA|U\.S\.|US|United States( of America)?)([,[:space:]]|$)|,\s*({state_codes})(\s*,\s*(US|USA|U\.S\.|United States( of America)?))?\s*$"


def _location_exclude_regex(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized not in {"usa", "us", "u.s.", "united states", "united states of america"}:
        return None
    return r",\s*(AB|BC|MB|NB|NL|NS|NT|NU|ON|PE|QC|SK|YT)\s*,\s*CA\s*$"


def _location_aliases(value: str) -> list[str]:
    normalized = value.strip().lower()
    if normalized == "san francisco":
        return [
            "San Francisco",
            "San Francisco Bay Area",
            "Bay Area",
            "Oakland",
            "Berkeley",
            "Palo Alto",
            "Mountain View",
            "Menlo Park",
            "Redwood City",
            "San Mateo",
            "San Jose",
            "Sunnyvale",
            "Santa Clara",
        ]
    return [value]


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(str(value) for value in embedding) + "]"


_US_STATE_CODES = {
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
    "DC",
}
