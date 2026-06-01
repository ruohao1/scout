from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

from .config import database_url


PROFILE_COLUMNS = """
    id,
    name,
    cv_text,
    target_roles,
    target_locations,
    skills,
    seniority,
    preferred_contract_types,
    remote_preference,
    created_at,
    updated_at
"""


class ProfileRepository:
    def __init__(self, *, url: str | None = None) -> None:
        self.url = url or database_url()

    def create(self, profile: dict[str, Any]) -> dict[str, Any]:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                INSERT INTO user_profiles (
                    name,
                    cv_text,
                    target_roles,
                    target_locations,
                    skills,
                    seniority,
                    preferred_contract_types,
                    remote_preference
                )
                VALUES (
                    %(name)s,
                    %(cv_text)s,
                    %(target_roles)s,
                    %(target_locations)s,
                    %(skills)s,
                    %(seniority)s,
                    %(preferred_contract_types)s,
                    %(remote_preference)s
                )
                RETURNING {PROFILE_COLUMNS}
                """,
                profile,
            ).fetchone()
        if row is None:
            raise RuntimeError("Profile insert did not return a row")
        return dict(row)

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            rows = conn.execute(
                f"""
                SELECT {PROFILE_COLUMNS}
                FROM user_profiles
                ORDER BY created_at DESC
                LIMIT %(limit)s
                """,
                {"limit": limit},
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, profile_id: str) -> dict[str, Any] | None:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                SELECT {PROFILE_COLUMNS}
                FROM user_profiles
                WHERE id = %(profile_id)s
                """,
                {"profile_id": profile_id},
            ).fetchone()
        return dict(row) if row is not None else None
