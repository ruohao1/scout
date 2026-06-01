from __future__ import annotations

from .chunking import chunk_text
from .embeddings import EmbeddingProvider
from .store import ChunkStore
from .types import Document, ScoredChunk


class Retriever:
    def __init__(self, *, embeddings: EmbeddingProvider, store: ChunkStore) -> None:
        self.embeddings = embeddings
        self.store = store

    def add_documents(self, documents: list[Document], *, chunk_size: int = 1_000, overlap: int = 150) -> None:
        chunks = [chunk for document in documents for chunk in chunk_text(document, chunk_size=chunk_size, overlap=overlap)]
        vectors = self.embeddings.embed_texts([chunk.text for chunk in chunks])
        self.store.upsert_chunks(chunks, vectors)

    def search(self, query: str, *, limit: int = 5) -> list[ScoredChunk]:
        vector = self.embeddings.embed_texts([query])[0]
        return self.store.search(vector, limit=limit)
