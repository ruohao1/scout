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
                cv_filename text,
                cv_content_type text,
                cv_file bytea,
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
        conn.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS cv_filename text")
        conn.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS cv_content_type text")
        conn.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS cv_file bytea")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profile_experiences (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                profile_id uuid NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
                title text NOT NULL,
                company text,
                location text,
                start_date text,
                end_date text,
                is_current boolean NOT NULL DEFAULT false,
                description text,
                skills text[] NOT NULL DEFAULT '{}',
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profile_projects (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                profile_id uuid NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
                name text NOT NULL,
                role text,
                url text,
                description text,
                skills text[] NOT NULL DEFAULT '{}',
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profile_skills (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                profile_id uuid NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
                name text NOT NULL,
                category text,
                proficiency text,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                display_name text,
                headline text,
                summary text,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_documents (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                filename text,
                content_type text,
                file_data bytea,
                text text NOT NULL,
                source text NOT NULL DEFAULT 'upload',
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_evidence (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                type text NOT NULL,
                title text NOT NULL,
                organization text,
                location text,
                start_date text,
                end_date text,
                is_current boolean NOT NULL DEFAULT false,
                description text,
                skills text[] NOT NULL DEFAULT '{}',
                url text,
                metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
                source_document_id uuid REFERENCES candidate_documents(id) ON DELETE SET NULL,
                confidence double precision NOT NULL DEFAULT 1.0,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now(),
                CHECK (type IN ('experience', 'project', 'skill', 'education', 'certification', 'language', 'interest', 'document_note')),
                CHECK (confidence >= 0.0 AND confidence <= 1.0)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_evidence_chunks (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                evidence_id uuid NOT NULL REFERENCES candidate_evidence(id) ON DELETE CASCADE,
                chunk_index integer NOT NULL,
                content text NOT NULL,
                embedding vector(1536),
                metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
                created_at timestamptz NOT NULL DEFAULT now(),
                UNIQUE (evidence_id, chunk_index)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS target_profiles (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                name text NOT NULL,
                summary text,
                target_roles text[] NOT NULL DEFAULT '{}',
                target_locations text[] NOT NULL DEFAULT '{}',
                preferred_contract_types text[] NOT NULL DEFAULT '{}',
                seniority text,
                remote_preference text,
                must_have_keywords text[] NOT NULL DEFAULT '{}',
                nice_to_have_keywords text[] NOT NULL DEFAULT '{}',
                avoid_keywords text[] NOT NULL DEFAULT '{}',
                instructions text,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS target_profile_evidence (
                target_profile_id uuid NOT NULL REFERENCES target_profiles(id) ON DELETE CASCADE,
                evidence_id uuid NOT NULL REFERENCES candidate_evidence(id) ON DELETE CASCADE,
                weight double precision NOT NULL DEFAULT 1.0,
                note text,
                created_at timestamptz NOT NULL DEFAULT now(),
                PRIMARY KEY (target_profile_id, evidence_id),
                CHECK (weight >= 0.0 AND weight <= 1.0)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS provider_import_runs (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                provider text NOT NULL,
                query jsonb NOT NULL DEFAULT '{}'::jsonb,
                requested_count integer NOT NULL DEFAULT 0,
                created_count integer NOT NULL DEFAULT 0,
                skipped_count integer NOT NULL DEFAULT 0,
                indexed_count integer NOT NULL DEFAULT 0,
                status text NOT NULL,
                error text,
                created_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key text PRIMARY KEY,
                value jsonb NOT NULL,
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS jobs_location_idx ON jobs (location)")
        conn.execute("CREATE INDEX IF NOT EXISTS jobs_contract_type_idx ON jobs (contract_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS jobs_seniority_idx ON jobs (seniority)")
        conn.execute("CREATE INDEX IF NOT EXISTS jobs_remote_policy_idx ON jobs (remote_policy)")
        conn.execute("CREATE INDEX IF NOT EXISTS jobs_skills_gin_idx ON jobs USING gin (skills)")
        conn.execute("CREATE INDEX IF NOT EXISTS jobs_source_idx ON jobs (source)")
        conn.execute("CREATE INDEX IF NOT EXISTS jobs_created_at_idx ON jobs (created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS job_chunks_job_id_idx ON job_chunks (job_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS job_chunks_section_idx ON job_chunks (section)")
        conn.execute("CREATE INDEX IF NOT EXISTS profile_experiences_profile_id_idx ON profile_experiences (profile_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS profile_experiences_created_at_idx ON profile_experiences (created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS profile_projects_profile_id_idx ON profile_projects (profile_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS profile_projects_created_at_idx ON profile_projects (created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS profile_skills_profile_id_idx ON profile_skills (profile_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS profile_skills_created_at_idx ON profile_skills (created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS candidate_evidence_type_idx ON candidate_evidence (type)")
        conn.execute("CREATE INDEX IF NOT EXISTS candidate_evidence_source_document_idx ON candidate_evidence (source_document_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS candidate_evidence_skills_gin_idx ON candidate_evidence USING gin (skills)")
        conn.execute("CREATE INDEX IF NOT EXISTS candidate_evidence_chunks_evidence_id_idx ON candidate_evidence_chunks (evidence_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS target_profiles_created_at_idx ON target_profiles (created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS target_profile_evidence_evidence_id_idx ON target_profile_evidence (evidence_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS provider_import_runs_provider_idx ON provider_import_runs (provider)")
        conn.execute("CREATE INDEX IF NOT EXISTS provider_import_runs_created_at_idx ON provider_import_runs (created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS app_settings_updated_at_idx ON app_settings (updated_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS user_profiles_skills_gin_idx ON user_profiles USING gin (skills)")
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS user_profiles_target_locations_gin_idx
            ON user_profiles USING gin (target_locations)
            """
        )
