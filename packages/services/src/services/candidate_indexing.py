from __future__ import annotations

from db.candidate import CandidateEvidenceChunkRepository, CandidateEvidenceRepository
from rag.candidate import candidate_evidence_metadata, candidate_evidence_text
from rag.embeddings import EmbeddingProvider, create_embedding_provider


class CandidateEvidenceNotFoundError(ValueError):
    pass


def index_candidate_evidence(
    evidence_id: str,
    *,
    evidence: CandidateEvidenceRepository | None = None,
    chunks: CandidateEvidenceChunkRepository | None = None,
    embeddings: EmbeddingProvider | None = None,
) -> int:
    evidence_repository = evidence or CandidateEvidenceRepository()
    chunk_repository = chunks or CandidateEvidenceChunkRepository()
    embedding_provider = embeddings or create_embedding_provider()

    item = evidence_repository.get(evidence_id)
    if item is None:
        raise CandidateEvidenceNotFoundError(f"Candidate evidence not found: {evidence_id}")

    content = candidate_evidence_text(item)
    chunk = {"chunk_index": 0, "content": content, "metadata": candidate_evidence_metadata(item)}
    vectors = embedding_provider.embed_texts([content])
    chunk_repository.replace_for_evidence(evidence_id=evidence_id, chunks=[chunk], embeddings=vectors)
    return 1


def reindex_all_candidate_evidence(
    *,
    evidence: CandidateEvidenceRepository | None = None,
    embeddings: EmbeddingProvider | None = None,
) -> int:
    evidence_repository = evidence or CandidateEvidenceRepository()
    embedding_provider = embeddings or create_embedding_provider()
    indexed = 0
    for item in evidence_repository.list(limit=10_000):
        indexed += index_candidate_evidence(str(item["id"]), evidence=evidence_repository, embeddings=embedding_provider)
    return indexed
