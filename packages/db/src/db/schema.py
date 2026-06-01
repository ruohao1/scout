from __future__ import annotations

import psycopg

from .config import database_url


def setup_database(*, url: str | None = None) -> None:
    with psycopg.connect(url or database_url()) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                title text NOT NULL,
                company text,
                location text,
                contract_type text,
                source text,
                url text UNIQUE,
                description text NOT NULL,
                salary text,
                seniority text,
                remote_policy text,
                skills text[] NOT NULL DEFAULT '{}',
                raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_chunks (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                job_id uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                chunk_index integer NOT NULL,
                section text,
                content text NOT NULL,
                embedding vector(1536),
                metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
                created_at timestamptz NOT NULL DEFAULT now(),
                UNIQUE (job_id, chunk_index)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_profiles (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                name text,
                cv_text text NOT NULL,
                target_roles text[] NOT NULL DEFAULT '{}',
                target_locations text[] NOT NULL DEFAULT '{}',
                skills text[] NOT NULL DEFAULT '{}',
                seniority text,
                preferred_contract_types text[] NOT NULL DEFAULT '{}',
                remote_preference text,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS jobs_location_idx ON jobs (location)")
        conn.execute("CREATE INDEX IF NOT EXISTS jobs_contract_type_idx ON jobs (contract_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS jobs_seniority_idx ON jobs (seniority)")
        conn.execute("CREATE INDEX IF NOT EXISTS jobs_remote_policy_idx ON jobs (remote_policy)")
        conn.execute("CREATE INDEX IF NOT EXISTS jobs_skills_gin_idx ON jobs USING gin (skills)")
        conn.execute("CREATE INDEX IF NOT EXISTS jobs_created_at_idx ON jobs (created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS job_chunks_job_id_idx ON job_chunks (job_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS job_chunks_section_idx ON job_chunks (section)")
        conn.execute("CREATE INDEX IF NOT EXISTS user_profiles_skills_gin_idx ON user_profiles USING gin (skills)")
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS user_profiles_target_locations_gin_idx
            ON user_profiles USING gin (target_locations)
            """
        )
