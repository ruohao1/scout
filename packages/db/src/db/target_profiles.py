from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

from .config import database_url


TARGET_PROFILE_COLUMNS = """
    id,
    name,
    summary,
    target_roles,
    target_locations,
    preferred_contract_types,
    seniority,
    remote_preference,
    must_have_keywords,
    nice_to_have_keywords,
    avoid_keywords,
    instructions,
    created_at,
    updated_at
"""

TARGET_PROFILE_EVIDENCE_COLUMNS = """
    target_profile_evidence.target_profile_id,
    target_profile_evidence.evidence_id,
    target_profile_evidence.weight,
    target_profile_evidence.note,
    target_profile_evidence.created_at,
    candidate_evidence.type AS evidence_type,
    candidate_evidence.title AS evidence_title,
    candidate_evidence.organization AS evidence_organization,
    candidate_evidence.location AS evidence_location,
    candidate_evidence.start_date AS evidence_start_date,
    candidate_evidence.end_date AS evidence_end_date,
    candidate_evidence.is_current AS evidence_is_current,
    candidate_evidence.description AS evidence_description,
    candidate_evidence.skills AS evidence_skills,
    candidate_evidence.url AS evidence_url,
    candidate_evidence.metadata AS evidence_metadata,
    candidate_evidence.source_document_id AS evidence_source_document_id,
    candidate_evidence.confidence AS evidence_confidence,
    candidate_evidence.created_at AS evidence_created_at,
    candidate_evidence.updated_at AS evidence_updated_at
"""


class TargetProfileRepository:
    def __init__(self, *, url: str | None = None) -> None:
        self.url = url or database_url()

    def create(self, profile: dict[str, Any]) -> dict[str, Any]:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                INSERT INTO target_profiles (
                    name,
                    summary,
                    target_roles,
                    target_locations,
                    preferred_contract_types,
                    seniority,
                    remote_preference,
                    must_have_keywords,
                    nice_to_have_keywords,
                    avoid_keywords,
                    instructions
                )
                VALUES (
                    %(name)s,
                    %(summary)s,
                    %(target_roles)s,
                    %(target_locations)s,
                    %(preferred_contract_types)s,
                    %(seniority)s,
                    %(remote_preference)s,
                    %(must_have_keywords)s,
                    %(nice_to_have_keywords)s,
                    %(avoid_keywords)s,
                    %(instructions)s
                )
                RETURNING {TARGET_PROFILE_COLUMNS}
                """,
                _profile_params(profile),
            ).fetchone()
        if row is None:
            raise RuntimeError("Target profile insert did not return a row")
        return dict(row)

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            rows = conn.execute(
                f"""
                SELECT {TARGET_PROFILE_COLUMNS}
                FROM target_profiles
                ORDER BY created_at DESC
                LIMIT %(limit)s
                """,
                {"limit": limit},
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, target_profile_id: str) -> dict[str, Any] | None:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                SELECT {TARGET_PROFILE_COLUMNS}
                FROM target_profiles
                WHERE id = %(target_profile_id)s
                """,
                {"target_profile_id": target_profile_id},
            ).fetchone()
        return dict(row) if row is not None else None

    def update(self, target_profile_id: str, profile: dict[str, Any]) -> dict[str, Any] | None:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                UPDATE target_profiles
                SET name = %(name)s,
                    summary = %(summary)s,
                    target_roles = %(target_roles)s,
                    target_locations = %(target_locations)s,
                    preferred_contract_types = %(preferred_contract_types)s,
                    seniority = %(seniority)s,
                    remote_preference = %(remote_preference)s,
                    must_have_keywords = %(must_have_keywords)s,
                    nice_to_have_keywords = %(nice_to_have_keywords)s,
                    avoid_keywords = %(avoid_keywords)s,
                    instructions = %(instructions)s,
                    updated_at = now()
                WHERE id = %(target_profile_id)s
                RETURNING {TARGET_PROFILE_COLUMNS}
                """,
                {**_profile_params(profile), "target_profile_id": target_profile_id},
            ).fetchone()
        return dict(row) if row is not None else None

    def delete(self, target_profile_id: str) -> bool:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                """
                DELETE FROM target_profiles
                WHERE id = %(target_profile_id)s
                RETURNING id
                """,
                {"target_profile_id": target_profile_id},
            ).fetchone()
        return row is not None


class TargetProfileEvidenceRepository:
    def __init__(self, *, url: str | None = None) -> None:
        self.url = url or database_url()

    def replace_for_profile(self, target_profile_id: str, links: list[dict[str, Any]]) -> list[dict[str, Any]]:
        inserted: list[dict[str, Any]] = []
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            conn.execute(
                "DELETE FROM target_profile_evidence WHERE target_profile_id = %(target_profile_id)s",
                {"target_profile_id": target_profile_id},
            )
            for link in links:
                row = conn.execute(
                    """
                    INSERT INTO target_profile_evidence (target_profile_id, evidence_id, weight, note)
                    VALUES (%(target_profile_id)s, %(evidence_id)s, %(weight)s, %(note)s)
                    RETURNING target_profile_id, evidence_id, weight, note, created_at
                    """,
                    {
                        "target_profile_id": target_profile_id,
                        "evidence_id": link["evidence_id"],
                        "weight": _clamp_weight(link.get("weight")),
                        "note": link.get("note"),
                    },
                ).fetchone()
                if row is None:
                    raise RuntimeError("Target profile evidence insert did not return a row")
                inserted.append(dict(row))
        return inserted

    def list_for_profile(self, target_profile_id: str) -> list[dict[str, Any]]:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            rows = conn.execute(
                f"""
                SELECT {TARGET_PROFILE_EVIDENCE_COLUMNS}
                FROM target_profile_evidence
                JOIN candidate_evidence ON candidate_evidence.id = target_profile_evidence.evidence_id
                WHERE target_profile_evidence.target_profile_id = %(target_profile_id)s
                ORDER BY target_profile_evidence.weight DESC, target_profile_evidence.created_at ASC
                """,
                {"target_profile_id": target_profile_id},
            ).fetchall()
        return [dict(row) for row in rows]


def _profile_params(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": None,
        "target_roles": [],
        "target_locations": [],
        "preferred_contract_types": [],
        "seniority": None,
        "remote_preference": None,
        "must_have_keywords": [],
        "nice_to_have_keywords": [],
        "avoid_keywords": [],
        "instructions": None,
        **profile,
    }


def _clamp_weight(value: object) -> float:
    if isinstance(value, int | float):
        return max(0.0, min(1.0, float(value)))
    return 1.0
