from __future__ import annotations

from typing import Protocol

from .types import Chunk, ScoredChunk


class ChunkStore(Protocol):
    def upsert_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        """Persist chunks and their embedding vectors."""

    def search(self, embedding: list[float], *, limit: int = 5) -> list[ScoredChunk]:
        """Return the nearest chunks for an embedding vector."""
