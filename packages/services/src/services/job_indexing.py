from __future__ import annotations

from db.job_chunks import JobChunkRepository
from db.jobs import JobRepository
from rag.embeddings import EmbeddingProvider, create_embedding_provider
from rag.job_chunking import chunk_job


class JobNotFoundError(ValueError):
    pass


def index_job(
    job_id: str,
    *,
    jobs: JobRepository | None = None,
    job_chunks: JobChunkRepository | None = None,
    embeddings: EmbeddingProvider | None = None,
) -> int:
    job_repository = jobs or JobRepository()
    chunk_repository = job_chunks or JobChunkRepository()
    embedding_provider = embeddings or create_embedding_provider()

    job = job_repository.get(job_id)
    if job is None:
        raise JobNotFoundError(f"Job not found: {job_id}")

    chunks = chunk_job(job)
    vectors = embedding_provider.embed_texts([chunk.content for chunk in chunks])
    chunk_repository.replace_for_job(job_id=job_id, chunks=chunks, embeddings=vectors)
    return len(chunks)
