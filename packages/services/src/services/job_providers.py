from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from psycopg.errors import UniqueViolation

from db.jobs import JobRepository

from .job_indexing import index_job


class JobProviderClient(Protocol):
    def fetch_jobs(self, *, count: int) -> list[dict[str, Any]]:
        """Return raw job payloads in a provider-specific response shape."""


class JobProviderAdapter(Protocol):
    source: str

    def normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Convert one raw provider payload to a JobRepository-compatible dict."""


@dataclass(frozen=True)
class JobImportResult:
    created: list[dict[str, Any]]
    indexed: int = 0
    skipped: int = 0


class MockJobProviderClient:
    def __init__(self, *, fixture_path: Path | None = None) -> None:
        self.fixture_path = fixture_path

    def fetch_jobs(self, *, count: int) -> list[dict[str, Any]]:
        if self.fixture_path is not None:
            return _fixture_jobs(self.fixture_path, count=count)
        return [_mock_job(index) for index in range(count)]


class MockJobProviderAdapter:
    def __init__(self, *, source: str = "mock_jobs") -> None:
        self.source = source

    def normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        details = _dict_value(payload, "details")
        body = _dict_value(payload, "body")
        company = _dict_value(payload, "company")
        location = _dict_value(payload, "location")
        compensation = _dict_value(payload, "compensation")

        title = _string_value(payload, "role") or _string_value(payload, "title")
        description = _description(body=body, details=details)
        if not title:
            raise ValueError("Mock job payload is missing role/title")
        if not description:
            raise ValueError("Mock job payload is missing body/details content")

        return {
            "title": title,
            "company": _string_value(company, "name"),
            "location": _location(location),
            "contract_type": _string_value(details, "employment_type"),
            "source": self.source,
            "url": _string_value(payload, "apply_url"),
            "description": description,
            "salary": _salary(compensation),
            "seniority": _string_value(details, "seniority"),
            "remote_policy": _string_value(location, "remote_policy"),
            "skills": _string_list(payload.get("skills")),
            "raw_payload": payload,
        }


def import_jobs(
    *,
    client: JobProviderClient,
    adapter: JobProviderAdapter,
    count: int,
    jobs: JobRepository | None = None,
    should_index: bool = False,
) -> JobImportResult:
    repository = jobs or JobRepository()
    created: list[dict[str, Any]] = []
    indexed = 0
    skipped = 0

    for payload in client.fetch_jobs(count=count):
        try:
            job = repository.create(adapter.normalize(payload))
        except UniqueViolation:
            skipped += 1
            continue
        created.append(job)
        if should_index:
            index_job(str(job["id"]), jobs=repository)
            indexed += 1

    return JobImportResult(created=created, indexed=indexed, skipped=skipped)


def _fixture_jobs(path: Path, *, count: int) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        jobs = data["jobs"]
    elif isinstance(data, list):
        jobs = data
    else:
        raise ValueError("Fixture must be a JSON list or an object with a jobs list")

    payloads = [job for job in jobs if isinstance(job, dict)]
    if len(payloads) != len(jobs):
        raise ValueError("Fixture jobs must all be JSON objects")
    return payloads[:count]


def _mock_job(index: int) -> dict[str, Any]:
    job_id = f"mock-{uuid.uuid4()}"
    template = _MOCK_TEMPLATES[index % len(_MOCK_TEMPLATES)]
    location = _MOCK_LOCATIONS[index % len(_MOCK_LOCATIONS)]
    company = _MOCK_COMPANIES[index % len(_MOCK_COMPANIES)]

    return {
        "id": job_id,
        "role": template["role"],
        "company": {"name": company, "industry": template["industry"]},
        "location": location,
        "details": {
            "employment_type": template["employment_type"],
            "seniority": template["seniority"],
        },
        "compensation": template["compensation"],
        "skills": template["skills"],
        "body": {
            "mission": template["mission"],
            "responsibilities": template["responsibilities"],
            "requirements": template["requirements"],
            "benefits": template["benefits"],
        },
        "apply_url": f"https://jobs.example.test/{job_id}",
    }


def _description(*, body: dict[str, Any], details: dict[str, Any]) -> str:
    sections = []
    for heading in ("mission", "responsibilities", "requirements", "benefits"):
        text = body.get(heading) or details.get(heading)
        if isinstance(text, list):
            content = "\n".join(f"- {item}" for item in _string_list(text))
        elif isinstance(text, str):
            content = text.strip()
        else:
            content = ""
        if content:
            sections.append(f"{heading.title()}:\n{content}")
    return "\n\n".join(sections)


def _location(location: dict[str, Any]) -> str | None:
    city = _string_value(location, "city")
    country = _string_value(location, "country")
    if city and country:
        return f"{city}, {country}"
    return city or country


def _salary(compensation: dict[str, Any]) -> str | None:
    minimum = compensation.get("min")
    maximum = compensation.get("max")
    currency = _string_value(compensation, "currency") or "EUR"
    period = _string_value(compensation, "period") or "year"
    if isinstance(minimum, int) and isinstance(maximum, int):
        return f"{minimum:,}-{maximum:,} {currency}/{period}".replace(",", " ")
    return None


def _dict_value(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _string_value(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


_MOCK_COMPANIES = ["Northstar Labs", "Cobalt Works", "Meridian Health", "Atlas Fintech"]

_MOCK_LOCATIONS = [
    {"city": "Paris", "country": "France", "remote_policy": "hybrid"},
    {"city": "Lyon", "country": "France", "remote_policy": "remote"},
    {"city": "Berlin", "country": "Germany", "remote_policy": "onsite"},
]

_MOCK_TEMPLATES: list[dict[str, Any]] = [
    {
        "role": "Senior Backend Engineer",
        "industry": "Developer Tools",
        "employment_type": "full-time",
        "seniority": "senior",
        "compensation": {"min": 75000, "max": 95000, "currency": "EUR", "period": "year"},
        "skills": ["Python", "PostgreSQL", "FastAPI", "Distributed Systems"],
        "mission": "Build reliable APIs and data workflows for a fast-growing engineering platform.",
        "responsibilities": ["Design service boundaries", "Improve database performance", "Review production changes"],
        "requirements": ["Strong Python experience", "Production SQL experience", "Comfort owning backend services"],
        "benefits": ["Flexible remote policy", "Learning budget", "Modern engineering stack"],
    },
    {
        "role": "Machine Learning Engineer",
        "industry": "Healthcare",
        "employment_type": "full-time",
        "seniority": "mid-level",
        "compensation": {"min": 68000, "max": 88000, "currency": "EUR", "period": "year"},
        "skills": ["Python", "Embeddings", "MLOps", "Vector Search"],
        "mission": "Turn clinical and operational data into safe retrieval and ranking products.",
        "responsibilities": ["Evaluate model quality", "Maintain vector pipelines", "Collaborate with product teams"],
        "requirements": ["Experience with embeddings", "Python data tooling", "Clear communication"],
        "benefits": ["Research time", "Health coverage", "Conference budget"],
    },
    {
        "role": "Product Data Analyst",
        "industry": "Fintech",
        "employment_type": "contract",
        "seniority": "mid-level",
        "compensation": {"min": 550, "max": 750, "currency": "EUR", "period": "day"},
        "skills": ["SQL", "Python", "Experimentation", "Dashboards"],
        "mission": "Help product and growth teams understand customer behavior and funnel quality.",
        "responsibilities": ["Define metrics", "Build dashboards", "Analyze experiments"],
        "requirements": ["Advanced SQL", "Product analytics background", "Stakeholder management"],
        "benefits": ["High-impact projects", "Hybrid setup", "Autonomous team"],
    },
]
