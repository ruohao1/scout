from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any
from urllib.parse import urlsplit

from db.config import database_url
from db.settings import AppSettingsRepository

from .job_providers import DEFAULT_JOBSPY_SITES, SUPPORTED_JOBSPY_SITES, jobspy_sites


JOBSPY_SITES_KEY = "jobspy_sites"
JOBSPY_DEFAULT_COUNT_KEY = "jobspy_default_count"
DEFAULT_JOBSPY_FETCH_COUNT = 15


@dataclass(frozen=True)
class JobSpyRuntimeSettings:
    sites: list[str]
    default_count: int


def get_jobspy_runtime_settings(*, settings: AppSettingsRepository | None = None) -> JobSpyRuntimeSettings:
    values = _settings(settings)
    sites = _configured_sites(values.get(JOBSPY_SITES_KEY))
    default_count = _bounded_count(values.get(JOBSPY_DEFAULT_COUNT_KEY), fallback=DEFAULT_JOBSPY_FETCH_COUNT)
    return JobSpyRuntimeSettings(sites=sites, default_count=default_count)


def get_runtime_settings(*, settings: AppSettingsRepository | None = None) -> dict[str, Any]:
    repository = settings or AppSettingsRepository()
    values = repository.list()
    jobspy = get_jobspy_runtime_settings(settings=repository)
    env_sites = jobspy_sites(os.environ.get("SCOUT_JOBSPY_SITES"))
    return {
        "jobspy": {
            "sites": jobspy.sites,
            "default_count": jobspy.default_count,
            "supported_sites": sorted(SUPPORTED_JOBSPY_SITES),
            "default_sites": list(DEFAULT_JOBSPY_SITES),
            "env_sites": env_sites,
        },
        "embeddings": {
            "provider": os.environ.get("SCOUT_EMBEDDINGS", "gemini"),
            "dimensions": _bounded_int(os.environ.get("SCOUT_EMBEDDING_DIMENSIONS"), fallback=1536, minimum=1, maximum=100_000),
            "gemini_model": os.environ.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"),
            "openai_model": os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        },
        "runtime": {
            "database": _safe_database_label(database_url()),
            "auth_dir": os.environ.get("SCOUT_AUTH_DIR", ".auth"),
        },
        "persisted_keys": sorted(values.keys()),
    }


def update_runtime_settings(payload: dict[str, Any], *, settings: AppSettingsRepository | None = None) -> dict[str, Any]:
    repository = settings or AppSettingsRepository()
    jobspy = payload.get("jobspy") if isinstance(payload.get("jobspy"), dict) else payload
    updates: dict[str, Any] = {}

    if "sites" in jobspy:
        sites = _site_list(jobspy["sites"])
        if not sites:
            raise ValueError("At least one supported JobSpy site must be selected")
        updates[JOBSPY_SITES_KEY] = sites

    if "default_count" in jobspy:
        updates[JOBSPY_DEFAULT_COUNT_KEY] = _bounded_int(jobspy["default_count"], fallback=DEFAULT_JOBSPY_FETCH_COUNT, minimum=1, maximum=25)

    for key, value in updates.items():
        repository.set(key, value)

    return get_runtime_settings(settings=repository)


def _settings(repository: AppSettingsRepository | None) -> dict[str, Any]:
    return (repository or AppSettingsRepository()).list()


def _configured_sites(value: object | None) -> list[str]:
    if value is None:
        value = os.environ.get("SCOUT_JOBSPY_SITES")
    return jobspy_sites(value)


def _site_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return jobspy_sites(value)


def _bounded_count(value: object, *, fallback: int) -> int:
    return _bounded_int(value, fallback=fallback, minimum=1, maximum=25)


def _bounded_int(value: object, *, fallback: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(parsed, maximum))


def _safe_database_label(url: str) -> str:
    parsed = urlsplit(url)
    host = parsed.hostname or "local"
    database = parsed.path.lstrip("/") or "default"
    return f"{host}/{database}"
