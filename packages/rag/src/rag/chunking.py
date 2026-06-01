from __future__ import annotations

from .types import Chunk, Document


def chunk_text(document: Document, *, chunk_size: int = 1_000, overlap: int = 150) -> list[Chunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if overlap < 0:
        raise ValueError("overlap must be greater than or equal to 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: list[Chunk] = []
    start = 0
    index = 0
    while start < len(document.text):
        end = min(start + chunk_size, len(document.text))
        text = document.text[start:end]
        chunks.append(
            Chunk(
                id=f"{document.id}:{index}",
                document_id=document.id,
                text=text,
                metadata={**document.metadata, "start": start, "end": end},
            )
        )
        if end == len(document.text):
            break
        start = end - overlap
        index += 1
    return chunks
