from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .config import database_url


IMPORT_RUN_COLUMNS = """
    id,
    provider,
    query,
    requested_count,
    created_count,
    skipped_count,
    indexed_count,
    status,
    error,
    created_at
"""


class ProviderImportRunRepository:
    def __init__(self, *, url: str | None = None) -> None:
        self.url = url or database_url()

    def create(self, run: dict[str, Any]) -> dict[str, Any]:
        params = {**run, "query": Jsonb(run.get("query") or {})}
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                INSERT INTO provider_import_runs (
                    provider,
                    query,
                    requested_count,
                    created_count,
                    skipped_count,
                    indexed_count,
                    status,
                    error
                )
                VALUES (
                    %(provider)s,
                    %(query)s,
                    %(requested_count)s,
                    %(created_count)s,
                    %(skipped_count)s,
                    %(indexed_count)s,
                    %(status)s,
                    %(error)s
                )
                RETURNING {IMPORT_RUN_COLUMNS}
                """,
                params,
            ).fetchone()
        if row is None:
            raise RuntimeError("Provider import run insert did not return a row")
        return dict(row)

    def list(self, *, provider: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            rows = conn.execute(
                f"""
                SELECT {IMPORT_RUN_COLUMNS}
                FROM provider_import_runs
                WHERE (%(provider)s::text IS NULL OR provider = %(provider)s)
                ORDER BY created_at DESC
                LIMIT %(limit)s
                """,
                {"provider": provider, "limit": limit},
            ).fetchall()
        return [dict(row) for row in rows]
