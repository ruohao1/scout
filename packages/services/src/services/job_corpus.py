from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from db.jobs import JobRepository


@dataclass(frozen=True)
class JobCorpusStatus:
    total_jobs: int
    indexed_jobs: int
    unindexed_jobs: int
    source: str | None = None


def get_job_corpus_status(*, source: str | None = None, jobs: JobRepository | None = None) -> JobCorpusStatus:
    repository = jobs or JobRepository()
    rows = repository.list(limit=10_000, source=source)
    indexed_jobs = sum(1 for row in rows if _is_indexed(row))
    total_jobs = len(rows)
    return JobCorpusStatus(
        total_jobs=total_jobs,
        indexed_jobs=indexed_jobs,
        unindexed_jobs=total_jobs - indexed_jobs,
        source=source,
    )


def _is_indexed(row: dict[str, Any]) -> bool:
    return bool(row.get("is_indexed") or row.get("indexed_chunks", 0))
