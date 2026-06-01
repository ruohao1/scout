from __future__ import annotations

import json

import psycopg
from psycopg import sql
from rag.types import Chunk, ScoredChunk

from .config import database_url


class PgVectorChunkStore:
    def __init__(self, *, url: str | None = None, table: str = "rag_chunks", dimensions: int = 1536) -> None:
        self.url = url or database_url()
        self.table = table
        self.dimensions = dimensions
        if self.dimensions <= 0:
            raise ValueError("dimensions must be greater than 0")

    def setup(self) -> None:
        with psycopg.connect(self.url) as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(
                sql.SQL(
                    """
                CREATE TABLE IF NOT EXISTS {} (
                    id text PRIMARY KEY,
                    document_id text NOT NULL,
                    text text NOT NULL,
                    metadata jsonb NOT NULL DEFAULT '{{}}'::jsonb,
                    embedding vector({}) NOT NULL
                )
                """
                ).format(sql.Identifier(self.table), sql.SQL(str(self.dimensions)))
            )

    def upsert_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")

        with psycopg.connect(self.url) as conn:
            with conn.cursor() as cur:
                for chunk, embedding in zip(chunks, embeddings, strict=True):
                    cur.execute(
                        sql.SQL(
                            """
                        INSERT INTO {} (id, document_id, text, metadata, embedding)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            document_id = EXCLUDED.document_id,
                            text = EXCLUDED.text,
                            metadata = EXCLUDED.metadata,
                            embedding = EXCLUDED.embedding
                        """,
                        ).format(sql.Identifier(self.table)),
                        (chunk.id, chunk.document_id, chunk.text, json.dumps(chunk.metadata), _vector_literal(embedding)),
                    )

    def search(self, embedding: list[float], *, limit: int = 5) -> list[ScoredChunk]:
        with psycopg.connect(self.url) as conn:
            rows = conn.execute(
                sql.SQL(
                    """
                SELECT id, document_id, text, metadata, 1 - (embedding <=> %s::vector) AS score
                FROM {}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                ).format(sql.Identifier(self.table)),
                (_vector_literal(embedding), _vector_literal(embedding), limit),
            ).fetchall()

        return [
            ScoredChunk(
                chunk=Chunk(id=row[0], document_id=row[1], text=row[2], metadata=dict(row[3] or {})),
                score=float(row[4]),
            )
            for row in rows
        ]


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(str(value) for value in embedding) + "]"
