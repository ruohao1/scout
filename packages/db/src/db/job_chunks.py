from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from rag.types import JobChunk

from .config import database_url


JOB_CHUNK_COLUMNS = """
    id,
    job_id,
    chunk_index,
    section,
    content,
    metadata,
    created_at
"""


class JobChunkRepository:
    def __init__(self, *, url: str | None = None) -> None:
        self.url = url or database_url()

    def replace_for_job(
        self,
        *,
        job_id: str,
        chunks: list[JobChunk],
        embeddings: list[list[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")

        with psycopg.connect(self.url) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM job_chunks WHERE job_id = %s", (job_id,))
                for chunk, embedding in zip(chunks, embeddings, strict=True):
                    cur.execute(
                        """
                        INSERT INTO job_chunks (job_id, chunk_index, section, content, embedding, metadata)
                        VALUES (%s, %s, %s, %s, %s::vector, %s)
                        """,
                        (
                            job_id,
                            chunk.chunk_index,
                            chunk.section,
                            chunk.content,
                            _vector_literal(embedding),
                            Jsonb(chunk.metadata),
                        ),
                    )

    def list_for_job(self, job_id: str) -> list[dict[str, Any]]:
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            rows = conn.execute(
                f"""
                SELECT {JOB_CHUNK_COLUMNS}
                FROM job_chunks
                WHERE job_id = %(job_id)s
                ORDER BY chunk_index ASC
                """,
                {"job_id": job_id},
            ).fetchall()
        return [dict(row) for row in rows]


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(str(value) for value in embedding) + "]"
