from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .config import database_url


CANDIDATE_COLUMNS = """
    id,
    display_name,
    headline,
    summary,
    created_at,
    updated_at
"""

DOCUMENT_COLUMNS = """
    id,
    filename,
    content_type,
    file_data,
    text,
    source,
    created_at,
    updated_at
"""

EVIDENCE_COLUMNS = """
    id,
    type,
    title,
    organization,
    location,
    start_date,
    end_date,
    is_current,
    description,
    skills,
    url,
    metadata,
    source_document_id,
    confidence,
    created_at,
    updated_at
"""

EVIDENCE_CHUNK_COLUMNS = """
    id,
    evidence_id,
    chunk_index,
    content,
    metadata,
    created_at
"""


class CandidateRepository:
    def __init__(self, *, url: str | None = None) -> None:
        self.url = url or database_url()

    def get(self) -> dict[str, Any] | None:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                SELECT {CANDIDATE_COLUMNS}
                FROM candidate
                ORDER BY created_at DESC
                LIMIT 1
                """
            ).fetchone()
        return dict(row) if row is not None else None

    def upsert(self, candidate: dict[str, Any]) -> dict[str, Any]:
        existing = self.get()
        params = _candidate_params(candidate, existing=existing)
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            if existing is None:
                row = conn.execute(
                    f"""
                    INSERT INTO candidate (display_name, headline, summary)
                    VALUES (%(display_name)s, %(headline)s, %(summary)s)
                    RETURNING {CANDIDATE_COLUMNS}
                    """,
                    params,
                ).fetchone()
            else:
                row = conn.execute(
                    f"""
                    UPDATE candidate
                    SET display_name = %(display_name)s,
                        headline = %(headline)s,
                        summary = %(summary)s,
                        updated_at = now()
                    WHERE id = %(candidate_id)s
                    RETURNING {CANDIDATE_COLUMNS}
                    """,
                    {**params, "candidate_id": existing["id"]},
                ).fetchone()
        if row is None:
            raise RuntimeError("Candidate upsert did not return a row")
        return dict(row)


class CandidateDocumentRepository:
    def __init__(self, *, url: str | None = None) -> None:
        self.url = url or database_url()

    def create(self, document: dict[str, Any]) -> dict[str, Any]:
        params = {
            "filename": None,
            "content_type": None,
            "file_data": None,
            "source": "upload",
            **document,
        }
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                INSERT INTO candidate_documents (filename, content_type, file_data, text, source)
                VALUES (%(filename)s, %(content_type)s, %(file_data)s, %(text)s, %(source)s)
                RETURNING {DOCUMENT_COLUMNS}
                """,
                params,
            ).fetchone()
        if row is None:
            raise RuntimeError("Candidate document insert did not return a row")
        return dict(row)

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            rows = conn.execute(
                f"""
                SELECT {DOCUMENT_COLUMNS}
                FROM candidate_documents
                ORDER BY created_at DESC
                LIMIT %(limit)s
                """,
                {"limit": limit},
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, document_id: str) -> dict[str, Any] | None:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                SELECT {DOCUMENT_COLUMNS}
                FROM candidate_documents
                WHERE id = %(document_id)s
                """,
                {"document_id": document_id},
            ).fetchone()
        return dict(row) if row is not None else None


class CandidateEvidenceRepository:
    def __init__(self, *, url: str | None = None) -> None:
        self.url = url or database_url()

    def create(self, evidence: dict[str, Any]) -> dict[str, Any]:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                INSERT INTO candidate_evidence (
                    type,
                    title,
                    organization,
                    location,
                    start_date,
                    end_date,
                    is_current,
                    description,
                    skills,
                    url,
                    metadata,
                    source_document_id,
                    confidence
                )
                VALUES (
                    %(type)s,
                    %(title)s,
                    %(organization)s,
                    %(location)s,
                    %(start_date)s,
                    %(end_date)s,
                    %(is_current)s,
                    %(description)s,
                    %(skills)s,
                    %(url)s,
                    %(metadata)s,
                    %(source_document_id)s,
                    %(confidence)s
                )
                RETURNING {EVIDENCE_COLUMNS}
                """,
                _evidence_params(evidence),
            ).fetchone()
        if row is None:
            raise RuntimeError("Candidate evidence insert did not return a row")
        return dict(row)

    def list(self, *, evidence_type: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            rows = conn.execute(
                f"""
                SELECT {EVIDENCE_COLUMNS}
                FROM candidate_evidence
                WHERE (%(evidence_type)s::text IS NULL OR type = %(evidence_type)s)
                ORDER BY created_at DESC
                LIMIT %(limit)s
                """,
                {"evidence_type": evidence_type, "limit": limit},
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, evidence_id: str) -> dict[str, Any] | None:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                SELECT {EVIDENCE_COLUMNS}
                FROM candidate_evidence
                WHERE id = %(evidence_id)s
                """,
                {"evidence_id": evidence_id},
            ).fetchone()
        return dict(row) if row is not None else None

    def update(self, evidence_id: str, evidence: dict[str, Any]) -> dict[str, Any] | None:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                f"""
                UPDATE candidate_evidence
                SET type = %(type)s,
                    title = %(title)s,
                    organization = %(organization)s,
                    location = %(location)s,
                    start_date = %(start_date)s,
                    end_date = %(end_date)s,
                    is_current = %(is_current)s,
                    description = %(description)s,
                    skills = %(skills)s,
                    url = %(url)s,
                    metadata = %(metadata)s,
                    source_document_id = %(source_document_id)s,
                    confidence = %(confidence)s,
                    updated_at = now()
                WHERE id = %(evidence_id)s
                RETURNING {EVIDENCE_COLUMNS}
                """,
                {**_evidence_params(evidence), "evidence_id": evidence_id},
            ).fetchone()
        return dict(row) if row is not None else None

    def delete(self, evidence_id: str) -> bool:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute(
                """
                DELETE FROM candidate_evidence
                WHERE id = %(evidence_id)s
                RETURNING id
                """,
                {"evidence_id": evidence_id},
            ).fetchone()
        return row is not None

    def replace_for_document(self, document_id: str, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        inserted: list[dict[str, Any]] = []
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            conn.execute("DELETE FROM candidate_evidence WHERE source_document_id = %(document_id)s", {"document_id": document_id})
            for item in evidence:
                row = conn.execute(
                    f"""
                    INSERT INTO candidate_evidence (
                        type,
                        title,
                        organization,
                        location,
                        start_date,
                        end_date,
                        is_current,
                        description,
                        skills,
                        url,
                        metadata,
                        source_document_id,
                        confidence
                    )
                    VALUES (
                        %(type)s,
                        %(title)s,
                        %(organization)s,
                        %(location)s,
                        %(start_date)s,
                        %(end_date)s,
                        %(is_current)s,
                        %(description)s,
                        %(skills)s,
                        %(url)s,
                        %(metadata)s,
                        %(source_document_id)s,
                        %(confidence)s
                    )
                    RETURNING {EVIDENCE_COLUMNS}
                    """,
                    _evidence_params({**item, "source_document_id": document_id}),
                ).fetchone()
                if row is None:
                    raise RuntimeError("Candidate evidence insert did not return a row")
                inserted.append(dict(row))
        return inserted


class CandidateEvidenceChunkRepository:
    def __init__(self, *, url: str | None = None) -> None:
        self.url = url or database_url()

    def replace_for_evidence(
        self,
        *,
        evidence_id: str,
        chunks: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")

        with psycopg.connect(self.url) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM candidate_evidence_chunks WHERE evidence_id = %s", (evidence_id,))
                for chunk, embedding in zip(chunks, embeddings, strict=True):
                    cur.execute(
                        """
                        INSERT INTO candidate_evidence_chunks (evidence_id, chunk_index, content, embedding, metadata)
                        VALUES (%s, %s, %s, %s::vector, %s)
                        """,
                        (
                            evidence_id,
                            chunk["chunk_index"],
                            chunk["content"],
                            _vector_literal(embedding),
                            Jsonb(chunk.get("metadata") or {}),
                        ),
                    )

    def list_for_evidence(self, evidence_id: str) -> list[dict[str, Any]]:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            rows = conn.execute(
                f"""
                SELECT {EVIDENCE_CHUNK_COLUMNS}
                FROM candidate_evidence_chunks
                WHERE evidence_id = %(evidence_id)s
                ORDER BY chunk_index ASC
                """,
                {"evidence_id": evidence_id},
            ).fetchall()
        return [dict(row) for row in rows]

    def search_chunks(self, *, embedding: list[float], limit: int = 8) -> list[dict[str, Any]]:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            rows = conn.execute(
                f"""
                SELECT
                    candidate_evidence_chunks.id,
                    candidate_evidence_chunks.evidence_id,
                    candidate_evidence_chunks.chunk_index,
                    candidate_evidence_chunks.content,
                    candidate_evidence_chunks.metadata,
                    1 - (candidate_evidence_chunks.embedding <=> %(embedding)s::vector) AS score,
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
                    candidate_evidence.source_document_id AS evidence_source_document_id,
                    candidate_evidence.confidence AS evidence_confidence
                FROM candidate_evidence_chunks
                JOIN candidate_evidence ON candidate_evidence.id = candidate_evidence_chunks.evidence_id
                WHERE candidate_evidence_chunks.embedding IS NOT NULL
                ORDER BY candidate_evidence_chunks.embedding <=> %(embedding)s::vector
                LIMIT %(limit)s
                """,
                {"embedding": _vector_literal(embedding), "limit": limit},
            ).fetchall()
        return [dict(row) for row in rows]


def _candidate_params(candidate: dict[str, Any], *, existing: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "display_name": candidate.get("display_name", existing.get("display_name") if existing else None),
        "headline": candidate.get("headline", existing.get("headline") if existing else None),
        "summary": candidate.get("summary", existing.get("summary") if existing else None),
    }


def _evidence_params(evidence: dict[str, Any]) -> dict[str, Any]:
    params = {
        "organization": None,
        "location": None,
        "start_date": None,
        "end_date": None,
        "is_current": False,
        "description": None,
        "skills": [],
        "url": None,
        "metadata": {},
        "source_document_id": None,
        "confidence": 1.0,
        **evidence,
    }
    params["metadata"] = Jsonb(params.get("metadata") or {})
    return params


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(str(value) for value in embedding) + "]"
