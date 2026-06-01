from __future__ import annotations

import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from psycopg.errors import UniqueViolation

from db.jobs import JobRepository

from .job_indexing import index_job
from .job_skills import enrich_job_skills


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


class AdzunaJobProviderClient:
    def __init__(
        self,
        *,
        app_id: str | None = None,
        app_key: str | None = None,
        country: str = "gb",
        what: str | None = None,
        where: str | None = None,
        results_per_page: int = 50,
        timeout: float = 30.0,
        base_url: str = "https://api.adzuna.com/v1/api/jobs",
    ) -> None:
        self.app_id = app_id or os.environ.get("ADZUNA_APP_ID")
        self.app_key = app_key or os.environ.get("ADZUNA_APP_KEY")
        self.country = country.strip().lower()
        self.what = what
        self.where = where
        self.results_per_page = results_per_page
        self.timeout = timeout
        self.base_url = base_url.rstrip("/")

    def fetch_jobs(self, *, count: int) -> list[dict[str, Any]]:
        if count <= 0:
            return []
        if not self.app_id or not self.app_key:
            raise ValueError("Adzuna requires ADZUNA_APP_ID and ADZUNA_APP_KEY, or --app-id and --app-key")
        if not self.country:
            raise ValueError("Adzuna country must not be empty")
        if self.results_per_page <= 0:
            raise ValueError("Adzuna results_per_page must be greater than 0")

        jobs: list[dict[str, Any]] = []
        page = 1
        while len(jobs) < count:
            page_size = min(self.results_per_page, count - len(jobs))
            payload = self._request_page(page=page, results_per_page=page_size)
            results = payload.get("results")
            if not isinstance(results, list):
                raise ValueError("Adzuna response did not include a results list")

            page_jobs = [job for job in results if isinstance(job, dict)]
            jobs.extend(page_jobs)
            if len(page_jobs) < page_size:
                break
            page += 1
        return jobs[:count]

    def _request_page(self, *, page: int, results_per_page: int) -> dict[str, Any]:
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": str(results_per_page),
            "content-type": "application/json",
        }
        if self.what:
            params["what"] = self.what
        if self.where:
            params["where"] = self.where

        country = urllib.parse.quote(self.country, safe="")
        url = f"{self.base_url}/{country}/search/{page}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers={"User-Agent": "scout-job-importer/0.1"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Adzuna request failed with HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Adzuna request failed: {exc.reason}") from exc
        if not isinstance(data, dict):
            raise ValueError("Adzuna response was not a JSON object")
        return data


class AdzunaJobProviderAdapter:
    def __init__(self, *, source: str = "adzuna") -> None:
        self.source = source

    def normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        title = _string_value(payload, "title")
        description = _clean_text(_string_value(payload, "description") or "")
        if not title:
            raise ValueError("Adzuna job payload is missing title")
        if not description:
            raise ValueError("Adzuna job payload is missing description")

        company = _dict_value(payload, "company")
        location = _dict_value(payload, "location")
        return {
            "title": title,
            "company": _string_value(company, "display_name"),
            "location": _adzuna_location(location),
            "contract_type": _adzuna_contract_type(payload),
            "source": self.source,
            "url": _adzuna_url(payload),
            "description": description,
            "salary": _adzuna_salary(payload),
            "seniority": _infer_seniority(f"{title}\n{description}"),
            "remote_policy": _infer_remote_policy(f"{title}\n{description}\n{_adzuna_location(location) or ''}"),
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
            job = repository.create(enrich_job_skills(adapter.normalize(payload)))
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


def _adzuna_location(location: dict[str, Any]) -> str | None:
    display_name = _string_value(location, "display_name")
    if display_name:
        return display_name
    area = location.get("area")
    if isinstance(area, list):
        parts = [item.strip() for item in area if isinstance(item, str) and item.strip()]
        return ", ".join(parts) if parts else None
    return None


def _adzuna_contract_type(payload: dict[str, Any]) -> str | None:
    contract_type = _string_value(payload, "contract_type")
    contract_time = _string_value(payload, "contract_time")
    normalized_type = (contract_type or "").lower().replace("_", "-")
    normalized_time = (contract_time or "").lower().replace("_", "-")
    if normalized_type == "contract":
        return "contract"
    if normalized_type == "permanent" or normalized_time == "full-time":
        return "full-time"
    if normalized_time == "part-time":
        return "part-time"
    return contract_type or contract_time


def _adzuna_url(payload: dict[str, Any]) -> str | None:
    redirect_url = _string_value(payload, "redirect_url")
    if redirect_url:
        return redirect_url
    adzuna_id = _string_value(payload, "id")
    return f"adzuna:{adzuna_id}" if adzuna_id else None


def _adzuna_salary(payload: dict[str, Any]) -> str | None:
    minimum = _number_value(payload.get("salary_min"))
    maximum = _number_value(payload.get("salary_max"))
    if minimum is not None and maximum is not None:
        return f"{_format_number(minimum)}-{_format_number(maximum)}"
    if minimum is not None:
        return f"from {_format_number(minimum)}"
    if maximum is not None:
        return f"up to {_format_number(maximum)}"
    return None


def _infer_seniority(text: str) -> str | None:
    normalized = text.lower()
    if re.search(r"\b(senior|sr\.?|principal|staff)\b", normalized):
        return "senior"
    if re.search(r"\b(lead|manager|head of)\b", normalized):
        return "lead"
    if re.search(r"\b(mid|middle|intermediate)\b", normalized):
        return "mid-level"
    if re.search(r"\b(junior|jr\.?|entry[- ]level|graduate)\b", normalized):
        return "junior"
    if re.search(r"\b(intern|internship|student|placement)\b", normalized):
        return "student"
    return None


def _infer_remote_policy(text: str) -> str | None:
    normalized = text.lower()
    if re.search(r"\bhybrid\b", normalized):
        return "hybrid"
    if re.search(r"\b(remote|work from home|wfh)\b", normalized):
        return "remote"
    if re.search(r"\b(onsite|on-site|office based)\b", normalized):
        return "onsite"
    return None


def _clean_text(value: str) -> str:
    text = html.unescape(value)
    text = re.sub(r"<\s*br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</\s*p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()


def _number_value(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None


def _format_number(value: float) -> str:
    if value.is_integer():
        return f"{int(value):,}".replace(",", " ")
    return f"{value:,.2f}".replace(",", " ")


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
