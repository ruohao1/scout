from __future__ import annotations

import html
import json
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from psycopg.errors import UniqueViolation

from db.jobs import JobRepository

from .job_description_enrichment import JobDescriptionUnavailableError, enrich_weak_job_description, has_weak_job_description
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


SUPPORTED_JOBSPY_SITES = frozenset(
    {"bayt", "bdjobs", "glassdoor", "google", "indeed", "linkedin", "naukri", "zip_recruiter"}
)
DEFAULT_JOBSPY_SITES = ("linkedin", "indeed")


def jobspy_sites(value: object | None = None) -> list[str]:
    candidates = _site_candidates(value)
    sites = [site for site in candidates if site in SUPPORTED_JOBSPY_SITES]
    return sites or list(DEFAULT_JOBSPY_SITES)


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


class JobSpyJobProviderClient:
    def __init__(
        self,
        *,
        site_name: list[str] | str | None = None,
        search_term: str | None = None,
        location: str | None = None,
        distance: int | None = None,
        job_type: str | None = None,
        is_remote: bool | None = None,
        hours_old: int | None = None,
        country_indeed: str | None = "UK",
        verbose: int = 0,
        worker_url: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.site_name = site_name or list(DEFAULT_JOBSPY_SITES)
        self.search_term = search_term
        self.location = location
        self.distance = distance
        self.job_type = job_type
        self.is_remote = is_remote
        self.hours_old = hours_old
        self.country_indeed = country_indeed
        self.verbose = verbose
        self.worker_url = (worker_url or os.environ.get("JOBSPY_WORKER_URL") or "").rstrip("/")
        self.timeout = timeout

    def fetch_jobs(self, *, count: int) -> list[dict[str, Any]]:
        if count <= 0:
            return []
        if not self.search_term:
            raise ValueError("JobSpy search_term is required")

        params: dict[str, Any] = {
            "site_name": self.site_name,
            "search_term": self.search_term,
            "results_wanted": count,
            "description_format": "markdown",
            "verbose": self.verbose,
        }
        if self.country_indeed:
            params["country_indeed"] = self.country_indeed
        if self.location:
            params["location"] = self.location
        if self.distance is not None:
            params["distance"] = self.distance
        if self.job_type:
            params["job_type"] = self.job_type
        if self.is_remote is not None:
            params["is_remote"] = self.is_remote
        if self.hours_old is not None:
            params["hours_old"] = self.hours_old

        if self.worker_url:
            return self._fetch_jobs_from_worker(params)

        try:
            from jobspy import scrape_jobs
        except ImportError as exc:
            raise RuntimeError(
                "JobSpy is not installed. Run `uv sync` to install python-jobspy, "
                "or set JOBSPY_WORKER_URL to a running JobSpy worker."
            ) from exc

        jobs = scrape_jobs(**params)
        return [_json_safe(row) for row in jobs.to_dict(orient="records")]

    def _fetch_jobs_from_worker(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        request = urllib.request.Request(
            f"{self.worker_url}/scrape",
            data=json.dumps(params).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "scout-jobspy-client/0.1"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"JobSpy worker request failed with HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"JobSpy worker request failed: {exc.reason}") from exc

        if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
            raise ValueError("JobSpy worker response did not include a jobs list")
        return [job for job in data["jobs"] if isinstance(job, dict)]


class JobSpyJobProviderAdapter:
    def __init__(self, *, source: str = "jobspy") -> None:
        self.source = source

    def normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        title = _string_value(payload, "title")
        if not title:
            raise ValueError("JobSpy job payload is missing title")

        description = _jobspy_description(payload)
        return {
            "title": title,
            "company": _string_value(payload, "company"),
            "location": _jobspy_location(payload),
            "contract_type": _jobspy_contract_type(payload, f"{title}\n{description}"),
            "source": self.source,
            "url": _jobspy_url(payload),
            "description": description,
            "salary": _jobspy_salary(payload),
            "seniority": _infer_seniority(f"{title}\n{description}"),
            "remote_policy": _jobspy_remote_policy(payload, f"{title}\n{description}\n{_jobspy_location(payload) or ''}"),
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
        normalized = adapter.normalize(payload)
        try:
            try:
                normalized = enrich_weak_job_description(
                    normalized,
                    infer_seniority=_infer_seniority,
                    infer_remote_policy=_infer_remote_policy,
                )
            except JobDescriptionUnavailableError:
                pass
            job = repository.create(enrich_job_skills(normalized))
        except UniqueViolation:
            updated = _update_weak_duplicate(normalized, jobs=repository, should_index=should_index)
            if updated:
                indexed += 1 if should_index else 0
            skipped += 1
            continue
        created.append(job)
        if should_index:
            index_job(str(job["id"]), jobs=repository)
            indexed += 1

    return JobImportResult(created=created, indexed=indexed, skipped=skipped)


def _update_weak_duplicate(normalized: dict[str, Any], *, jobs: JobRepository, should_index: bool) -> dict[str, Any] | None:
    job_url = normalized.get("url")
    if not isinstance(job_url, str) or not job_url.startswith(("http://", "https://")):
        return None
    if has_weak_job_description(normalized):
        return None
    existing = jobs.get_by_url(job_url)
    if existing is None or not has_weak_job_description(existing):
        return None
    enriched = enrich_job_skills(normalized)
    updated = jobs.update_description(
        str(existing["id"]),
        description=str(normalized["description"]),
        skills=enriched.get("skills") or [],
        seniority=enriched.get("seniority"),
        remote_policy=enriched.get("remote_policy"),
        raw_payload=normalized.get("raw_payload") or {},
    )
    if updated and should_index:
        index_job(str(existing["id"]), jobs=jobs)
    return updated


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


def _jobspy_description(payload: dict[str, Any]) -> str:
    description = _clean_text(_string_value(payload, "description") or "")
    if description:
        return description

    parts = [_string_value(payload, "title")]
    company = _string_value(payload, "company")
    location = _jobspy_location(payload)
    if company:
        parts.append(f"Company: {company}")
    if location:
        parts.append(f"Location: {location}")
    return "\n".join(part for part in parts if part) or "Job offer imported from JobSpy."


def _jobspy_location(payload: dict[str, Any]) -> str | None:
    location = _string_value(payload, "location")
    if location:
        return location
    parts = [
        _string_value(payload, "city"),
        _string_value(payload, "state"),
        _string_value(payload, "country"),
    ]
    location_parts = [part for part in parts if part]
    return ", ".join(location_parts) if location_parts else None


def _jobspy_url(payload: dict[str, Any]) -> str | None:
    job_url = _string_value(payload, "job_url")
    if job_url:
        return job_url
    site = _string_value(payload, "site")
    job_id = _string_value(payload, "id") or _string_value(payload, "job_id")
    if site and job_id:
        return f"jobspy:{site}:{job_id}"
    return None


def _jobspy_salary(payload: dict[str, Any]) -> str | None:
    minimum = _number_value(payload.get("min_amount"))
    maximum = _number_value(payload.get("max_amount"))
    interval = _string_value(payload, "interval")
    currency = _string_value(payload, "currency")
    suffix = ""
    if currency:
        suffix = f" {currency}"
    if interval:
        suffix = f"{suffix}/{interval}" if suffix else f"/{interval}"
    if minimum is not None and maximum is not None:
        return f"{_format_number(minimum)}-{_format_number(maximum)}{suffix}"
    if minimum is not None:
        return f"from {_format_number(minimum)}{suffix}"
    if maximum is not None:
        return f"up to {_format_number(maximum)}{suffix}"
    return None


def _jobspy_contract_type(payload: dict[str, Any], text: str) -> str | None:
    job_type = _string_value(payload, "job_type")
    if job_type:
        normalized_type = job_type.strip().lower().replace("_", "-")
        if normalized_type == "fulltime":
            return "full-time"
        if normalized_type == "parttime":
            return "part-time"
        return normalized_type

    normalized = text.lower()
    if re.search(r"\b(intern|internship|stage|stagiaire|placement)\b", normalized):
        return "internship"
    if re.search(r"\b(contract|contractor|freelance)\b", normalized):
        return "contract"
    if re.search(r"\b(part[- ]?time|temps partiel)\b", normalized):
        return "part-time"
    if re.search(r"\b(full[- ]?time|permanent|temps plein)\b", normalized):
        return "full-time"
    return None


def _jobspy_remote_policy(payload: dict[str, Any], text: str) -> str | None:
    is_remote = payload.get("is_remote")
    if isinstance(is_remote, bool):
        return "remote" if is_remote else _infer_remote_policy(text)
    return _infer_remote_policy(text)


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


def _json_safe(value: object) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return isoformat()
    return str(value)


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


def _site_candidates(value: object | None) -> list[str]:
    if isinstance(value, str):
        raw = value.split(",")
    elif isinstance(value, list):
        raw = [item for item in value if isinstance(item, str)]
    else:
        raw = list(DEFAULT_JOBSPY_SITES)
    return [site.strip().lower() for site in raw if site.strip()]
