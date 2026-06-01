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

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            rows = conn.execute(
                f"""
                SELECT {JOB_COLUMNS}
                FROM jobs
                ORDER BY created_at DESC
                LIMIT %(limit)s
                """,
                {"limit": limit},
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, job_id: str) -> dict[str, Any] | None:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                SELECT {JOB_COLUMNS}
                FROM jobs
                WHERE id = %(job_id)s
                """,
                {"job_id": job_id},
            ).fetchone()
        return dict(row) if row is not None else None
