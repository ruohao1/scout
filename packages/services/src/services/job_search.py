from __future__ import annotations

from db.search import JobSearchRepository
from rag.embeddings import EmbeddingProvider, create_embedding_provider
from rag.types import JobSearchFilters, JobSearchResult


class EmptySearchQueryError(ValueError):
    pass


def search_jobs(
    query: str,
    *,
    filters: JobSearchFilters | None = None,
    limit: int = 10,
    embeddings: EmbeddingProvider | None = None,
    search: JobSearchRepository | None = None,
) -> list[JobSearchResult]:
    query = query.strip()
    if not query:
        raise EmptySearchQueryError("Search query must not be empty")

    embedding_provider = embeddings or create_embedding_provider()
    search_repository = search or JobSearchRepository()

    vector = embedding_provider.embed_texts([query])[0]
    return search_repository.search_chunks(
        embedding=vector,
        filters=filters or JobSearchFilters(),
        limit=limit,
    )
