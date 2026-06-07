from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Document:
    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Chunk:
    id: str
    document_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScoredChunk:
    chunk: Chunk
    score: float


@dataclass(frozen=True)
class JobChunk:
    job_id: str
    chunk_index: int
    section: str | None
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class JobSearchFilters:
    location: str | None = None
    contract_type: str | None = None
    company: str | None = None
    seniority: str | None = None
    remote_policy: str | None = None


@dataclass(frozen=True)
class JobSearchResult:
    job_id: str
    chunk_id: str
    chunk_index: int
    score: float
    title: str
    content: str
    section: str | None = None
    company: str | None = None
    location: str | None = None
    contract_type: str | None = None
    source: str | None = None
    url: str | None = None
    salary: str | None = None
    seniority: str | None = None
    remote_policy: str | None = None
    skills: list[str] = field(default_factory=list)
    created_at: datetime | None = None


@dataclass(frozen=True)
class RankedJob:
    job_id: str
    title: str
    final_score: float
    vector_score: float
    skill_overlap_score: float
    location_score: float
    contract_type_score: float
    recency_score: float
    selected_evidence_score: float = 0.0
    background_evidence_score: float = 0.0
    keyword_score: float = 0.0
    penalty_score: float = 0.0
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    matched_evidence: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[JobSearchResult] = field(default_factory=list)
    company: str | None = None
    location: str | None = None
    contract_type: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class ExplainedRankedJob:
    ranked_job: RankedJob
    why_match: str
    cv_suggestions: list[str] = field(default_factory=list)
