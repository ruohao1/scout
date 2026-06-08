from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .config import database_url


JOB_COLUMNS = """
    id,
    title,
    company,
    location,
    contract_type,
    source,
    url,
    description,
    salary,
    seniority,
    remote_policy,
    skills,
    raw_payload,
    created_at,
    updated_at
"""

JOB_LIST_COLUMNS = """
    jobs.id,
    jobs.title,
    jobs.company,
    jobs.location,
    jobs.contract_type,
    jobs.source,
    jobs.url,
    jobs.description,
    jobs.salary,
    jobs.seniority,
    jobs.remote_policy,
    jobs.skills,
    jobs.raw_payload,
    COALESCE(indexed.chunk_count, 0) AS indexed_chunks,
    COALESCE(indexed.chunk_count, 0) > 0 AS is_indexed,
    jobs.created_at,
    jobs.updated_at
"""


class JobRepository:
    def __init__(self, *, url: str | None = None) -> None:
        self.url = url or database_url()

    def create(self, job: dict[str, Any]) -> dict[str, Any]:
        params = {**job, "raw_payload": Jsonb(job["raw_payload"])}
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                INSERT INTO jobs (
                    title,
                    company,
                    location,
                    contract_type,
                    source,
                    url,
                    description,
                    salary,
                    seniority,
                    remote_policy,
                    skills,
                    raw_payload
                )
                VALUES (
                    %(title)s,
                    %(company)s,
                    %(location)s,
                    %(contract_type)s,
                    %(source)s,
                    %(url)s,
                    %(description)s,
                    %(salary)s,
                    %(seniority)s,
                    %(remote_policy)s,
                    %(skills)s,
                    %(raw_payload)s
                )
                RETURNING {JOB_COLUMNS}
                """,
                params,
            ).fetchone()
        if row is None:
            raise RuntimeError("Job insert did not return a row")
        return dict(row)

    def list(self, *, limit: int = 50, source: str | None = None, indexed: bool | None = None) -> list[dict[str, Any]]:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            rows = conn.execute(
                f"""
                SELECT {JOB_LIST_COLUMNS}
                FROM jobs
                LEFT JOIN (
                    SELECT job_id, count(*) AS chunk_count
                    FROM job_chunks
                    GROUP BY job_id
                ) indexed ON indexed.job_id = jobs.id
                WHERE (%(source)s::text IS NULL OR jobs.source = %(source)s)
                    AND (
                        %(indexed)s::boolean IS NULL
                        OR %(indexed)s::boolean = (COALESCE(indexed.chunk_count, 0) > 0)
                    )
                ORDER BY jobs.created_at DESC
                LIMIT %(limit)s
                """,
                {"limit": limit, "source": source, "indexed": indexed},
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, job_id: str) -> dict[str, Any] | None:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                SELECT {JOB_LIST_COLUMNS}
                FROM jobs
                LEFT JOIN (
                    SELECT job_id, count(*) AS chunk_count
                    FROM job_chunks
                    GROUP BY job_id
                ) indexed ON indexed.job_id = jobs.id
                WHERE jobs.id = %(job_id)s
                """,
                {"job_id": job_id},
            ).fetchone()
        return dict(row) if row is not None else None

    def update_description(
        self,
        job_id: str,
        *,
        description: str,
        skills: list[str],
        seniority: str | None,
        remote_policy: str | None,
        raw_payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                UPDATE jobs
                SET description = %(description)s,
                    skills = %(skills)s,
                    seniority = %(seniority)s,
                    remote_policy = %(remote_policy)s,
                    raw_payload = %(raw_payload)s,
                    updated_at = now()
                WHERE id = %(job_id)s
                RETURNING {JOB_COLUMNS}
                """,
                {
                    "job_id": job_id,
                    "description": description,
                    "skills": skills,
                    "seniority": seniority,
                    "remote_policy": remote_policy,
                    "raw_payload": Jsonb(raw_payload),
                },
            ).fetchone()
        return dict(row) if row is not None else None
