from __future__ import annotations

import hashlib
import math
import os
from typing import Protocol

from google import genai
from google.genai import types
from openai import OpenAI


class EmbeddingProvider(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector for each input text."""


class HashEmbeddingProvider:
    def __init__(self, *, dimensions: int = 1536) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be greater than 0")
        self.dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [_hash_embedding(text, dimensions=self.dimensions) for text in texts]


class OpenAIEmbeddingProvider:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
    ) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be greater than 0")
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimensions,
        )
        return [list(item.embedding) for item in response.data]


class GeminiEmbeddingProvider:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "gemini-embedding-001",
        dimensions: int = 1536,
    ) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be greater than 0")
        self.client = genai.Client(api_key=api_key or os.environ.get("GEMINI_API_KEY"))
        self.model = model
        self.dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.models.embed_content(
            model=self.model,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=self.dimensions,
            ),
        )
        return [list(item.values) for item in response.embeddings]


def create_embedding_provider() -> EmbeddingProvider:
    provider = os.environ.get("SCOUT_EMBEDDINGS", "gemini").strip().lower()
    dimensions = int(os.environ.get("SCOUT_EMBEDDING_DIMENSIONS", "1536"))

    if provider == "hash":
        return HashEmbeddingProvider(dimensions=dimensions)
    if provider == "gemini":
        return GeminiEmbeddingProvider(
            model=os.environ.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"),
            dimensions=dimensions,
        )
    if provider == "openai":
        return OpenAIEmbeddingProvider(
            model=os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            dimensions=dimensions,
        )
    raise ValueError(f"Unknown embedding provider: {provider}")


def _hash_embedding(text: str, *, dimensions: int) -> list[float]:
    values: list[float] = []
    seed = text.encode("utf-8")
    counter = 0
    while len(values) < dimensions:
        digest = hashlib.sha256(seed + counter.to_bytes(8, "big")).digest()
        values.extend((byte / 127.5) - 1.0 for byte in digest)
        counter += 1

    vector = values[:dimensions]
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]
