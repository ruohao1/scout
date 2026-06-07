from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

from .config import database_url


PROFILE_COLUMNS = """
    id,
    name,
    cv_text,
    cv_filename,
    cv_content_type,
    (cv_file IS NOT NULL) AS has_cv_file,
    target_roles,
    target_locations,
    skills,
    seniority,
    preferred_contract_types,
    remote_preference,
    created_at,
    updated_at
"""

PROFILE_LIST_COLUMNS = """
    id,
    name,
    left(cv_text, 500) AS cv_preview,
    cv_filename,
    cv_content_type,
    (cv_file IS NOT NULL) AS has_cv_file,
    target_roles,
    target_locations,
    skills,
    seniority,
    preferred_contract_types,
    remote_preference,
    created_at,
    updated_at
"""

PROFILE_EXPERIENCE_COLUMNS = """
    id,
    profile_id,
    title,
    company,
    location,
    start_date,
    end_date,
    is_current,
    description,
    skills,
    created_at,
    updated_at
"""

PROFILE_PROJECT_COLUMNS = """
    id,
    profile_id,
    name,
    role,
    url,
    description,
    skills,
    created_at,
    updated_at
"""

PROFILE_SKILL_COLUMNS = """
    id,
    profile_id,
    name,
    category,
    proficiency,
    created_at,
    updated_at
"""


class ProfileRepository:
    def __init__(self, *, url: str | None = None) -> None:
        self.url = url or database_url()

    def create(self, profile: dict[str, Any]) -> dict[str, Any]:
        params = {
            "cv_filename": None,
            "cv_content_type": None,
            "cv_file": None,
            **profile,
        }
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                INSERT INTO user_profiles (
                    name,
                    cv_text,
                    cv_filename,
                    cv_content_type,
                    cv_file,
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
                    %(cv_filename)s,
                    %(cv_content_type)s,
                    %(cv_file)s,
                    %(target_roles)s,
                    %(target_locations)s,
                    %(skills)s,
                    %(seniority)s,
                    %(preferred_contract_types)s,
                    %(remote_preference)s
                )
                RETURNING {PROFILE_COLUMNS}
                """,
                params,
            ).fetchone()
        if row is None:
            raise RuntimeError("Profile insert did not return a row")
        return dict(row)

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            rows = conn.execute(
                f"""
                SELECT {PROFILE_LIST_COLUMNS}
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

    def get_cv_file(self, profile_id: str) -> dict[str, Any] | None:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                """
                SELECT cv_filename, cv_content_type, cv_file
                FROM user_profiles
                WHERE id = %(profile_id)s AND cv_file IS NOT NULL
                """,
                {"profile_id": profile_id},
            ).fetchone()
        return dict(row) if row is not None else None

    def attach_cv_file(self, profile_id: str, *, filename: str, content_type: str, data: bytes, cv_text: str) -> dict[str, Any] | None:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                UPDATE user_profiles
                SET cv_text = %(cv_text)s,
                    cv_filename = %(filename)s,
                    cv_content_type = %(content_type)s,
                    cv_file = %(data)s,
                    updated_at = now()
                WHERE id = %(profile_id)s
                RETURNING {PROFILE_COLUMNS}
                """,
                {
                    "profile_id": profile_id,
                    "filename": filename,
                    "content_type": content_type,
                    "data": data,
                    "cv_text": cv_text,
                },
            ).fetchone()
        return dict(row) if row is not None else None

    def get_with_enrichment(self, profile_id: str) -> dict[str, Any] | None:
        profile = self.get(profile_id)
        if profile is None:
            return None
        enrichment = self.list_enrichment(profile_id)
        profile.update(enrichment)
        return profile

    def list_enrichment(self, profile_id: str) -> dict[str, list[dict[str, Any]]]:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            experiences = conn.execute(
                f"""
                SELECT {PROFILE_EXPERIENCE_COLUMNS}
                FROM profile_experiences
                WHERE profile_id = %(profile_id)s
                ORDER BY created_at DESC
                """,
                {"profile_id": profile_id},
            ).fetchall()
            projects = conn.execute(
                f"""
                SELECT {PROFILE_PROJECT_COLUMNS}
                FROM profile_projects
                WHERE profile_id = %(profile_id)s
                ORDER BY created_at DESC
                """,
                {"profile_id": profile_id},
            ).fetchall()
            skills = conn.execute(
                f"""
                SELECT {PROFILE_SKILL_COLUMNS}
                FROM profile_skills
                WHERE profile_id = %(profile_id)s
                ORDER BY created_at DESC
                """,
                {"profile_id": profile_id},
            ).fetchall()
        return {
            "experiences": [dict(row) for row in experiences],
            "projects": [dict(row) for row in projects],
            "enriched_skills": [dict(row) for row in skills],
        }

    def replace_enrichment(
        self,
        profile_id: str,
        *,
        experiences: list[dict[str, Any]],
        projects: list[dict[str, Any]],
        skills: list[dict[str, Any]],
    ) -> None:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            conn.execute("DELETE FROM profile_experiences WHERE profile_id = %(profile_id)s", {"profile_id": profile_id})
            conn.execute("DELETE FROM profile_projects WHERE profile_id = %(profile_id)s", {"profile_id": profile_id})
            conn.execute("DELETE FROM profile_skills WHERE profile_id = %(profile_id)s", {"profile_id": profile_id})

            for experience in experiences:
                conn.execute(
                    """
                    INSERT INTO profile_experiences (
                        profile_id,
                        title,
                        company,
                        location,
                        start_date,
                        end_date,
                        is_current,
                        description,
                        skills
                    )
                    VALUES (
                        %(profile_id)s,
                        %(title)s,
                        %(company)s,
                        %(location)s,
                        %(start_date)s,
                        %(end_date)s,
                        %(is_current)s,
                        %(description)s,
                        %(skills)s
                    )
                    """,
                    {**experience, "profile_id": profile_id},
                )

            for project in projects:
                conn.execute(
                    """
                    INSERT INTO profile_projects (
                        profile_id,
                        name,
                        role,
                        url,
                        description,
                        skills
                    )
                    VALUES (
                        %(profile_id)s,
                        %(name)s,
                        %(role)s,
                        %(url)s,
                        %(description)s,
                        %(skills)s
                    )
                    """,
                    {**project, "profile_id": profile_id},
                )

            for skill in skills:
                conn.execute(
                    """
                    INSERT INTO profile_skills (
                        profile_id,
                        name,
                        category,
                        proficiency
                    )
                    VALUES (
                        %(profile_id)s,
                        %(name)s,
                        %(category)s,
                        %(proficiency)s
                    )
                    """,
                    {**skill, "profile_id": profile_id},
                )

    def create_experience(self, profile_id: str, experience: dict[str, Any]) -> dict[str, Any]:
        params = {**experience, "profile_id": profile_id}
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                INSERT INTO profile_experiences (
                    profile_id,
                    title,
                    company,
                    location,
                    start_date,
                    end_date,
                    is_current,
                    description,
                    skills
                )
                VALUES (
                    %(profile_id)s,
                    %(title)s,
                    %(company)s,
                    %(location)s,
                    %(start_date)s,
                    %(end_date)s,
                    %(is_current)s,
                    %(description)s,
                    %(skills)s
                )
                RETURNING {PROFILE_EXPERIENCE_COLUMNS}
                """,
                params,
            ).fetchone()
        if row is None:
            raise RuntimeError("Profile experience insert did not return a row")
        return dict(row)

    def update_experience(self, profile_id: str, experience_id: str, experience: dict[str, Any]) -> dict[str, Any] | None:
        params = {**experience, "profile_id": profile_id, "experience_id": experience_id}
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                UPDATE profile_experiences
                SET title = %(title)s,
                    company = %(company)s,
                    location = %(location)s,
                    start_date = %(start_date)s,
                    end_date = %(end_date)s,
                    is_current = %(is_current)s,
                    description = %(description)s,
                    skills = %(skills)s,
                    updated_at = now()
                WHERE id = %(experience_id)s AND profile_id = %(profile_id)s
                RETURNING {PROFILE_EXPERIENCE_COLUMNS}
                """,
                params,
            ).fetchone()
        return dict(row) if row is not None else None

    def delete_experience(self, profile_id: str, experience_id: str) -> bool:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                """
                DELETE FROM profile_experiences
                WHERE id = %(experience_id)s AND profile_id = %(profile_id)s
                RETURNING id
                """,
                {"profile_id": profile_id, "experience_id": experience_id},
            ).fetchone()
        return row is not None

    def create_project(self, profile_id: str, project: dict[str, Any]) -> dict[str, Any]:
        params = {**project, "profile_id": profile_id}
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                INSERT INTO profile_projects (
                    profile_id,
                    name,
                    role,
                    url,
                    description,
                    skills
                )
                VALUES (
                    %(profile_id)s,
                    %(name)s,
                    %(role)s,
                    %(url)s,
                    %(description)s,
                    %(skills)s
                )
                RETURNING {PROFILE_PROJECT_COLUMNS}
                """,
                params,
            ).fetchone()
        if row is None:
            raise RuntimeError("Profile project insert did not return a row")
        return dict(row)

    def update_project(self, profile_id: str, project_id: str, project: dict[str, Any]) -> dict[str, Any] | None:
        params = {**project, "profile_id": profile_id, "project_id": project_id}
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                UPDATE profile_projects
                SET name = %(name)s,
                    role = %(role)s,
                    url = %(url)s,
                    description = %(description)s,
                    skills = %(skills)s,
                    updated_at = now()
                WHERE id = %(project_id)s AND profile_id = %(profile_id)s
                RETURNING {PROFILE_PROJECT_COLUMNS}
                """,
                params,
            ).fetchone()
        return dict(row) if row is not None else None

    def delete_project(self, profile_id: str, project_id: str) -> bool:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                """
                DELETE FROM profile_projects
                WHERE id = %(project_id)s AND profile_id = %(profile_id)s
                RETURNING id
                """,
                {"profile_id": profile_id, "project_id": project_id},
            ).fetchone()
        return row is not None

    def create_skill(self, profile_id: str, skill: dict[str, Any]) -> dict[str, Any]:
        params = {**skill, "profile_id": profile_id}
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                INSERT INTO profile_skills (
                    profile_id,
                    name,
                    category,
                    proficiency
                )
                VALUES (
                    %(profile_id)s,
                    %(name)s,
                    %(category)s,
                    %(proficiency)s
                )
                RETURNING {PROFILE_SKILL_COLUMNS}
                """,
                params,
            ).fetchone()
        if row is None:
            raise RuntimeError("Profile skill insert did not return a row")
        return dict(row)

    def update_skill(self, profile_id: str, skill_id: str, skill: dict[str, Any]) -> dict[str, Any] | None:
        params = {**skill, "profile_id": profile_id, "skill_id": skill_id}
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                UPDATE profile_skills
                SET name = %(name)s,
                    category = %(category)s,
                    proficiency = %(proficiency)s,
                    updated_at = now()
                WHERE id = %(skill_id)s AND profile_id = %(profile_id)s
                RETURNING {PROFILE_SKILL_COLUMNS}
                """,
                params,
            ).fetchone()
        return dict(row) if row is not None else None

    def delete_skill(self, profile_id: str, skill_id: str) -> bool:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                """
                DELETE FROM profile_skills
                WHERE id = %(skill_id)s AND profile_id = %(profile_id)s
                RETURNING id
                """,
                {"profile_id": profile_id, "skill_id": skill_id},
            ).fetchone()
        return row is not None
